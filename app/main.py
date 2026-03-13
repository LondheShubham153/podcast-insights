from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter

from app.config import settings
from app.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    client = await Client.connect(
        settings.temporal_host,
        data_converter=pydantic_data_converter,
    )
    app.state.temporal_client = client
    app.state.task_queue = settings.task_queue
    print(f"API connected to Temporal at '{settings.temporal_host}'")
    yield


app = FastAPI(title="Durable Podcast Insights", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)

static_dir = Path(__file__).parent.parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def index():
    return FileResponse(str(static_dir / "index.html"))


@app.get("/health")
async def health():
    try:
        client = app.state.temporal_client
        await client.service_client.check_health()
        return {"status": "ok", "temporal": "connected"}
    except Exception:
        return {"status": "ok", "temporal": "disconnected"}
