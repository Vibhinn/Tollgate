import threading
import time

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


def test_concurrent_resolve_of_uncached_singleton_builds_exactly_once(container):
    """Regression test: resolve() used to have no locking around the
    check-then-build-then-cache sequence, so many threads racing to resolve
    the same not-yet-cached singleton (e.g. many concurrent requests hitting
    a cold DI container) would each build their own instance - duplicating
    expensive construction (in production, this meant loading a ~500MB local
    model once per racing thread instead of once total)."""
    call_count = 0
    build_lock = threading.Lock()

    def slow_factory():
        nonlocal call_count
        with build_lock:
            call_count += 1
        time.sleep(0.05)  # widen the race window
        return ServiceA()

    container.register(ServiceA, slow_factory, singleton=True)

    results = []
    errors = []

    def worker():
        try:
            results.append(container.resolve(ServiceA))
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    assert call_count == 1
    assert len(results) == 20
    assert all(r is results[0] for r in results)


def test_resolve_can_recurse_into_another_resolve_on_the_same_thread(container):
    """Regression test: a factory commonly resolves other dependencies while
    it's still building (mirrors ChatAdapter -> RouterRepository ->
    RouterAdapter -> RoutingIntelligenceLayer in build.py, all resolved on
    one thread inside one outer resolve() call). A plain threading.Lock
    deadlocks the thread against itself the first time this happens, since
    the outer resolve() is still holding the lock when the inner resolve()
    tries to acquire it again. Needs a reentrant lock."""

    class Inner:
        pass

    class Outer:
        def __init__(self, inner):
            self.inner = inner

    container.register(Inner, lambda: Inner())
    container.register(Outer, lambda: Outer(container.resolve(Inner)))

    result_holder = {}

    def resolve_outer():
        result_holder["outer"] = container.resolve(Outer)

    t = threading.Thread(target=resolve_outer)
    t.start()
    t.join(timeout=2)

    assert not t.is_alive(), "resolve() deadlocked on a recursive call"
    assert isinstance(result_holder.get("outer"), Outer)
    assert isinstance(result_holder["outer"].inner, Inner)
