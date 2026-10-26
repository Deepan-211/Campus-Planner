"""
Main FastAPI Application Entrypoint for CampusRide Planner.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api.routes import router
from backend.api.auth_routes import auth_router, seed_default_users
from backend.db.session import init_db, SessionLocal

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ensure database tables and demo seed users exist."""
    init_db()
    with SessionLocal() as db:
        seed_default_users(db)
    yield

app = FastAPI(
    title="CampusRide Planner API",
    description="Digital Twin and Optimization Platform for Campus Micromobility",
    version="0.2.0",
    lifespan=lifespan
)

# Enable CORS for Next.js frontend (default port 3000) and local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(router)


@app.get("/health", tags=["Health"])
def health_check():
    """Service health and readiness check."""
    return {
        "status": "healthy",
        "service": "CampusRide Planner",
        "campus": "UC Berkeley",
        "version": "0.1.0"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.api.main:app", host="0.0.0.0", port=8000, reload=True)
