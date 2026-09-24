"""Health endpoint. Reports whether the server can reach its database."""

from importlib.metadata import version

from fastapi import APIRouter, Request
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

router = APIRouter()


class Health(BaseModel):
    status: str
    version: str
    database: str


@router.get("/health", response_model=Health)
def health(request: Request) -> Health:
    try:
        with request.app.state.engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        database = "ok"
    except SQLAlchemyError:
        database = "unreachable"
    return Health(
        status="ok" if database == "ok" else "degraded",
        version=version("katib"),
        database=database,
    )
