"""Unit-тесты серверной валидации форм (Задание 3)."""
import pytest

from store.forms import FeedbackForm, LoginForm, PasswordChangeForm, ProfileForm, RegisterForm, normalize_phone
from store.models import User
from tests.helpers import reg_payload


@pytest.mark.parametrize("raw, expected", [
    ("+7 (999) 123-45-67", "+79991234567"),
    ("8 999 123 45 67", "+79991234567"),
    ("79991234567", "+79991234567"),
    ("9991234567", "+79991234567"),
    ("12345", None),
    ("", None),
    (None, None),
    ("+1 202 555 0100", None),
])
def test_normalize_phone(raw, expected):
    assert normalize_phone(raw) == expected


@pytest.mark.django_db
class TestRegisterForm:
    def test_valid_email_only(self):
        f = RegisterForm(reg_payload())
        assert f.is_valid(), f.errors
        assert f.cleaned_data["email"] == "ivan@example.com"
        assert f.cleaned_data["phone"] is None

    def test_email_is_lowercased(self):
        f = RegisterForm(reg_payload(email="IVAN@Example.COM"))
        assert f.is_valid() and f.cleaned_data["email"] == "ivan@example.com"

    def test_valid_phone_only_is_normalized(self):
        f = RegisterForm(reg_payload(email="", phone="8 (999) 123-45-67"))
        assert f.is_valid(), f.errors
        assert f.cleaned_data["phone"] == "+79991234567" and f.cleaned_data["email"] is None

    def test_requires_email_or_phone(self):
        f = RegisterForm(reg_payload(email="", phone=""))
        assert not f.is_valid() and "__all__" in f.errors

    @pytest.mark.parametrize("field, value", [
        ("email", "not-an-email"), ("phone", "123"), ("name", "А"), ("password", "short1"),
    ])
    def test_invalid_fields(self, field, value):
        data = reg_payload(**{field: value})
        if field == "password":
            data["confirm_password"] = value
        f = RegisterForm(data)
        assert not f.is_valid() and field in f.errors

    def test_password_mismatch(self):
        f = RegisterForm(reg_payload(confirm_password="Different1!"))
        assert not f.is_valid() and "confirm_password" in f.errors

    def test_password_longer_than_72_bytes_rejected(self):
        long_pwd = "я" * 40  # 80 байт в UTF-8 — bcrypt учитывает только 72
        f = RegisterForm(reg_payload(password=long_pwd, confirm_password=long_pwd))
        assert not f.is_valid() and "password" in f.errors

    @pytest.mark.parametrize("field", ["consent", "terms"])
    def test_required_consents(self, field):
        f = RegisterForm(reg_payload(**{field: False}))
        assert not f.is_valid() and field in f.errors

    def test_ads_consent_is_optional(self):
        assert RegisterForm(reg_payload(ads=False)).is_valid()
        assert RegisterForm(reg_payload(ads=True)).is_valid()

    def test_duplicate_email_and_phone(self, user):
        assert "email" in RegisterForm(reg_payload(email=user.email)).errors
        User.objects.create(name="Т", phone="+79991234567", password_hash="x")
        assert "phone" in RegisterForm(reg_payload(email="", phone="8 999 123 45 67")).errors


def test_login_form_requires_both_fields():
    assert LoginForm({"login": "a@b.ru", "password": "x"}).is_valid()
    assert not LoginForm({"login": "", "password": "x"}).is_valid()
    assert not LoginForm({"login": "a@b.ru", "password": ""}).is_valid()


@pytest.mark.django_db
def test_feedback_form_rules():
    ok = {"subject": "Тема", "message": "Достаточно длинное сообщение", "rating": 5, "consent": True}
    assert FeedbackForm(ok).is_valid()
    assert FeedbackForm({**ok, "rating": ""}).is_valid()            # оценка необязательна
    assert not FeedbackForm({**ok, "rating": 6}).is_valid()
    assert not FeedbackForm({**ok, "rating": 0}).is_valid()
    assert not FeedbackForm({**ok, "subject": "ab"}).is_valid()
    assert not FeedbackForm({**ok, "message": "коротко"}).is_valid()
    assert not FeedbackForm({**ok, "consent": False}).is_valid()


@pytest.mark.django_db
def test_profile_form_unique_and_required(user, other_user):
    assert not ProfileForm({"name": "Имя", "email": other_user.email, "phone": ""}, user=user).is_valid()
    assert ProfileForm({"name": "Имя", "email": user.email, "phone": ""}, user=user).is_valid()  # свой email можно
    assert not ProfileForm({"name": "Имя", "email": "", "phone": ""}, user=user).is_valid()


@pytest.mark.django_db
def test_password_change_form(user):
    ok = {"old_password": "Passw0rd!", "new_password": "NewPassw0rd!", "confirm_password": "NewPassw0rd!"}
    assert PasswordChangeForm(ok, user=user).is_valid()
    assert not PasswordChangeForm({**ok, "old_password": "wrong"}, user=user).is_valid()
    assert not PasswordChangeForm({**ok, "confirm_password": "Other1234!"}, user=user).is_valid()
    assert not PasswordChangeForm({**ok, "new_password": "short", "confirm_password": "short"}, user=user).is_valid()
