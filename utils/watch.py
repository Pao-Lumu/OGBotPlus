import psutil
import sys


def wait_or_when_cancelled(pid):
    proc = psutil.Process(pid=int(pid))
    while True:
        try:
            proc.wait(timeout=1)
        except psutil.TimeoutExpired:
            continue
        except KeyboardInterrupt:
            break
        finally:
            exit(1)


wait_or_when_cancelled(sys.argv[1])