from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.app.injector import container
from src.jobs import RedisStreamRepository, MetricsAggregator
from src.app.migrations import BaseMigration
from src.router import RouterRepository
from src.app.intelligence import RoutingIntelligenceLayer
from src.cache import RedisRepository
from src.utils.types import RedisAtomicCounters


class ApplicationLifespan:
    @staticmethod
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        routing_intelligence: RoutingIntelligenceLayer = container.resolve(RoutingIntelligenceLayer)
        metrics_aggregator: MetricsAggregator | None = None
        try:
            scheduler: RedisStreamRepository = container.resolve(RedisStreamRepository)
            router_repository: RouterRepository = container.resolve(RouterRepository)
            db_migrations: BaseMigration = container.resolve(BaseMigration)
            redis_repository: RedisRepository = container.resolve(RedisRepository)
            metrics_aggregator: MetricsAggregator = container.resolve(MetricsAggregator)

            await db_migrations.run_all()
            await redis_repository.save(RedisAtomicCounters.IN_FLIGHT, 0)
            scheduler.start()
            await router_repository.warm_up_latency_rankings()

            await metrics_aggregator.start()

            yield
        finally:
            metrics_aggregator.stop()
            routing_intelligence.shutdown()
