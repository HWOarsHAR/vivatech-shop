"""Первичная настройка при запуске на сервере (вызывается из main.py после migrate).

1. Если в БД нет товаров — загружает каталог из fixtures/catalog.json,
   а при его отсутствии — демонстрационные данные (без демо-пользователей).
2. Если заданы ADMIN_EMAIL и ADMIN_PASSWORD — создаёт или обновляет администратора.
Команда идемпотентна: повторный запуск ничего не дублирует.
"""
import os
from pathlib import Path

from django.conf import settings
from django.core import serializers
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.core.management.color import no_style
from django.db import connection, transaction
from django.utils import timezone

from store.auth import hash_password
from store.models import Category, Manufacturer, Product, ProductImage, ProductProperty, User


class Command(BaseCommand):
    help = "Загрузка каталога и создание администратора из переменных окружения"

    def add_arguments(self, parser):
        parser.add_argument("--fixture", default=os.environ.get("CATALOG_FIXTURE", ""))

    def handle(self, *args, **opts):
        self._load_catalog(opts["fixture"])
        self._ensure_admin()

    def _load_catalog(self, fixture):
        if Product.objects.exists():
            self.stdout.write("Каталог уже заполнен — загрузка пропущена")
            return
        path = Path(fixture) if fixture else Path(settings.BASE_DIR) / "fixtures" / "catalog.json"
        if not path.exists():
            call_command("seed", no_users=True)
            return
        text = path.read_text(encoding="utf-8")
        with transaction.atomic():
            count = 0
            for obj in serializers.deserialize("json", text):
                obj.save()
                count += 1
        # после вставки строк с явными id сдвигаем счётчики PostgreSQL (в SQLite список пуст)
        models = [Manufacturer, Category, Product, Product.categories.through, ProductProperty, ProductImage]
        with connection.cursor() as cur:
            for sql in connection.ops.sequence_reset_sql(no_style(), models):
                cur.execute(sql)
        self.stdout.write(self.style.SUCCESS(f"Каталог загружен из {path.name}: {count} объектов"))

    def _ensure_admin(self):
        email = os.environ.get("ADMIN_EMAIL", "").strip().lower()
        password = os.environ.get("ADMIN_PASSWORD", "")
        if not email or not password:
            self.stdout.write("ADMIN_EMAIL / ADMIN_PASSWORD не заданы — администратор не создан")
            return
        if len(password) < 8 or len(password.encode("utf-8")) > 72:
            raise CommandError("ADMIN_PASSWORD: от 8 символов, не длиннее 72 байт")
        user = User.objects.filter(email=email).first()
        if user is None:
            User.objects.create(name="Администратор", email=email, role="admin",
                                password_hash=hash_password(password), consent_at=timezone.now())
            self.stdout.write(self.style.SUCCESS(f"Администратор {email} создан"))
        else:
            user.role, user.password_hash = "admin", hash_password(password)
            user.save(update_fields=["role", "password_hash"])
            self.stdout.write(self.style.SUCCESS(f"Администратор {email} обновлён"))
