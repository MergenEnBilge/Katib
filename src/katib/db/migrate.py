"""Run Alembic migrations from code so `katib` can bring an existing database up to date."""

from pathlib import Path

from alembic import command
from alembic.config import Config

from katib.db.session import normalize_url

_ROOT = Path(__file__).resolve().parent


def upgrade_to_head(url: str) -> None:
    cfg = Config()
    cfg.set_main_option("script_location", str(_ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", normalize_url(url).replace("%", "%%"))
    command.upgrade(cfg, "head")
