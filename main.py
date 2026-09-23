from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from build import Builder
from src.app.injector import container
from src.jobs import RedisStreamRepository
from src.app.migrations import BaseMigration

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = container.resolve(RedisStreamRepository)
    db_migrations = container.resolve(BaseMigration)

    await db_migrations.run_all()
    scheduler.start()

    yield


app = FastAPI(lifespan=lifespan)
builder = Builder(app)
builder.build_and_initialize_app()

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=13000, reload=False)