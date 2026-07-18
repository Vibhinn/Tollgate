import pytest

from src.app.injector.dependency_container import DependencyContainer


class ServiceA:
    pass


class ServiceB:
    pass


@pytest.fixture
def container():
    return DependencyContainer()


def test_resolve_unregistered_type_raises(container):
    with pytest.raises(ValueError, match="ServiceA"):
        container.resolve(ServiceA)


def test_singleton_registration_returns_same_instance(container):
    calls = []

    def factory():
        calls.append(1)
        return ServiceA()

    container.register(ServiceA, factory, singleton=True)

    first = container.resolve(ServiceA)
    second = container.resolve(ServiceA)

    assert first is second
    assert len(calls) == 1


def test_non_singleton_registration_returns_new_instance_each_time(container):
    calls = []

    def factory():
        calls.append(1)
        return ServiceA()

    container.register(ServiceA, factory, singleton=False)

    first = container.resolve(ServiceA)
    second = container.resolve(ServiceA)

    assert first is not second
    assert len(calls) == 2


def test_different_abstractions_resolve_independently(container):
    container.register(ServiceA, lambda: ServiceA())
    container.register(ServiceB, lambda: ServiceB())

    a = container.resolve(ServiceA)
    b = container.resolve(ServiceB)

    assert isinstance(a, ServiceA)
    assert isinstance(b, ServiceB)


def test_re_registering_before_first_resolve_replaces_factory(container):
    container.register(ServiceA, lambda: "first")
    container.register(ServiceA, lambda: "second")

    assert container.resolve(ServiceA) == "second"
