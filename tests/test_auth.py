"""Unit-тесты bcrypt и JWT (store/auth.py)."""
import datetime as dt

import jwt
import pytest
from django.conf import settings

from store.auth import decode_token, get_api_user, hash_password, make_tokens, verify_password
from tests.helpers import jget


def test_hash_is_bcrypt_and_salted():
    h1, h2 = hash_password("Passw0rd!"), hash_password("Passw0rd!")
    assert h1.startswith("$2") and h1 != h2          # разная соль -> разные хэши
    assert "Passw0rd!" not in h1


def test_verify_password():
    h = hash_password("Passw0rd!")
    assert verify_password("Passw0rd!", h)
    assert not verify_password("passw0rd!", h)
    assert not verify_password("", h)
    assert not verify_password("Passw0rd!", "not-a-bcrypt-hash")   # битый хэш не вызывает исключение


def test_verify_unicode_password():
    h = hash_password("Пароль-123")
    assert verify_password("Пароль-123", h) and not verify_password("Пароль-124", h)


@pytest.mark.django_db
def test_tokens_roundtrip(user):
    tokens = make_tokens(user)
    payload = decode_token(tokens["access"], "access")
    assert payload["sub"] == str(user.id) and payload["role"] == "user" and payload["type"] == "access"
    assert decode_token(tokens["refresh"], "refresh")["type"] == "refresh"
    assert tokens["expires_in"] == int(settings.JWT_ACCESS_LIFETIME.total_seconds())


@pytest.mark.django_db
def test_token_type_is_checked(user):
    tokens = make_tokens(user)
    with pytest.raises(jwt.PyJWTError):
        decode_token(tokens["refresh"], "access")     # refresh нельзя использовать как access
    with pytest.raises(jwt.PyJWTError):
        decode_token(tokens["access"], "refresh")


@pytest.mark.django_db
def test_expired_and_tampered_tokens_rejected(user):
    past = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=1)
    expired = jwt.encode({"sub": str(user.id), "type": "access", "exp": past}, settings.JWT_SECRET, algorithm="HS256")
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_token(expired, "access")
    good = make_tokens(user)["access"]
    with pytest.raises(jwt.PyJWTError):
        decode_token(good[:-3] + ("AAA" if not good.endswith("AAA") else "BBB"), "access")
    forged = jwt.encode({"sub": str(user.id), "type": "access",
                         "exp": dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1)}, "wrong-secret", algorithm="HS256")
    with pytest.raises(jwt.InvalidSignatureError):
        decode_token(forged, "access")


@pytest.mark.django_db
def test_get_api_user(rf, user):
    request = rf.get("/", HTTP_AUTHORIZATION=f"Bearer {make_tokens(user)['access']}")
    assert get_api_user(request) == user
    assert get_api_user(rf.get("/")) is None
    assert get_api_user(rf.get("/", HTTP_AUTHORIZATION="Bearer garbage")) is None
    assert get_api_user(rf.get("/", HTTP_AUTHORIZATION="Basic abc")) is None


@pytest.mark.django_db
def test_jwt_required_blocks_anonymous(client):
    assert jget(client, "/api/profile").status_code == 401
    assert jget(client, "/api/actions").status_code == 401
