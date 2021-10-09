import psutil
import sys


def wait_or_when_cancelled(pid):
    proc = psutil.Process(pid=int(pid))
    while True:
        try:
            proc.wait(timeout=1)
            exit(1)
        except psutil.TimeoutExpired:
            continue
        except KeyboardInterrupt:
            break


wait_or_when_cancelled(sys.argv[1])
