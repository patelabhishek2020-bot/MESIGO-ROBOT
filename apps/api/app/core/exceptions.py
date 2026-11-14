"""Application exceptions and FastAPI handlers."""

from typing import Any, Optional

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger

logger = get_logger("errors")


class MesigoError(Exception):
    def __init__(self, message: str, code: str = "mesigo_error", status_code: int = 400):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)


class UnauthorizedError(MesigoError):
    def __init__(self, message: str = "Unauthorized"):
        super().__init__(message, code="unauthorized", status_code=401)


class ForbiddenError(MesigoError):
    def __init__(self, message: str = "Forbidden"):
        super().__init__(message, code="forbidden", status_code=403)


class NotFoundError(MesigoError):
    def __init__(self, message: str = "Not found"):
        super().__init__(message, code="not_found", status_code=404)


def _error_body(
    *,
    code: str,
    message: str,
    details: Optional[Any] = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {"error": {"code": code, "message": message}}
    if details is not None:
        body["error"]["details"] = details
    return body


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(MesigoError)
    async def mesigo_error_handler(_: Request, exc: MesigoError):
        logger.warning("mesigo_error", code=exc.code, message=exc.message)
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(code=exc.code, message=exc.message),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(_: Request, exc: StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(code="http_error", message=str(exc.detail)),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content=_error_body(
                code="validation_error",
                message="Request validation failed",
                details=exc.errors(),
            ),
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(_: Request, exc: Exception):
        logger.exception("unhandled_error", error=str(exc))
        return JSONResponse(
            status_code=500,
            content=_error_body(code="internal_error", message="Internal server error"),
        )
