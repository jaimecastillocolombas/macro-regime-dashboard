"""Runtime configuration. The series catalogue will live here too (added with each source)."""

import os

from dotenv import load_dotenv

load_dotenv()

DEFAULT_DATABASE_URL = "sqlite:///data/macro.db"


def database_url() -> str:
    """Database URL from the environment; SQLite file by default."""
    return os.getenv("DATABASE_URL") or DEFAULT_DATABASE_URL
