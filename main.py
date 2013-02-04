import sys
from rq.worker import make_worker


if __name__ == '__main__':
    backend = sys.argv[1]
    if len(sys.argv) > 2:
        num = int(sys.argv[2])
    else:
        num = 1
    w = make_worker(backend, num)
    w.work()
