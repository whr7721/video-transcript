"""Hold an OS lock for the entire lifetime, including worker shutdown."""
import os


def acquire(path):
    file=path.open('a+b')
    file.seek(0)
    if not file.read(1): file.write(b'0');file.flush()
    file.seek(0)
    try:
        if os.name=='nt':
            import msvcrt
            msvcrt.locking(file.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(file,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except OSError:
        file.close()
        raise RuntimeError('此核心数据目录已有服务运行；请勿多进程共享缓冲') from None
    return file
