"""Функциональные тесты API (Задания 3-6): регистрация, вход, профиль, отзывы, поиск, корзина, заказы."""
from decimal import Decimal

import pytest

from store.auth import make_tokens
from store.models import (CartItem, Feedback, Order, OrderItem, Product, User, UserAction, UserSession)
from tests.helpers import jget, jpost, jput, reg_payload

pytestmark = pytest.mark.django_db


# ---------------- регистрация ----------------
class TestRegister:
    def test_ok_by_email(self, client):
        r = jpost(client, "/api/register", reg_payload())
        assert r.status_code == 201
        u = User.objects.get(email="ivan@example.com")
        assert u.password_hash.startswith("$2") and u.password_hash != "Passw0rd!"
        assert u.consent_at is not None and u.ads_consent_at is None and u.role == "user"
        assert UserAction.objects.filter(user=u, action="register").exists()

    def test_ads_consent_is_stored_separately(self, client):
        jpost(client, "/api/register", reg_payload(ads=True))
        assert User.objects.get().ads_consent_at is not None

    def test_ok_by_phone_only(self, client):
        r = jpost(client, "/api/register", reg_payload(email="", phone="8 (999) 123-45-67"))
        assert r.status_code == 201
        u = User.objects.get()
        assert u.phone == "+79991234567" and u.email is None

    def test_duplicate_email_rejected(self, client, user):
        r = jpost(client, "/api/register", reg_payload(email=user.email))
        assert r.status_code == 400 and "email" in r.json()["errors"]

    def test_invalid_payloads(self, client):
        for bad in (reg_payload(consent=False), reg_payload(terms=False), reg_payload(email="", phone=""),
                    reg_payload(password="short", confirm_password="short"), reg_payload(email="bad")):
            assert jpost(client, "/api/register", bad).status_code == 400
        assert User.objects.count() == 0

    def test_broken_json_and_wrong_method(self, client):
        r = client.post("/api/register", data="{not json", content_type="application/json")
        assert r.status_code == 400
        assert client.get("/api/register").status_code == 405


# ---------------- вход / выход ----------------
class TestLogin:
    def test_login_by_email_creates_session_and_tokens(self, client, user):
        r = jpost(client, "/api/login", {"login": user.email, "password": "Passw0rd!"})
        assert r.status_code == 200
        body = r.json()
        assert body["access"] and body["refresh"] and body["user"]["email"] == user.email
        assert "password_hash" not in body["user"]
        assert client.session["user_id"] == user.id
        assert UserSession.objects.filter(user=user).count() == 1
        assert UserAction.objects.filter(user=user, action="login").exists()
        user.refresh_from_db()
        assert user.last_login is not None

    def test_login_by_phone_in_any_format(self, client):
        jpost(client, "/api/register", reg_payload(email="", phone="+7 999 123 45 67"))
        for variant in ("+79991234567", "8 (999) 123-45-67", "89991234567"):
            c = client.__class__()
            assert jpost(c, "/api/login", {"login": variant, "password": "Passw0rd!"}).status_code == 200

    def test_wrong_password_and_unknown_user_look_identical(self, client, user):
        wrong = jpost(client, "/api/login", {"login": user.email, "password": "Wrong1234!"})
        unknown = jpost(client, "/api/login", {"login": "nobody@example.com", "password": "Wrong1234!"})
        assert wrong.status_code == unknown.status_code == 401
        assert wrong.json() == unknown.json()                 # нельзя узнать, существует ли аккаунт
        assert "user_id" not in client.session

    def test_empty_fields(self, client):
        assert jpost(client, "/api/login", {"login": "", "password": ""}).status_code == 400

    def test_refresh_token(self, client, user):
        tokens = make_tokens(user)
        ok = jpost(client, "/api/token/refresh", {"refresh": tokens["refresh"]})
        assert ok.status_code == 200 and ok.json()["access"]
        assert jpost(client, "/api/token/refresh", {"refresh": tokens["access"]}).status_code == 401
        assert jpost(client, "/api/token/refresh", {"refresh": "garbage"}).status_code == 401

    def test_logout_destroys_session(self, client, user):
        jpost(client, "/api/login", {"login": user.email, "password": "Passw0rd!"})
        assert client.get("/profile/").status_code == 200
        assert jpost(client, "/api/logout").status_code == 200
        r = client.get("/profile/")
        assert r.status_code == 302 and r["Location"].startswith("/login/")
        assert UserSession.objects.count() == 0


