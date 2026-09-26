from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from build import Builder
from src.app.injector import container
from src.jobs import RedisStreamRepository
from src.app.migrations import BaseMigration
from src.router import RouterRepository
from src.app.intelligence import RoutingIntelligenceLayer

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler: RedisStreamRepository = container.resolve(RedisStreamRepository)
    router_repository: RouterRepository = container.resolve(RouterRepository)
    db_migrations: BaseMigration = container.resolve(BaseMigration)
    # Resolving RouterRepository above already constructs this transitively
    # (RouterRepository -> RouterAdapter -> RoutingIntelligenceLayer), which
    # is what we want - it spawns the llama-server subprocess and blocks
    # until it's ready, here at startup rather than on some real user's
    # first "smart" request. This second resolve just returns that same
    # cached singleton, giving us a handle to shut it down cleanly below.
    routing_intelligence: RoutingIntelligenceLayer = container.resolve(RoutingIntelligenceLayer)

    await db_migrations.run_all()
    scheduler.start()
    await router_repository.warm_up_latency_rankings()

    yield

    routing_intelligence.shutdown()


app = FastAPI(lifespan=lifespan)
builder = Builder(app)
builder.build_and_initialize_app()

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=13000, reload=False)