"""Тесты HTML-страниц, защиты маршрутов и админ-панели (Задания 4, 6, 7)."""
from decimal import Decimal

import pytest

from store.models import Category, Feedback, Manufacturer, Product, User
from tests.helpers import session_login

pytestmark = pytest.mark.django_db

PANEL_FORMSETS = {"props-TOTAL_FORMS": "0", "props-INITIAL_FORMS": "0", "props-MIN_NUM_FORMS": "0",
                  "props-MAX_NUM_FORMS": "1000", "imgs-TOTAL_FORMS": "0", "imgs-INITIAL_FORMS": "0",
                  "imgs-MIN_NUM_FORMS": "0", "imgs-MAX_NUM_FORMS": "1000"}


def html(response):
    return response.content.decode("utf-8")


# ---------------- публичные страницы ----------------
class TestPublicPages:
    @pytest.mark.parametrize("path", ["/", "/register/", "/login/", "/feedback/", "/cart/", "/privacy/", "/terms/"])
    def test_pages_open(self, client, path):
        assert client.get(path).status_code == 200

    def test_index_lists_products_and_slider(self, client, product):
        content = html(client.get("/"))
        assert "Смартфон Тест" in content and 'id="slider"' in content

    def test_unavailable_products_are_hidden(self, client, product):
        product.available = False
        product.save()
        assert "Смартфон Тест" not in html(client.get("/"))

    def test_category_filter_and_sort(self, client):
        cat = Category.objects.create(name="Телефоны", alias="phones")
        a = Product.objects.create(name="Дешёвый", alias="cheap", price=Decimal("10"))
        b = Product.objects.create(name="Дорогой", alias="rich", price=Decimal("999"))
        c = Product.objects.create(name="Другой", alias="other", price=Decimal("500"))
        a.categories.add(cat)
        b.categories.add(cat)
        content = html(client.get("/?category=phones&sort=-price"))
        assert "Другой" not in content and content.index("Дорогой") < content.index("Дешёвый")

    def test_pagination_8_per_page(self, client):
        for i in range(9):
            Product.objects.create(name=f"Товар-{i}", alias=f"p{i}", price=Decimal(i + 1))
        assert html(client.get("/?sort=name")).count('class="card"') == 8
        assert html(client.get("/?sort=name&page=2")).count('class="card"') == 1

    def test_product_page_and_404(self, client, product):
        assert client.get(f"/product/{product.id}/").status_code == 200
        assert client.get("/product/999999/").status_code == 404

    def test_last_viewed_keeps_five_unique(self, client):
        ids = [Product.objects.create(name=f"T{i}", alias=f"t{i}", price=Decimal(1)).id for i in range(7)]
        for pk in ids + [ids[-1]]:
            client.get(f"/product/{pk}/")
        assert client.session["last_viewed"] == [ids[-1], ids[-2], ids[-3], ids[-4], ids[-5]]
        assert "Вы смотрели" in html(client.get("/"))

    def test_search_page(self, client, product):
        assert "Смартфон Тест" in html(client.get("/search/?q=смартфон"))
        assert "минимум 2 символа" in html(client.get("/search/?q=a"))

    def test_login_next_open_redirect_is_blocked(self, client):
        assert 'data-redirect="/profile/"' in html(client.get("/login/?next=https://evil.example/"))
        assert 'data-redirect="/cart/"' in html(client.get("/login/?next=/cart/"))


# ---------------- защита от XSS (экранирование) ----------------
class TestXss:
    PAYLOAD = "<script>alert('XSS')</script>"

    def test_product_name_is_escaped(self, client):
        p = Product.objects.create(name=self.PAYLOAD, alias="xss", price=Decimal("1"))
        for url in ("/", f"/product/{p.id}/", "/search/?q=alert"):
            content = html(client.get(url))
            assert self.PAYLOAD not in content and "&lt;script&gt;" in content

    def test_search_query_is_escaped(self, client):
        content = html(client.get("/search/", {"q": self.PAYLOAD}))
        assert self.PAYLOAD not in content

    def test_img_onerror_payload_is_escaped(self, client):
        evil = '"><img src=x onerror=alert(1)>'
        content = html(client.get("/search/", {"q": evil}))
        assert evil not in content


