import random
import time
import datetime
import signal
from helpers import install_signal_handlers


def slow_fib(n):
    return 1 if n <= 2 else slow_fib(n - 1) + slow_fib(n - 2)


class FakeWorkMethodMixin(object):
    """
    This is just a dummy place to hold the logic that can be replaced by RQ's
    job popping and execution.
    """
    def fake_wait(self):
        """This is a fake IO-bound method."""
        sleep_time = 10 * random.random()
        print datetime.datetime.now(), '- Hello from', self.get_ident()
        time.sleep(sleep_time)
        print datetime.datetime.now(), '- Done from', self.get_ident()

    def fake_fib(self, n=30):
        """This is a fake CPU-bound method."""
        print slow_fib(n)

    def fake_url_get(self, url='http://nvie.com/about'):
        """This is a fake IO-bound method that has network access."""
        import requests
        word_count = len(requests.get(url).text.split())
        print '{} contains {} words.'.format(url, word_count)

    def fake(self):
        """
        This simulates a BLPOP call, which will block until a job is
        available.
        """
        methods = [self.fake_wait, self.fake_fib, self.fake_url_get]
        random.choice(methods)()


class BaseWorker(FakeWorkMethodMixin):

    def work(self):
        install_signal_handlers()

        while True:
            try:
                self.spawn_child()
            except KeyboardInterrupt:
                self.terminate_idle_children()
                break

        try:
            self.wait_for_children()
        except KeyboardInterrupt:
            print 'Cold shutdown entered'
            self.kill_children()
            print 'Children killed. You murderer.'

        print 'Shut down'

    def get_ident(self):
        raise NotImplementedError('Implement this in a subclass.')

    def spawn_child(self):
        raise NotImplementedError('Implement this in a subclass.')

    def terminate_idle_children(self):
        raise NotImplementedError('Implement this in a subclass.')

    def wait_for_children(self):
        raise NotImplementedError('Implement this in a subclass.')

    def kill_children(self):
        raise NotImplementedError('Implement this in a subclass.')


if __name__ == '__main__':
    pass
