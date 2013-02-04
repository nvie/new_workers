import random
import time
import datetime


def make_worker(backend, num_processes=1):
    if backend == 'gevent':
        from rq.worker.gevent import GeventWorker
        return GeventWorker(num_processes)
    elif backend == 'forking':
        from rq.worker.forking import ForkingWorker
        return ForkingWorker(num_processes)
    else:
        raise ValueError('Unknown concurrency backend implementation.')
