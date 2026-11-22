"""Конфигурация подключения к БД (Задания 2 и 4): PostgreSQL или SQLite, выбор по окружению.

Порядок выбора (функция choose_engine):
  1. DB_ENGINE=sqlite | postgres — явное указание;
  2. задан DATABASE_URL или любая из DB_HOST / DB_NAME / DB_USER / DB_PASSWORD -> PostgreSQL;
  3. иначе -> PostgreSQL с параметрами по умолчанию из задания (локальная разработка).
SQLite включается ТОЛЬКО явно (DB_ENGINE=sqlite): файловая система контейнера временная,
молчаливый откат на SQLite привёл бы к потере данных при каждом обновлении приложения.
"""
import os
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

BASE_DIR = Path(__file__).resolve().parent.parent


def data_dir(env=None) -> Path:
    """Постоянная папка для SQLite и секретного ключа: DATA_DIR, /data (хостинг) или ./data."""
    env = os.environ if env is None else env
    if env.get("DATA_DIR"):
        return Path(env["DATA_DIR"])
    d = Path("/data")
    if os.name != "nt" and d.is_dir() and os.access(d, os.W_OK):
        return d
    return BASE_DIR / "data"


def choose_engine(env=None) -> str:
    env = os.environ if env is None else env
    explicit = env.get("DB_ENGINE", "").strip().lower()
    if explicit in ("sqlite", "sqlite3"):
        return "sqlite"
    if explicit in ("postgres", "postgresql"):
        return "postgres"
    if env.get("DATABASE_URL") or any(env.get(k) for k in ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD")):
        return "postgres"
    return "postgres"


def parse_database_url(url: str) -> dict:
    """postgres://user:pass@host:5432/dbname?sslmode=require -> словарь для Django."""
    u = urlparse(url)
    if u.scheme not in ("postgres", "postgresql"):
        raise ValueError("DATABASE_URL должен начинаться с postgres:// или postgresql://")
    cfg = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": unquote(u.path.lstrip("/")),
        "USER": unquote(u.username or ""),
        "PASSWORD": unquote(u.password or ""),
        "HOST": u.hostname or "localhost",
        "PORT": str(u.port or 5432),
        "CONN_MAX_AGE": 60,
        "OPTIONS": {"connect_timeout": 5},
    }
    sslmode = parse_qs(u.query).get("sslmode")
    if sslmode:
        cfg["OPTIONS"]["sslmode"] = sslmode[0]
    return cfg


def build_db_settings(env=None) -> dict:
    env = os.environ if env is None else env
    if choose_engine(env) == "sqlite":
        folder = data_dir(env)
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        return {"ENGINE": "django.db.backends.sqlite3", "NAME": str(folder / "db.sqlite3"),
                "OPTIONS": {"timeout": 20}}
    if env.get("DATABASE_URL"):
        return parse_database_url(env["DATABASE_URL"])
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env.get("DB_NAME", "products_db"),
        "USER": env.get("DB_USER", "user"),
        "PASSWORD": env.get("DB_PASSWORD", "password"),
        "HOST": env.get("DB_HOST", "localhost"),
        "PORT": env.get("DB_PORT", "5432"),
        "CONN_MAX_AGE": 60,                 # переиспользование соединений
        "OPTIONS": {"connect_timeout": 5},  # не висим вечно, если сервер БД недоступен
    }


DB_SETTINGS = build_db_settings()


def check_connection():
    """Проверка соединения с БД. Возвращает (ok: bool, сообщение: str)."""
    from django.db import connection
    from django.db.utils import Error, OperationalError

    try:
        with connection.cursor() as cur:
            if connection.vendor == "sqlite":
                cur.execute("SELECT sqlite_version()")
                version = "SQLite " + cur.fetchone()[0]
            else:
                cur.execute("SELECT version()")
                version = cur.fetchone()[0]
        return True, f"Подключение к «{DB_SETTINGS['NAME']}» успешно. {version}"
    except OperationalError as exc:  # сервер недоступен, неверный пароль, нет БД
        return False, f"Не удалось подключиться к БД: {str(exc).strip()}"
    except Error as exc:             # прочие ошибки драйвера
        return False, f"Ошибка БД: {str(exc).strip()}"
