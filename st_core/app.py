from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import os

from database import engine, Base
from routes import leads, dashboard, health, download

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield

app = FastAPI(
    title="ST CORE",
    description="Shamanic Travels Backend Core",
    version="1.0.0",
    lifespan=lifespan
)

if not os.path.exists("static"):
    os.makedirs("static")
app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(health.router)
app.include_router(leads.router)
app.include_router(dashboard.router)
app.include_router(download.router)
