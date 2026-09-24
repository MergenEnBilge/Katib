"""Import string target for uvicorn's reload mode."""

from fastapi import FastAPI

from katib.api.app import create_app
from katib.config import get_settings


def build_app() -> FastAPI:
    return create_app(get_settings())
