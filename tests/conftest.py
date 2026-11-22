from decimal import Decimal

import bcrypt
import pytest

from store.auth import hash_password, make_tokens
from store.models import Product, User

_real_gensalt = bcrypt.gensalt


@pytest.fixture(autouse=True)
def fast_bcrypt(monkeypatch):
    """В тестах bcrypt считается с минимальной стоимостью (4 раунда) — набор тестов идёт быстрее."""
    monkeypatch.setattr(bcrypt, "gensalt", lambda rounds=12, prefix=b"2b": _real_gensalt(rounds=4, prefix=prefix))


@pytest.fixture
def user(db):
    return User.objects.create(name="Тест Пользователь", email="user@example.com",
                               password_hash=hash_password("Passw0rd!"))


@pytest.fixture
def other_user(db):
    return User.objects.create(name="Другой", email="other@example.com", password_hash=hash_password("Passw0rd!"))


@pytest.fixture
def admin(db):
    return User.objects.create(name="Админ", email="admin@example.com", role="admin",
                               password_hash=hash_password("Passw0rd!"))


@pytest.fixture
def product(db):
    return Product.objects.create(name="Смартфон Тест", alias="test-phone", short_description="6.5 AMOLED",
                                  description="Подробное описание тестового смартфона", price=Decimal("1999.00"))


@pytest.fixture
def token(user):
    return make_tokens(user)["access"]
