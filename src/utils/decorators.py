import functools
import threading

def singleton(cls):
    """
    Decorator that turns a class into a singleton.

    Usage:
        @singleton
        class DatabasePool:
            def __init__(self, url):
                self.url = url

        a = DatabasePool("postgres://localhost")
        b = DatabasePool("postgres://localhost")
        assert a is b  # True — same instance
    """
    instances = {}
    lock = threading.Lock()

    @functools.wraps(cls)
    def get_instance(*args, **kwargs):
        if cls not in instances:
            with lock:
                if cls not in instances:
                    instances[cls] = cls(*args, **kwargs)
        return instances[cls]

    get_instance.reset = lambda: instances.pop(cls, None)

    return get_instance