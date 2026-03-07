from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import auth, goals, tasks, plans
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(title="Orchestruct API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(goals.router, prefix="/api/v1")
app.include_router(tasks.router, prefix="/api/v1")
app.include_router(plans.router, prefix="/api/v1")


@app.get("/health")
def health():
    return {"status": "ok"}
