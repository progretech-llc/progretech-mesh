"""Process locks for the host-local office on Unix and Windows."""
import os


def lock(stream, blocking=True):
    if os.name == 'nt':
        import msvcrt
        stream.seek(0)
        # Windows forbids even reading another handle's locked byte. Checking
        # file size avoids touching that range before the lock attempt.
        if os.fstat(stream.fileno()).st_size == 0:
            stream.write('0'); stream.flush()
        stream.seek(0)
        try:
            msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK if blocking else msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            raise BlockingIOError('office_locked') from exc
    else:
        import fcntl
        fcntl.flock(stream, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))


def unlock(stream):
    if os.name == 'nt':
        import msvcrt
        stream.seek(0); msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(stream, fcntl.LOCK_UN)
