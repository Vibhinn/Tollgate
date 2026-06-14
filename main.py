import uvicorn
from fastapi import FastAPI
from src.build import Builder

app = FastAPI()
builder = Builder(app)
builder.build_and_initialize_app()

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=13000)
