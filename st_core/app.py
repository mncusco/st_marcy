from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import os

from database import engine, Base, SessionLocal
from routes import leads, dashboard, health, download

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        from services.editorial_service import seed_editorials
        seed_editorials(db)
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()
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
