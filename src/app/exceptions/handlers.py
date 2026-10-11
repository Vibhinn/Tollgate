from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse
from .classes import ErrorSpec

def openai_error(status_code: int, message: str, error_type: str, code: str | None = None,
                 param: str | None = None, headers: dict[str, str] | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"message": message, "type": error_type, "param": param, "code": code}},
        headers=headers,
    )


# the error code a request ended with, for RequestMetricsMiddleware's event
ERROR_CODE_STATE_KEY = "error_code"


def status_handler(error_spec: ErrorSpec):
    async def handle(request, exc):
        setattr(request.state, ERROR_CODE_STATE_KEY, error_spec.code)
        return openai_error(error_spec.status_code, str(exc), error_spec.type, error_spec.code,
                            headers=getattr(exc, "headers", None))
    return handle


async def validation_error_handler(request, exc: RequestValidationError):
    error = exc.errors()[0]
    # loc starts with where the value came from ("body", "header", ...); OpenAI's param is just the name
    location = [str(part) for part in error.get("loc", ())[1:]]
    message = error.get("msg", "Invalid request").removeprefix("Value error, ")
    return openai_error(400, message, "invalid_request_error", param=".".join(location) or None)


async def http_error_handler(request, exc: HTTPException):
    return openai_error(exc.status_code, str(exc.detail), "invalid_request_error", headers=exc.headers) #type: ignore


async def unexpected_error_handler(request, exc: Exception):
    # A bug, not a known failure. The message stays generic because str(exc) can expose internals;
    # Starlette re-raises after this response, so the server still logs the full traceback
    return openai_error(500, "The gateway hit an internal error.", "server_error", "internal_error")
