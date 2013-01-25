import os
import errno
import signal


def install_signal_handlers():
    signal.signal(signal.SIGINT, signal.default_int_handler)
    signal.signal(signal.SIGTERM, signal.default_int_handler)


def disable_interrupts():
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    signal.signal(signal.SIGTERM, signal.SIG_IGN)


class Interruptable(object):
    def __enter__(self):
        install_signal_handlers()

    def __exit__(self, type, value, traceback):
        disable_interrupts()


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
