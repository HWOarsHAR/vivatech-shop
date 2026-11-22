"""Настройки для автотестов (pytest): SQLite во временной папке, боевой режим без HTTPS."""
import os
import tempfile

os.environ["DB_ENGINE"] = "sqlite"
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="shop-test-")
os.environ["DJANGO_DEBUG"] = "0"
os.environ["FORCE_HTTPS"] = "0"
os.environ["DJANGO_SECRET_KEY"] = "test-secret-key-only-for-pytest-0123456789-abcdef"

from .settings import *  # noqa: E402,F401,F403

ALLOWED_HOSTS = ["testserver", "localhost"]
LOGGING = {"version": 1, "disable_existing_loggers": True, "handlers": {"null": {"class": "logging.NullHandler"}},
           "root": {"handlers": ["null"], "level": "CRITICAL"}}
