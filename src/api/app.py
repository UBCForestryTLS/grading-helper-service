from fastapi import FastAPI

from src.api.routes.health import router as health_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="Grading Helper Service",
        description="AI-powered grading assistant for UBC Forestry courses",
        version="0.1.0",
    )
    app.include_router(health_router)
    return app
