from gevent import monkey
monkey.patch_all()
import gevent.pool

import os
import random
import time
import datetime
from multiprocessing import Semaphore, Array


class BaseWorker(object):

    def work(self):
        while True:
            self.spawn_child()

    def spawn_child(self):
        raise NotImplementedError('Implement this in a subclass.')

    def fake_work(self):
        sleep_time = 3 * random.random()
        print datetime.datetime.now(), '- Hello from', os.getpid(), '- %.3fs' % sleep_time
        time.sleep(sleep_time)



class ForkingWorker(BaseWorker):

    def __init__(self, num_processes=1):
        self._semaphore = Semaphore(num_processes)
        self._slots = Array('i', [0] * num_processes)

    def spawn_child(self):
        """Forks and executes the job."""
        self._semaphore.acquire()

        for slot, value in enumerate(self._slots):
            if value == 0:
                break

        child_pid = os.fork()
        if child_pid == 0:
            random.seed()
            # Within child
            try:
                self.fake_work()
            finally:
                self._slots[slot] = 0
                self._semaphore.release()
                os._exit(0)
        else:
            # Within parent
            self._slots[slot] = child_pid


class GeventWorker(BaseWorker):

    def __init__(self, num_processes=1):
        self._pool = gevent.pool.Pool(num_processes)

    def spawn_child(self):
        """Forks and executes the job."""
        self._pool.spawn(self.fake_work)


if __name__ == '__main__':
    #fw = ForkingWorker(4)
    #fw.work()

    gw = GeventWorker(4)
    gw.work()