# ---------------- профиль ----------------
class TestProfile:
    def test_get_and_update(self, client, user, token):
        assert jget(client, "/api/profile", token).json()["email"] == user.email
        r = jput(client, "/api/profile", {"name": "Новое Имя", "email": user.email, "phone": "8 999 111 22 33"}, token)
        assert r.status_code == 200
        user.refresh_from_db()
        assert user.name == "Новое Имя" and user.phone == "+79991112233"
        assert UserAction.objects.filter(user=user, action="update_profile").exists()

    def test_cannot_take_foreign_email_or_clear_both(self, client, user, other_user, token):
        assert jput(client, "/api/profile", {"name": "Имя", "email": other_user.email, "phone": ""}, token).status_code == 400
        assert jput(client, "/api/profile", {"name": "Имя", "email": "", "phone": ""}, token).status_code == 400

    def test_change_password(self, client, user, token):
        bad = jpost(client, "/api/profile/password", {"old_password": "nope", "new_password": "NewPassw0rd!",
                                                       "confirm_password": "NewPassw0rd!"}, token)
        assert bad.status_code == 400
        ok = jpost(client, "/api/profile/password", {"old_password": "Passw0rd!", "new_password": "NewPassw0rd!",
                                                      "confirm_password": "NewPassw0rd!"}, token)
        assert ok.status_code == 200
        c = client.__class__()
        assert jpost(c, "/api/login", {"login": user.email, "password": "NewPassw0rd!"}).status_code == 200
        assert jpost(c, "/api/login", {"login": user.email, "password": "Passw0rd!"}).status_code == 401


# ---------------- обратная связь ----------------
class TestFeedback:
    payload = {"subject": "Вопрос по заказу", "message": "Подскажите сроки доставки, пожалуйста", "rating": 4, "consent": True}

    def test_requires_token(self, client):
        assert jpost(client, "/api/feedback", self.payload).status_code == 401

    def test_create_and_list_own_only(self, client, user, other_user, token):
        assert jpost(client, "/api/feedback", self.payload, token).status_code == 201
        fb = Feedback.objects.get()
        assert fb.user == user and fb.consent_at is not None and fb.status == "new"
        Feedback.objects.create(user=other_user, subject="Чужое", message="Чужое сообщение 123")
        items = jget(client, "/api/feedback", token).json()["results"]
        assert len(items) == 1 and items[0]["subject"] == "Вопрос по заказу"

    @pytest.mark.parametrize("patch", [{"consent": False}, {"rating": 6}, {"subject": "ab"}, {"message": "коротко"}])
    def test_validation(self, client, token, patch):
        assert jpost(client, "/api/feedback", {**self.payload, **patch}, token).status_code == 400
        assert Feedback.objects.count() == 0


# ---------------- поиск ----------------
class TestSearch:
    def test_short_query_rejected(self, client):
        assert client.get("/api/search?q=a").status_code == 400

    def test_case_insensitive_by_name_and_description(self, client, product):
        assert client.get("/api/search?q=смартфон").json()["count"] == 1
        assert client.get("/api/search?q=СМАРТФОН").json()["count"] == 1
        assert client.get("/api/search?q=подробное").json()["count"] == 1   # описание
        assert client.get("/api/search?q=несуществует").json()["count"] == 0

    def test_sort_by_price(self, client, product):
        Product.objects.create(name="Смартфон Дорогой", alias="expensive", price=Decimal("9999"))
        asc = [p["price"] for p in client.get("/api/search?q=смартфон&sort=price").json()["results"]]
        desc = [p["price"] for p in client.get("/api/search?q=смартфон&sort=-price").json()["results"]]
        assert asc == sorted(asc) and desc == sorted(desc, reverse=True)

    def test_history_is_kept_in_session(self, client, product):
        client.get("/api/search?q=смартфон")
        client.get("/api/search?q=наушники")
        client.get("/api/search?q=смартфон")
        assert client.session["search_history"] == ["смартфон", "наушники"]

    def test_search_is_logged_for_authorized(self, client, user, token, product):
        jget(client, "/api/search?q=смартфон", token)
        assert UserAction.objects.filter(user=user, action="search", page="смартфон").exists()


