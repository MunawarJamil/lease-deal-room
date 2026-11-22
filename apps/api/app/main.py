import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import health
from app.core.config import get_settings
from app.core.exceptions import LeaseDealRoomError
from app.core.logging import setup_logging

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings.log_level)

    app = FastAPI(title=settings.app_name, version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(LeaseDealRoomError)
    async def app_error_handler(request: Request, exc: LeaseDealRoomError) -> JSONResponse:
        logger.warning("Handled error [%s] on %s: %s", exc.code, request.url.path, exc.message)
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "detail": exc.message},
        )

    app.include_router(health.router)
    return app


app = create_app()