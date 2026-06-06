import functools
import threading

from src.utils.exceptions import PrivateMethodError

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


def private(method):
    """
    Decorator that enforces method privacy at runtime.
    Raises PrivateMethodError if called from outside the owning class.

    Usage:
        class PaymentService:
            @private
            def _validate_card(self, number):
                return len(number) == 16

            def charge(self, amount, card):
                self._validate_card(card)  # works fine — internal call
                ...

        svc = PaymentService()
        svc._validate_card("1234")  # raises PrivateMethodError
    """

    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        import sys
        caller_frame = sys._getframe(1)
        caller_locals = caller_frame.f_locals

        caller_self = caller_locals.get("self", None)
        if caller_self is self:
            return method(self, *args, **kwargs)

        raise PrivateMethodError(
            f"'{method.__name__}' is private and cannot be called from outside "
            f"'{type(self).__name__}'"
        )

    wrapper._is_private = True
    return wrapper