def test_actions_endpoint(client, user, token):
    UserAction.objects.create(user=user, action="login", page="/login/")
    UserAction.objects.create(user=user, action="search", page="q")
    assert len(jget(client, "/api/actions", token).json()["results"]) == 2
    assert len(jget(client, "/api/actions?limit=1", token).json()["results"]) == 1
    assert len(jget(client, "/api/actions?limit=abc", token).json()["results"]) == 2


# ---------------- корзина и заказы ----------------
class TestCartAndOrders:
    def test_anonymous_cart_lives_in_session(self, client, product):
        r = jput(client, "/api/cart", {"items": [{"product_id": product.id, "qty": 3}]})
        assert r.status_code == 200 and r.json()["total"] == 5997.0
        assert client.session["cart"] == {str(product.id): 3} and CartItem.objects.count() == 0
        assert jget(client, "/api/cart").json()["items"][0]["qty"] == 3

    def test_authorized_cart_is_saved_in_db(self, client, user, token, product):
        jput(client, "/api/cart", {"items": [{"product_id": product.id, "qty": 2}]}, token)
        assert CartItem.objects.get(user=user).quantity == 2
        jput(client, "/api/cart", {"items": []}, token)                 # пустой список очищает корзину
        assert CartItem.objects.count() == 0

    @pytest.mark.parametrize("items", [[{"product_id": 1, "qty": 0}], [{"product_id": 1, "qty": 100}],
                                       [{"product_id": "x", "qty": 1}], [{"qty": 1}], "not-a-list"])
    def test_invalid_items(self, client, product, items):
        assert jput(client, "/api/cart", {"items": items}).status_code == 400

    def test_unavailable_and_unknown_products_are_dropped(self, client, product):
        product.available = False
        product.save()
        r = jput(client, "/api/cart", {"items": [{"product_id": product.id, "qty": 1}, {"product_id": 99999, "qty": 1}]})
        assert r.json()["items"] == []

    def _fill(self, client, token, product, qty=2):
        jput(client, "/api/cart", {"items": [{"product_id": product.id, "qty": qty}]}, token)

    def test_order_requires_auth_and_all_consents(self, client, token, product):
        assert jpost(client, "/api/orders", {}).status_code == 401
        self._fill(client, token, product)
        full = {"consent": True, "consent_third": True, "terms": True}
        for missing in full:
            assert jpost(client, "/api/orders", {**full, missing: False}, token).status_code == 400
        assert Order.objects.count() == 0

    def test_empty_cart_cannot_be_ordered(self, client, token):
        r = jpost(client, "/api/orders", {"consent": True, "consent_third": True, "terms": True}, token)
        assert r.status_code == 400

    def test_order_flow(self, client, user, token, product):
        self._fill(client, token, product, qty=2)
        r = jpost(client, "/api/orders", {"consent": True, "consent_third": True, "terms": True}, token)
        assert r.status_code == 201 and r.json()["total"] == 3998.0
        order = Order.objects.get()
        assert order.user == user and order.total == Decimal("3998.00")
        assert order.consent_at and order.third_party_consent_at
        item = OrderItem.objects.get()
        assert (item.name, item.price, item.quantity) == ("Смартфон Тест", Decimal("1999.00"), 2)
        assert CartItem.objects.count() == 0 and client.session["cart"] == {}
        assert UserAction.objects.filter(user=user, action="checkout").exists()
        # смена цены не меняет уже оформленный заказ
        product.price = Decimal("5.00")
        product.save()
        assert OrderItem.objects.get().price == Decimal("1999.00")
        listing = jget(client, "/api/orders", token).json()["results"]
        assert listing[0]["items"][0]["qty"] == 2

    def test_client_cannot_set_price(self, client, token, product):
        self._fill(client, token, product, qty=1)
        jpost(client, "/api/orders", {"consent": True, "consent_third": True, "terms": True, "total": 1,
                                       "price": 1}, token)
        assert Order.objects.get().total == Decimal("1999.00")        # цена берётся из БД
