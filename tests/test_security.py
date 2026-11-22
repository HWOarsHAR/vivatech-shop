"""Тесты безопасности (раздел «Тестирование безопасности»): заголовки, JWT, SQL-инъекции, хранение паролей."""
import datetime as dt

import jwt
import pytest
from django.conf import settings

from store.models import Product, User
from tests.helpers import jget, jpost, reg_payload

pytestmark = pytest.mark.django_db


class TestHeaders:
    def test_security_headers_on_html(self, client):
        r = client.get("/")
        csp = r["Content-Security-Policy"]
        assert "frame-ancestors 'none'" in csp and "object-src 'none'" in csp and "default-src 'self'" in csp
        assert r["X-Frame-Options"] == "DENY"
        assert r["X-Content-Type-Options"] == "nosniff"
        assert r["Referrer-Policy"] == "same-origin"
        assert "camera=()" in r["Permissions-Policy"]

    def test_api_and_private_pages_are_not_cached(self, client):
        for path in ("/api/search?q=ab", "/cart/", "/profile/"):
            assert client.get(path)["Cache-Control"] == "no-store"

    def test_session_cookie_flags(self, client, user):
        jpost(client, "/api/login", {"login": user.email, "password": "Passw0rd!"})
        cookie = client.cookies["sessionid"]
        assert cookie["httponly"] and cookie["samesite"] == "Lax"


class TestHealth:
    def test_healthz(self, client):
        r = client.get("/healthz")
        assert r.status_code == 200 and r.json() == {"status": "ok"}

    def test_healthz_with_db(self, client):
        assert client.get("/healthz?db=1").json() == {"status": "ok", "db": "ok"}


class TestProductionSettings:
    def _reload(self, monkeypatch, **env):
        import importlib
        import config.settings as s
        for key in ("DJANGO_DEBUG", "FORCE_HTTPS", "SITE_URL", "ALLOWED_HOSTS", "CSRF_TRUSTED_ORIGINS"):
            monkeypatch.delenv(key, raising=False)
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        return importlib.reload(s)

    def test_https_hardening_in_production(self, monkeypatch):
        s = self._reload(monkeypatch, DJANGO_DEBUG="0", SITE_URL="https://shop.example.app/")
        assert s.DEBUG is False and s.FORCE_HTTPS is True
        assert s.SESSION_COOKIE_SECURE and s.CSRF_COOKIE_SECURE
        assert s.SECURE_HSTS_SECONDS >= 31536000
        assert s.SECURE_PROXY_SSL_HEADER == ("HTTP_X_FORWARDED_PROTO", "https")
        assert s.CSRF_TRUSTED_ORIGINS == ["https://shop.example.app"]

    def test_debug_defaults_for_local_development(self, monkeypatch):
        s = self._reload(monkeypatch)
        assert s.DEBUG is True and s.FORCE_HTTPS is False and s.ALLOWED_HOSTS == ["*"]

    def test_secret_key_is_required_in_production(self, monkeypatch):
        import importlib
        import config.settings as s
        monkeypatch.setenv("DJANGO_DEBUG", "0")
        monkeypatch.delenv("DJANGO_SECRET_KEY")
        with pytest.raises(RuntimeError):
            importlib.reload(s)
        monkeypatch.setenv("DJANGO_SECRET_KEY", "x" * 50)
        importlib.reload(s)                                         # вернуть модуль в рабочее состояние

    def test_allowed_hosts_from_env(self, monkeypatch):
        s = self._reload(monkeypatch, DJANGO_DEBUG="0", ALLOWED_HOSTS="a.example.ru, b.example.ru")
        assert s.ALLOWED_HOSTS == ["a.example.ru", "b.example.ru"]


class TestInjectionAndAuth:
    @pytest.mark.parametrize("payload", ["' OR '1'='1", "'; DROP TABLE users;--", "%%", "__", "\\\\", "\" OR \"\"=\"",
                                         "1; SELECT * FROM users", "<script>alert(1)</script>"])
    def test_search_survives_injection_payloads(self, client, product, payload):
        r = client.get("/api/search", {"q": payload})
        assert r.status_code == 200 and r.json()["count"] == 0
        assert Product.objects.count() == 1 and User.objects.count() == 0

    def test_login_with_sql_payload(self, client, user):
        r = jpost(client, "/api/login", {"login": "' OR 1=1 --", "password": "' OR 1=1 --"})
        assert r.status_code == 401

    def test_passwords_are_never_stored_in_plaintext(self, client):
        jpost(client, "/api/register", reg_payload(password="Secret123!", confirm_password="Secret123!"))
        stored = User.objects.get().password_hash
        assert "Secret123!" not in stored and stored.startswith("$2")

    def test_api_never_returns_password_hash(self, client, user, token):
        assert "password" not in jget(client, "/api/profile", token).content.decode().lower()

    def test_forged_jwt_variants_are_rejected(self, client, user):
        exp = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1)
        claims = {"sub": str(user.id), "type": "access", "exp": exp}
        variants = {
            "alg_none": jwt.encode(claims, None, algorithm="none"),
            "wrong_secret": jwt.encode(claims, "wrong", algorithm="HS256"),
            "expired": jwt.encode({**claims, "exp": exp - dt.timedelta(hours=2)}, settings.JWT_SECRET, algorithm="HS256"),
            "refresh_type": jwt.encode({**claims, "type": "refresh"}, settings.JWT_SECRET, algorithm="HS256"),
            "unknown_user": jwt.encode({**claims, "sub": "999999"}, settings.JWT_SECRET, algorithm="HS256"),
        }
        for name, tok in variants.items():
            assert jget(client, "/api/profile", tok).status_code == 401, name
        good = jwt.encode(claims, settings.JWT_SECRET, algorithm="HS256")
        assert jget(client, "/api/profile", good).status_code == 200

    def test_user_cannot_read_foreign_data(self, client, user, other_user):
        from store.models import Feedback
        Feedback.objects.create(user=other_user, subject="Чужое", message="Чужое сообщение 123")
        from store.auth import make_tokens
        mine = jget(client, "/api/feedback", make_tokens(user)["access"]).json()["results"]
        assert mine == []
