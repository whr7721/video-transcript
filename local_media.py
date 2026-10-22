"""Strict file admission and bounded, non-network audio preparation."""
import json
import math
import subprocess
import tempfile
import time
import wave
from pathlib import Path

MAX_BYTES = 1_000_000_000
MAX_SECONDS = 7200
# Leave enough room to decode past a dishonest duration and reject, rather than silently truncate.
# The muxer can finish its final packet after -fs; that packet has a separate reserved margin.
WAV_BUDGET = (MAX_SECONDS+3) * 32000 + 131072
EXTENSIONS = {'.mp3':'mp3','.flac':'flac','.wav':'wav','.m4a':'mov','.mp4':'mov','.mov':'mov'}


def display_name(name):
    if not name or len(name)>255 or any(ord(c)<32 for c in name) or any(c in name for c in '/\\:') or name in {'.','..'}:
        raise ValueError('请提供不含路径的有效文件名')
    if Path(name).suffix.lower() not in EXTENSIONS:
        raise ValueError('仅支持 MP3/M4A/WAV/FLAC/MP4/MOV')
    return name


def input_args(path, container):
    args = ['-protocol_whitelist','file','-format_whitelist','mp3,wav,flac,mov','-max_streams','64','-f',container]
    if container=='mov':
        args += ['-enable_drefs','0','-use_absolute_path','0']
    return args + ['-i',str(path)]


def inspect(path, name):
    container = EXTENSIONS[Path(display_name(name)).suffix.lower()]
    with path.open('rb') as f:
        head = f.read(16)
    signature = {'wav':head[:4]==b'RIFF' and head[8:12]==b'WAVE',
                 'flac':head[:4]==b'fLaC',
                 'mp3':head[:3]==b'ID3' or (len(head)>1 and head[0]==255 and head[1]&224==224),
                 'mov':head[4:8] in {b'ftyp',b'moov',b'mdat',b'wide',b'free'}}[container]
    if not signature:
        raise ValueError('文件内容与格式不符，或不支持这种容器')
    try:
        r = subprocess.run(['ffprobe','-v','error',*input_args(path,container),'-show_entries','format=duration,format_name:stream=codec_type,index,codec_name','-of','json'],
                           capture_output=True,check=True,timeout=35)
        info=json.loads(r.stdout)
        duration=float(info.get('format',{}).get('duration',0))
        audio=[s for s in info.get('streams',[]) if s.get('codec_type')=='audio']
        if not audio or not math.isfinite(duration) or duration<=0 or duration>MAX_SECONDS+0.5:
            raise ValueError('文件必须有音轨且时长不超过两小时')
        return {'container':container,'duration':duration,'audio_tracks':len(audio),
                'has_video':any(s.get('codec_type')=='video' for s in info.get('streams',[]))}
    except (subprocess.SubprocessError,json.JSONDecodeError,TypeError,OverflowError):
        raise ValueError('媒体无法解析或已损坏') from None


def cached_audio(audio):
    if audio.is_file():
        try:
            with wave.open(str(audio),'rb') as f:
                if (f.getframerate(),f.getnchannels(),f.getsampwidth())==(16000,1,2) and 0<f.getnframes()/16000<=MAX_SECONDS+0.05:
                    if audio.stat().st_size>=f.getnframes()*2+44:
                        return f.getnframes()/16000
        except (wave.Error,EOFError,OSError):
            pass
    return None


def wav_budget(info):
    return min(WAV_BUDGET,math.ceil(info['duration']+3)*32000+131072)


def prepare(source, audio, info, stopped=lambda:False):
    cached=cached_audio(audio)
    if cached: return cached
    if audio.exists():
        audio.unlink()
    partial=audio.with_name('audio.partial.wav')
    command=['ffmpeg','-nostdin','-v','error','-xerror','-err_detect','explode','-y',*input_args(source,info['container']),
             '-map','0:a:0','-vn','-sn','-dn','-ac','1','-ar','16000','-af','asetnsamples=n=1024:p=0',
             '-c:a','pcm_s16le','-fs',str(wav_budget(info)-65536),str(partial)]
    try:
        with tempfile.TemporaryFile() as errors:
            process=subprocess.Popen(command,stdout=subprocess.DEVNULL,stderr=errors)
            started=time.monotonic()
            try:
                while process.poll() is None:
                    if stopped(): raise InterruptedError('处理已暂停，重启后恢复')
                    if time.monotonic()-started>1200 or errors.tell()>1_000_000:
                        raise ValueError('音轨转换超过处理保护上限')
                    time.sleep(0.05)
                if process.returncode: raise ValueError('音轨解码失败，文件可能损坏')
            finally:
                if process.poll() is None:
                    process.kill();process.wait()
        with wave.open(str(partial),'rb') as f:
            duration=f.getnframes()/16000
        if not 0<duration<=MAX_SECONDS+0.05 or abs(duration-info['duration'])>2:
            raise ValueError('实际解码时长与声明不符或超过两小时')
        partial.replace(audio)
        return duration
    finally:
        partial.unlink(missing_ok=True)
