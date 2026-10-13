import uvicorn
from fastapi import FastAPI
from build import Builder, ApplicationLifespan


app = FastAPI(lifespan=ApplicationLifespan.lifespan)
builder = Builder(app)
builder.build_and_initialize_app()

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=13000, reload=False, timeout_graceful_shutdown=5)