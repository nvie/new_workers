from gevent import monkey
monkey.patch_all()

import random
import signal
import gevent
import gevent.pool
from gevent.event import Event
import time
from base_worker import BaseWorker


class GeventWorker(BaseWorker):

    ##
    # Overridden from BaseWorker
    def __init__(self, num_processes=1):
        self._pool = gevent.pool.Pool(num_processes)

        # In this dictionary, we keep a greenlet -> Event mapping to indicate
        # whether that greenlet is in idle or busy state.  Greenlets that are
        # in busy state will not be terminated, since that might lead to loss
        # of work.  The Event is a gevent synchronisation primitive that can
        # be used to let the child set a flag that the main worker acts on.
        self._busy = {}

    def install_signal_handlers(self):
        # Enabling the following line to explicitly set SIGINT yields very
        # weird behaviour: can anybody explain?
        # gevent.signal(signal.SIGINT, signal.default_int_handler)
        gevent.signal(signal.SIGTERM, signal.default_int_handler)

    def get_ident(self):
        return id(gevent.getcurrent())

    def spawn_child(self):
        """Forks and executes the job."""
        busy_flag = Event()
        child_greenlet = self._pool.spawn(self._main_child, busy_flag)
        self._busy[child_greenlet] = busy_flag
        child_greenlet.link(self._unregister_child)

    def terminate_idle_children(self):
        print 'Find all children that are in idle state (waiting for work)...'
        for child_greenlet, busy_flag in self._busy.items():
            if not busy_flag.is_set():
                print '==> Killing {}'.format(id(child_greenlet))
                child_greenlet.kill()
            else:
                print '==> Waiting for {} (still busy)'.format(id(child_greenlet))

    def wait_for_children(self):
        print 'Waiting for children to finish gracefully...'
        self._pool.join()
        print 'YIPPY!'

    def kill_children(self):
        print 'Killing all children...'
        self._pool.kill()
        print 'MWHUAHAHAHAHA!'
        self.wait_for_children()


    ##
    # Helper methods (specific to gevent workers)
    def _unregister_child(self, child):  # noqa
        print '==> Unregistering {}'.format(id(child))
        del self._busy[child]

    def _main_child(self, busy_flag):
        busy_flag.clear()  # Not really necessary, but explicit
        time.sleep(random.random() * 4)  # TODO: Fake BLPOP behaviour
        busy_flag.set()

        time.sleep(0)  # TODO: Required to avoid "blocking" by CPU-bound jobs
        self.fake()


if __name__ == '__main__':
    gw = GeventWorker(10)
    gw.work()