# ---------------- защита маршрутов ----------------
class TestAccessControl:
    def test_profile_requires_login(self, client):
        r = client.get("/profile/")
        assert r.status_code == 302 and r["Location"] == "/login/?next=/profile/"

    def test_profile_for_logged_user(self, client, user):
        session_login(client, user)
        assert client.get("/profile/").status_code == 200

    def test_panel_anonymous_user_and_admin(self, client, user, admin):
        r = client.get("/panel/")
        assert r.status_code == 302 and r["Location"].startswith("/login/")
        session_login(client, user)
        r = client.get("/panel/")
        assert r.status_code == 302 and r["Location"] == "/"             # обычному пользователю — нельзя
        for path in ("/panel/products/", "/panel/users/", "/panel/feedback/", "/panel/products/new/"):
            assert client.get(path).status_code == 302
        c = client.__class__()
        session_login(c, admin)
        for path in ("/panel/", "/panel/products/", "/panel/users/", "/panel/feedback/", "/panel/products/new/"):
            assert c.get(path).status_code == 200

    def test_deleted_user_session_is_dropped(self, client, user):
        session_login(client, user)
        user.delete()
        assert client.get("/profile/").status_code == 302


# ---------------- админ-панель ----------------
class TestPanel:
    @pytest.fixture
    def adm(self, client, admin):
        session_login(client, admin)
        return client

    def test_create_product_builds_alias(self, adm):
        r = adm.post("/panel/products/new/", {"name": "Новый товар", "alias": "", "price": "100.00",
                                               "available": "on", **PANEL_FORMSETS})
        assert r.status_code == 302 and r["Location"] == "/panel/products/"
        p = Product.objects.get(name="Новый товар")
        assert p.alias == "новый-товар" and p.price == Decimal("100.00")

    def test_negative_price_and_duplicate_alias_rejected(self, adm, product):
        r = adm.post("/panel/products/new/", {"name": "Минус", "alias": "m", "price": "-5", **PANEL_FORMSETS})
        assert r.status_code == 200 and not Product.objects.filter(name="Минус").exists()
        r = adm.post("/panel/products/new/", {"name": "Копия", "alias": product.alias, "price": "5", **PANEL_FORMSETS})
        assert r.status_code == 200 and Product.objects.count() == 1

    def test_edit_and_delete_product(self, adm, product):
        adm.post(f"/panel/products/{product.id}/", {"name": "Переименован", "alias": product.alias,
                                                    "price": "2500.00", "available": "on", **PANEL_FORMSETS})
        product.refresh_from_db()
        assert product.name == "Переименован" and product.price == Decimal("2500.00")
        assert adm.get(f"/panel/products/{product.id}/delete/").status_code == 405   # только POST
        assert adm.post(f"/panel/products/{product.id}/delete/").status_code == 302
        assert not Product.objects.exists()

    def test_sorting_whitelist(self, adm, product):
        Product.objects.create(name="Дорогой", alias="r", price=Decimal("9999"))
        content = html(adm.get("/panel/products/?sort=price&dir=desc"))
        assert content.index("Дорогой") < content.index("Смартфон Тест")
        # произвольное значение вместо поля сортировки не ломает страницу и не вызывает ошибку SQL
        assert adm.get("/panel/products/?sort=password_hash;DROP TABLE users").status_code == 200
        assert adm.get("/panel/products/?q=смартфон").status_code == 200

    def test_admin_cannot_change_or_delete_self(self, adm, admin):
        adm.post(f"/panel/users/{admin.id}/", {"act": "user"})
        adm.post(f"/panel/users/{admin.id}/", {"act": "delete"})
        admin.refresh_from_db()
        assert admin.role == "admin" and User.objects.filter(pk=admin.pk).exists()

    def test_role_change_and_user_delete(self, adm, user):
        adm.post(f"/panel/users/{user.id}/", {"act": "admin"})
        user.refresh_from_db()
        assert user.role == "admin"
        adm.post(f"/panel/users/{user.id}/", {"act": "delete"})
        assert not User.objects.filter(pk=user.pk).exists()

    def test_feedback_moderation(self, adm, user):
        fb = Feedback.objects.create(user=user, subject="Тема", message="Сообщение 1234567")
        adm.post(f"/panel/feedback/{fb.id}/", {"status": "resolved"})
        fb.refresh_from_db()
        assert fb.status == "resolved"
        adm.post(f"/panel/feedback/{fb.id}/", {"status": "hacked"})     # неизвестный статус игнорируется
        fb.refresh_from_db()
        assert fb.status == "resolved"
        assert "Тема" in html(adm.get("/panel/feedback/?status=resolved"))
        adm.post(f"/panel/feedback/{fb.id}/", {"act": "delete"})
        assert not Feedback.objects.exists()
