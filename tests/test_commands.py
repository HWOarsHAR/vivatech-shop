"""Тесты команд управления, конфигурации БД и развёртывания."""
import os
from decimal import Decimal

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from config import db_config
from store import sqlite_compat
from store.auth import verify_password
from store.models import Category, Manufacturer, Product, ProductImage, ProductProperty, User


# ---------- конфигурация БД (чистые функции, база не нужна) ----------
class TestDbConfig:
    def test_engine_choice(self):
        assert db_config.choose_engine({"DB_ENGINE": "sqlite"}) == "sqlite"
        assert db_config.choose_engine({"DB_ENGINE": "postgres", "PORT": "8080"}) == "postgres"
        assert db_config.choose_engine({"DATABASE_URL": "postgres://u:p@h/db"}) == "postgres"
        assert db_config.choose_engine({"DB_HOST": "db.local"}) == "postgres"
        assert db_config.choose_engine({"PORT": "8080"}) == "postgres"     # SQLite только по явному DB_ENGINE
        assert db_config.choose_engine({}) == "postgres"                   # локальная разработка

    def test_parse_database_url(self):
        cfg = db_config.parse_database_url("postgres://shop:p%40ss@db.example.com:6543/mydb?sslmode=require")
        assert cfg["NAME"] == "mydb" and cfg["USER"] == "shop" and cfg["PASSWORD"] == "p@ss"
        assert cfg["HOST"] == "db.example.com" and cfg["PORT"] == "6543"
        assert cfg["OPTIONS"]["sslmode"] == "require"
        with pytest.raises(ValueError):
            db_config.parse_database_url("mysql://u:p@h/db")

    def test_sqlite_settings_use_data_dir(self, tmp_path):
        cfg = db_config.build_db_settings({"DB_ENGINE": "sqlite", "DATA_DIR": str(tmp_path)})
        assert cfg["ENGINE"].endswith("sqlite3") and cfg["NAME"] == str(tmp_path / "db.sqlite3")

    def test_default_postgres_settings_match_lab(self):
        cfg = db_config.build_db_settings({})
        assert (cfg["NAME"], cfg["USER"], cfg["PASSWORD"], cfg["HOST"], cfg["PORT"]) == (
            "products_db", "user", "password", "localhost", "5432")
        assert cfg["OPTIONS"]["connect_timeout"] == 5

    @pytest.mark.django_db
    def test_check_connection_and_command(self, capsys):
        ok, message = db_config.check_connection()
        assert ok and "успешно" in message
        call_command("check_db")
        assert "успешно" in capsys.readouterr().out


class TestSqliteLike:
    @pytest.mark.parametrize("pattern, value, expected", [
        ("%смартфон%", "Смартфон Nova", 1), ("%СМАРТФОН%", "смартфон", 1), ("%nova%", "NOVA X1", 1),
        ("%ноутбук%", "Смартфон", 0), ("100\\%", "100%", 1), ("100\\%", "1000", 0), ("а_в", "авв", 1),
    ])
    def test_unicode_like(self, pattern, value, expected):
        assert sqlite_compat.unicode_like(pattern, value, "\\") == expected

    def test_null_handling(self):
        assert sqlite_compat.unicode_like(None, "x") is None and sqlite_compat.unicode_like("x", None) is None

    @pytest.mark.django_db
    def test_cyrillic_search_through_orm(self, product):
        for q in ("смартфон", "СМАРТФОН", "СмАрТфОн"):
            assert Product.objects.filter(name__icontains=q).count() == 1


# ---------- команды seed / bootstrap / export ----------
@pytest.mark.django_db
class TestCommands:
    def test_seed_is_idempotent_and_can_skip_users(self):
        call_command("seed", no_users=True)
        first = Product.objects.count()
        assert first == 8 and User.objects.count() == 0
        call_command("seed", no_users=True)
        assert Product.objects.count() == first

    def test_bootstrap_creates_admin_from_env(self, monkeypatch):
        monkeypatch.setenv("ADMIN_EMAIL", "Boss@Example.com")
        monkeypatch.setenv("ADMIN_PASSWORD", "Str0ng-Password")
        call_command("bootstrap")
        admin = User.objects.get(email="boss@example.com")
        assert admin.role == "admin" and verify_password("Str0ng-Password", admin.password_hash)
        monkeypatch.setenv("ADMIN_PASSWORD", "Another-Pass1")          # повторный запуск обновляет пароль
        call_command("bootstrap")
        admin.refresh_from_db()
        assert User.objects.filter(role="admin").count() == 1 and verify_password("Another-Pass1", admin.password_hash)

    def test_bootstrap_rejects_weak_admin_password(self, monkeypatch):
        monkeypatch.setenv("ADMIN_EMAIL", "boss@example.com")
        monkeypatch.setenv("ADMIN_PASSWORD", "short")
        with pytest.raises(CommandError):
            call_command("bootstrap")

    def test_bootstrap_without_admin_env_creates_no_users(self, monkeypatch):
        monkeypatch.delenv("ADMIN_EMAIL", raising=False)
        monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
        call_command("bootstrap")
        assert User.objects.count() == 0 and Product.objects.exists()

    def test_export_then_bootstrap_roundtrip(self, tmp_path):
        m = Manufacturer.objects.create(name="Acme")
        c = Category.objects.create(name="Гаджеты", alias="gadgets")
        p = Product.objects.create(name="Устройство «Ё»", alias="device", price=Decimal("1234.50"), manufacturer=m)
        p.categories.add(c)
        ProductProperty.objects.create(product=p, property_name="Цвет", property_value="Красный")
        ProductImage.objects.create(product=p, image="/static/img/x.jpg", title="Фото")
        out = tmp_path / "catalog.json"
        call_command("export_catalog", output=str(out))
        assert "Устройство «Ё»" in out.read_text(encoding="utf-8")        # кириллица записана как UTF-8
        Product.objects.all().delete(); Category.objects.all().delete(); Manufacturer.objects.all().delete()
        call_command("bootstrap", fixture=str(out))
        restored = Product.objects.get(alias="device")
        assert restored.price == Decimal("1234.50") and restored.manufacturer.name == "Acme"
        assert restored.categories.get().alias == "gadgets"
        assert restored.properties.get().property_value == "Красный" and restored.images.count() == 1
        call_command("bootstrap", fixture=str(out))                       # повторный запуск ничего не дублирует
        assert Product.objects.count() == 1
