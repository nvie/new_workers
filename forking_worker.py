import signal
import os
import time
import random
import errno
from multiprocessing import Semaphore, Array
from base_worker import BaseWorker


def waitpid(pid):
    """
    Safe version of `os.waitpid(pid, 0)` that catches OSError in case of an
    already-gone child pid.
    """
    try:
        os.waitpid(pid, 0)
    except OSError as e:
        if e.errno != errno.ECHILD:
            # Allow "No such process", since that means process is
            # already gone---no need to wait for it to finish
            raise


def kill(pid, signum=signal.SIGKILL):
    """
    Safe version of `os.kill(pid, signum)` that catches OSError in case of an
    already-dead pid.
    """
    try:
        os.kill(pid, signum)
    except OSError as e:
        if e.errno != errno.ESRCH:
            # Allow "No such process", since that means process is
            # already gone---no need to kill what's already dead
            raise


class ForkingWorker(BaseWorker):

    def __init__(self, num_processes=1):
        # Set up sync primitives, to communicate with the spawned children
        self.num_processes = num_processes

        # This semaphore is used as a "worker pool guard" to keep the number
        # of spawned workers in the pool to the specified maximum (and block
        # the .spawn_child() call after that)
        self._semaphore = Semaphore(num_processes)

        # This array of integers represents a slot per worker and holds the
        # actual pids (process ids) of the worker's children.  Initially, the
        # array-of-pids is all zeroes.  When a new child is spawned, the pid
        # is written into the slot.  WHen a child finishes, it resets its own
        # slot to 0 again, effectively freeing up the slot (and allowing new
        # children to be spawned).
        self._pids = Array('i', [0] * num_processes)

        # This array of integers also represents a slot per worker and also
        # holds the actual pids of the worker's children.  The difference with
        # _pids, however, is that this array's slots don't get reset
        # immediately when the children end.  In order for Unix subprocesses
        # to actually disappear from the process list (and freeing up the
        # memory), they need to be waitpid()'ed for by the parent process.
        # When each new child is spawned, it waitpid()'s for the (finished)
        # child that was previously in that slot before it claims the new
        # slot.  This mainly avoids ever-growing process lists and slowly
        # growing the memory footprint.
        self._waitfor = Array('i', [0] * num_processes)

        # This array of booleans represent workers that are in their idle
        # state (i.e. they are waiting for work).  During this time, it is
        # safe to terminate them when the user requests so.  Once they start
        # processing work, they flip their idle state and won't be terminated
        # while they're still doing work.
        self._idle = Array('b', [False] * num_processes)

    def get_ident(self):
        return os.getpid()

    def disable_interrupts(self):
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        signal.signal(signal.SIGTERM, signal.SIG_IGN)

    def spawn_child(self):
        """Forks and executes the job."""
        self.install_signal_handlers()

        # Responsible for the blocking, may be interrupted by SIGINT or
        # SIGTERM, the worker's main loop will catch it
        self._semaphore.acquire()

        self.disable_interrupts()
        self._fork()

    def _fork(self):
        slot = self._claim_slot()

        # The usual hardcore forking action
        child_pid = os.fork()
        if child_pid == 0:
            random.seed()

            # Within child
            try:
                self._idle[slot] = True
                time.sleep(random.random() * 4)  # TODO: Fake BLPOP behaviour
                self._idle[slot] = False
                self.fake()
            finally:
                # Remember, we're in the child process currently. When all
                # work is done here, free up the current slot (by writing
                # a 0 in the slot position).  This communicates to the parent
                # that the current child has died (so can safely be forgotten
                # about).
                self._pids[slot] = 0
                self._semaphore.release()
                os._exit(0)
        else:
            # Within parent, keep track of the new child by writing its PID
            # into the first free slot index.
            self._pids[slot] = child_pid
            self._waitfor[slot] = child_pid

    def _claim_slot(self):
        slot = self._find_empty_slot()
        self._wait_for_previous_worker(slot)
        return slot

    def _find_empty_slot(self):
        # Select an empty slot from self._pids (the first 0 value is picked)
        # The implementation guarantees there will always be at least one empty slot
        for slot, value in enumerate(self._pids):
            if value == 0:
                return slot
        raise RuntimeError('This should never happen.')

    def _wait_for_previous_worker(self, slot):
        if self._waitfor[slot] > 0:
            os.waitpid(self._waitfor[slot], 0)
            self._waitfor[slot] = 0

    def wait_for_children(self):
        """
        Wait for children to finish their execution.  This function should
        block until all children are finished.  May be interrupted by another
        press of Ctrl+C, which kicks off forceful termination.
        """
        # As soon as we can acquire all slots, we're done executing
        for pid in self._pids:
            if pid != 0:
                print 'waiting for pid %d to finish gracefully...' % (pid,)
                waitpid(pid)

    def terminate_idle_children(self):
        for slot, idle in enumerate(self._idle):
            pid = self._pids[slot]
            if idle:
                print '==> Killing idle pid {}'.format(pid)
                kill(pid, signal.SIGKILL)
                #os.waitpid(pid, 0)  # necessary?
            else:
                print '==> Waiting for pid {} (still busy)'.format(pid)

    def kill_children(self):
        """
        Force-kill all children.  This function should block until all
        children are terminated.
        """
        # As soon as we can acquire all slots, we're done executing
        for pid in self._pids:
            if pid != 0:
                print 'killing pid %d...' % (pid,)
                kill(pid, signal.SIGKILL)

        self.wait_for_children()


if __name__ == '__main__':
    w = ForkingWorker(4)
    w.work()
