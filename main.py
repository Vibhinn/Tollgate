from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from src.build import Builder
from src.app.injector import container
from src.jobs import RedisStreamRepository

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = container.resolve(RedisStreamRepository)
    scheduler.start()
    yield


app = FastAPI(lifespan=lifespan)
builder = Builder(app)
builder.build_and_initialize_app()

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=13000, reload=True)
