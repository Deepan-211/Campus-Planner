"""
Main FastAPI Application Entrypoint for CampusRide Planner.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api.routes import router

app = FastAPI(
    title="CampusRide Planner API",
    description="Digital Twin and Optimization Platform for Campus Micromobility (UC Berkeley)",
    version="0.1.0"
)

# Enable CORS for Next.js frontend (default port 3000) and local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
