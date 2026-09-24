"""Maps service errors to the shared error shape: {code, message, details}."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from katib.services.errors import KatibError


def _body(code: str, message: str, details: object = None) -> dict[str, object]:
    return {"code": code, "message": message, "details": details or {}}


def install(app: FastAPI) -> None:
    @app.exception_handler(KatibError)
    async def _katib_error(_: Request, err: KatibError) -> JSONResponse:
        return JSONResponse(_body(err.code, err.message, err.details), status_code=err.status)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, err: RequestValidationError) -> JSONResponse:
        first = err.errors()[0]
        where = ".".join(str(p) for p in first["loc"] if p != "body")
        message = f"{where}: {first['msg']}" if where else str(first["msg"])
        return JSONResponse(
            _body("invalid_input", message, {"errors": [str(e["msg"]) for e in err.errors()]}),
            status_code=422,
        )
