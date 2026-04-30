from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import settings

app = FastAPI(title=settings.app_name, version="0.1.0")

_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
_use_wildcard = not _origins or any(o == "*" for o in _origins)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if _use_wildcard else _origins,
    allow_credentials=not _use_wildcard,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")


@app.get("/")
async def root():
    return {"service": settings.app_name, "docs": "/docs"}
