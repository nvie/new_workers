from rq.worker.fakeness import FakeWorkMethodMixin
from rq.worker.helpers import install_signal_handlers


class BaseWorker(FakeWorkMethodMixin):
    def install_signal_handlers(self):
        install_signal_handlers()

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

    def work(self):
        self.install_signal_handlers()

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
