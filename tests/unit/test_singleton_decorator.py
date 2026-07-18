from src.utils.decorators import singleton


def test_singleton_returns_same_instance_across_calls():
    @singleton
    class Service:
        def __init__(self):
            self.value = object()

    a = Service()
    b = Service()

    assert a is b


def test_singleton_ignores_args_on_subsequent_calls():
    @singleton
    class Service:
        def __init__(self, name):
            self.name = name

    a = Service("first")
    b = Service("second")

    assert a is b
    assert a.name == "first"


def test_singleton_reset_allows_new_instance():
    @singleton
    class Service:
        def __init__(self):
            self.value = object()

    a = Service()
    Service.reset()
    b = Service()

    assert a is not b


def test_independent_singleton_classes_do_not_share_instances():
    @singleton
    class ServiceA:
        pass

    @singleton
    class ServiceB:
        pass

    a = ServiceA()
    b = ServiceB()

    assert type(a) is not type(b)
