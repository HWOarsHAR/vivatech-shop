"""Настройки проекта: Django + БД + сессии + JWT + безопасность для публикации в Интернете.

Все чувствительные значения берутся из переменных окружения (см. .env.example).
Локально (DJANGO_DEBUG=1 по умолчанию) всё работает как раньше; main.py запускает
приложение в режиме DJANGO_DEBUG=0 (боевой режим).
"""
import os
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlparse

from .db_config import DB_SETTINGS

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name, default):
    value = os.environ.get(name)
    return default if value is None else value.strip().lower() in ("1", "true", "yes", "on")


def env_list(name):
    return [x.strip() for x in os.environ.get(name, "").split(",") if x.strip()]


DEBUG = env_bool("DJANGO_DEBUG", True)


def _secret_key():
    """Ключ из окружения. В боевом режиме он обязателен: без него сессии и JWT были бы небезопасны."""
    key = os.environ.get("DJANGO_SECRET_KEY")
    if key:
        return key
    if DEBUG:
        return "dev-insecure-key-change-me"
    raise RuntimeError("Не задана переменная окружения DJANGO_SECRET_KEY (обязательна при DJANGO_DEBUG=0)")


SECRET_KEY = _secret_key()

# Адрес сайта после публикации, например https://my-shop.example.app
SITE_URL = os.environ.get("SITE_URL", "").rstrip("/")
ALLOWED_HOSTS = ["*"] if DEBUG else (env_list("ALLOWED_HOSTS") or ["*"])
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS") + ([SITE_URL] if SITE_URL else [])

# django.contrib.auth/admin не подключаем: пользователи хранятся в собственной таблице `users`.
INSTALLED_APPS = [
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "store",
]

MIDDLEWARE = [
    "store.security.HealthAndHeadersMiddleware",       # /healthz и заголовки безопасности
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",      # раздача static без отдельного nginx
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "store.middleware.CurrentUserMiddleware",          # request.current_user из сессии
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.messages.context_processors.messages",
        "store.context.common",
    ]},
}]

DATABASES = {"default": DB_SETTINGS}

# --- Сессии хранятся в БД (таблица django_session) ---
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"

# --- JWT ---
JWT_SECRET = os.environ.get("JWT_SECRET", SECRET_KEY)
JWT_ALGORITHM = "HS256"
JWT_ACCESS_LIFETIME = timedelta(minutes=30)
JWT_REFRESH_LIFETIME = timedelta(days=7)

# --- HTTPS и безопасность (включается в боевом режиме) ---
FORCE_HTTPS = env_bool("FORCE_HTTPS", not DEBUG)
if FORCE_HTTPS:
    # хостинг завершает TLS на прокси и сообщает схему заголовком X-Forwarded-Proto
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 365
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_SSL_REDIRECT = env_bool("FORCE_SSL_REDIRECT", False)  # включайте, только если прокси шлёт X-Forwarded-Proto
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# Политика CSP. 'unsafe-inline' нужен из-за обработчиков onclick/onchange в шаблонах админ-панели.
CSP_POLICY = "; ".join([
    "default-src 'self'",
    "img-src 'self' data: https:",
    "style-src 'self' 'unsafe-inline'",
    "script-src 'self' 'unsafe-inline'",
    "connect-src 'self'",
    "font-src 'self' data:",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
])
PERMISSIONS_POLICY = "camera=(), microphone=(), geolocation=(), payment=(), usb=()"

LANGUAGE_CODE = "ru-ru"
TIME_ZONE = "Europe/Moscow"
USE_I18N = True
USE_TZ = True

# --- Статические файлы (WhiteNoise) ---
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}
WHITENOISE_USE_FINDERS = DEBUG
WHITENOISE_AUTOREFRESH = DEBUG

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": os.environ.get("LOG_LEVEL", "INFO")},
}
