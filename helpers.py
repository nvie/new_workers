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
