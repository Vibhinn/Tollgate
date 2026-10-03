from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from build import Builder
from src.app.injector import container
from src.jobs import RedisStreamRepository
from src.app.migrations import BaseMigration
from src.router import RouterRepository
from src.app.intelligence import RoutingIntelligenceLayer
from src.cache import RedisRepository
from src.utils.types import RedisAtomicCounters

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler: RedisStreamRepository = container.resolve(RedisStreamRepository)
    router_repository: RouterRepository = container.resolve(RouterRepository)
    db_migrations: BaseMigration = container.resolve(BaseMigration)
    routing_intelligence: RoutingIntelligenceLayer = container.resolve(RoutingIntelligenceLayer)
    redis_repository: RedisRepository = container.resolve(RedisRepository)

    await db_migrations.run_all()
    await redis_repository.save(RedisAtomicCounters.IN_FLIGHT, 0)
    scheduler.start()
    await router_repository.warm_up_latency_rankings()

    yield

    routing_intelligence.shutdown()


app = FastAPI(lifespan=lifespan)
builder = Builder(app)
builder.build_and_initialize_app()

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=13000, reload=False)