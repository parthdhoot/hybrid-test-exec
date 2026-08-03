from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import db
from app.routers import promotions, runs, tests

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="Hybrid Test Execution", lifespan=lifespan)

app.include_router(tests.router)
app.include_router(runs.router)
app.include_router(promotions.router)

app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
