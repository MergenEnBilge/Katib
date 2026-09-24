"""Run Alembic migrations from code so `katib` can bring an existing database up to date."""

from pathlib import Path

from alembic import command
from alembic.config import Config

_ROOT = Path(__file__).resolve().parent


def upgrade_to_head(url: str) -> None:
    cfg = Config()
    cfg.set_main_option("script_location", str(_ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(cfg, "head")
