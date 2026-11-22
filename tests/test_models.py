"""Тесты базы данных: ограничения, каскады, связи (Задание 1)."""
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction

from store.models import (CartItem, Category, Feedback, Manufacturer, Order, OrderItem, Product, User, UserAction)

pytestmark = pytest.mark.django_db


def test_price_check_constraint():
    with pytest.raises(IntegrityError), transaction.atomic():
        Product.objects.create(name="Минус", alias="minus", price=Decimal("-1"))


def test_alias_is_unique(product):
    with pytest.raises(IntegrityError), transaction.atomic():
        Product.objects.create(name="Дубль", alias=product.alias, price=Decimal("1"))


def test_feedback_rating_check(user):
    with pytest.raises(IntegrityError), transaction.atomic():
        Feedback.objects.create(user=user, subject="Тема", message="Сообщение 12345", rating=9)
    Feedback.objects.create(user=user, subject="Тема", message="Сообщение 12345", rating=5)
    Feedback.objects.create(user=user, subject="Тема", message="Сообщение 12345", rating=None)


def test_user_needs_email_or_phone():
    with pytest.raises(IntegrityError), transaction.atomic():
        User.objects.create(name="Никто", password_hash="x")


def test_user_email_and_phone_unique(user):
    with pytest.raises(IntegrityError), transaction.atomic():
        User.objects.create(name="Копия", email=user.email, password_hash="x")
    User.objects.create(name="А", phone="+79990000001", password_hash="x")
    with pytest.raises(IntegrityError), transaction.atomic():
        User.objects.create(name="Б", phone="+79990000001", password_hash="x")


def test_several_users_without_email_are_allowed():
    User.objects.create(name="А", phone="+79990000001", password_hash="x")
    User.objects.create(name="Б", phone="+79990000002", password_hash="x")   # NULL не нарушает UNIQUE
    assert User.objects.filter(email__isnull=True).count() == 2


def test_cart_pair_is_unique(user, product):
    CartItem.objects.create(user=user, product=product, quantity=1)
    with pytest.raises(IntegrityError), transaction.atomic():
        CartItem.objects.create(user=user, product=product, quantity=2)


def test_deleting_user_cascades(user, product):
    Feedback.objects.create(user=user, subject="Тема", message="Сообщение 12345")
    CartItem.objects.create(user=user, product=product, quantity=1)
    UserAction.objects.create(user=user, action="login")
    user.delete()
    assert not Feedback.objects.exists() and not CartItem.objects.exists() and not UserAction.objects.exists()
    assert Product.objects.filter(pk=product.pk).exists()            # товары остаются


def test_deleting_manufacturer_keeps_products():
    m = Manufacturer.objects.create(name="Acme")
    p = Product.objects.create(name="Товар", alias="t", price=Decimal("1"), manufacturer=m)
    m.delete()
    p.refresh_from_db()
    assert p.manufacturer is None


def test_order_history_survives_product_deletion(user, product):
    order = Order.objects.create(user=user, total=Decimal("1999.00"))
    OrderItem.objects.create(order=order, product=product, name=product.name, price=product.price, quantity=1)
    product.delete()
    item = OrderItem.objects.get()
    assert item.product is None and item.name == "Смартфон Тест" and item.price == Decimal("1999.00")


def test_product_categories_many_to_many(product):
    c1, c2 = Category.objects.create(name="А", alias="a"), Category.objects.create(name="Б", alias="b")
    product.categories.add(c1, c2)
    assert set(product.categories.values_list("alias", flat=True)) == {"a", "b"}
    assert c1.products.get() == product


def test_image_url_placeholder_and_custom(product):
    assert product.image_url.endswith("img/placeholder.svg")
    product.image = "/static/img/phone.jpg"
    assert product.image_url == "/static/img/phone.jpg"
