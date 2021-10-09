import psutil
import sys


def wait_or_when_cancelled(pid):
    print(pid)
    print(type(pid))
    proc = psutil.Process(pid=pid)
    while True:
        try:
            proc.wait(timeout=1)
        except psutil.TimeoutExpired:
            continue
        except KeyboardInterrupt:
            break
        finally:
            exit(0)


wait_or_when_cancelled(sys.argv[0])
