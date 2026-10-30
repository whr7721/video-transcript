"""Local speaker clustering, separate from immutable recognition text."""
import wave
from pathlib import Path
import numpy as np
import setup_speakers
VERSION='campplus-zh-en-pyannote-int8-v1'
def turns(audio,speakers=0):
 import sherpa_onnx as s
 root=Path(__file__).parent/'models'
 if not all(setup_speakers.verify(root).values()):raise ValueError('说话人模型未就绪，请先运行 setup_speakers.py')
 config=s.OfflineSpeakerDiarizationConfig(segmentation=s.OfflineSpeakerSegmentationModelConfig(pyannote=s.OfflineSpeakerSegmentationPyannoteModelConfig(model=str(root/setup_speakers.SEG))),embedding=s.SpeakerEmbeddingExtractorConfig(model=str(root/setup_speakers.EMBED),num_threads=4),clustering=s.FastClusteringConfig(num_clusters=speakers if speakers else -1,threshold=0.5),min_duration_on=0.3,min_duration_off=0.5)
 if not config.validate():raise ValueError('说话人模型配置无效')
 with wave.open(str(audio)) as f:
  if (f.getframerate(),f.getnchannels(),f.getsampwidth())!=(16000,1,2):raise ValueError('说话人音频格式无效')
  samples=np.frombuffer(f.readframes(f.getnframes()),dtype=np.int16).astype(np.float32)/32768
 diarizer=s.OfflineSpeakerDiarization(config);labels={};out=[]
 for t in diarizer.process(samples).sort_by_start_time():
  label=labels.setdefault(t.speaker,'说话人'+str(len(labels)+1));out.append({'start':t.start,'end':t.end,'speaker':label})
 if not out:raise ValueError('未检测到有效说话人')
 return out

def annotate(result,rows):
 segments=[]
 for seg in result.get('segments',[]):
  overlap={}
  for row in rows:
   seconds=max(0,min(seg['end'],row['end'])-max(seg['start'],row['start']))
   overlap[row['speaker']]=overlap.get(row['speaker'],0)+seconds
  label=max(overlap,key=overlap.get) if overlap and max(overlap.values())>0 else '未确定'
  segments.append({**seg,'speaker':label})
 return {**result,'segments':segments,'speaker_turns':rows,'diarization_version':VERSION}
