import functools
import threading
import inspect


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


class UndeclaredException(Exception):
    pass

def throws_exception(*exceptions, strict: bool = True):
    """For wrapping functions - list all the exceptions you """

    def decorator(func):
        is_async_function: bool = inspect.iscoroutinefunction(func)

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except exceptions:
                raise
            except Exception as e:
                if strict:
                    raise UndeclaredException(e) from e
                raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except exceptions:
                raise
            except Exception as e:
                if strict:
                    raise UndeclaredException(e) from e
                raise

        return async_wrapper if is_async_function else sync_wrapper

    return decorator