"""Хэширование паролей (bcrypt), JWT и декораторы защиты маршрутов."""
import datetime as dt
from functools import wraps

import bcrypt
import jwt
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import redirect

from .models import User, UserAction


# ---------- пароли ----------
def hash_password(password: str) -> str:
    """bcrypt с солью (gensalt) — пароль в открытом виде не хранится."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode())
    except ValueError:  # битый хэш / слишком длинный пароль
        return False


# ---------- JWT ----------
def _make_token(user: User, kind: str, lifetime: dt.timedelta) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    payload = {"sub": str(user.id), "role": user.role, "type": kind,
               "iat": now, "exp": now + lifetime}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def make_tokens(user: User) -> dict:
    """Пара токенов: короткоживущий access и долгоживущий refresh."""
    return {
        "access": _make_token(user, "access", settings.JWT_ACCESS_LIFETIME),
        "refresh": _make_token(user, "refresh", settings.JWT_REFRESH_LIFETIME),
        "expires_in": int(settings.JWT_ACCESS_LIFETIME.total_seconds()),
    }


def decode_token(token: str, kind: str) -> dict:
    """Проверяет подпись, срок жизни и тип токена. Бросает jwt.PyJWTError."""
    payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    if payload.get("type") != kind:
        raise jwt.InvalidTokenError("wrong token type")
    return payload


def get_api_user(request):
    """Пользователь из заголовка `Authorization: Bearer <access>` или None."""
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    try:
        payload = decode_token(header[7:], "access")
    except jwt.PyJWTError:
        return None
    return User.objects.filter(pk=payload["sub"]).first()


def jwt_required(view):
    """Декоратор для API: требует валидный JWT access-токен (иначе 401)."""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        user = get_api_user(request)
        if user is None:
            return JsonResponse({"error": "Не авторизован или токен истёк"}, status=401)
        request.api_user = user
        return view(request, *args, **kwargs)
    return wrapper


# ---------- защита HTML-страниц (по сессии) ----------
def login_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if request.current_user is None:
            return redirect(f"/login/?next={request.path}")
        return view(request, *args, **kwargs)
    return wrapper


def admin_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if request.current_user is None:
            return redirect(f"/login/?next={request.path}")
        if not request.current_user.is_admin:
            return redirect("/")
        return view(request, *args, **kwargs)
    return wrapper


# ---------- журнал действий (долгосрочное хранение, таблица user_actions) ----------
def log_action(user, action: str, page: str = ""):
    if user is not None:
        UserAction.objects.create(user=user, action=action, page=page[:255])
