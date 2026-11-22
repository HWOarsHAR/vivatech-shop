"""Серверная валидация (дублирует клиентскую — комбинированный подход)."""
import re

from django import forms
from django.utils.text import slugify

from .auth import verify_password
from .models import Product, ProductImage, ProductProperty, User


def _check_bcrypt_len(password):
    # bcrypt учитывает только первые 72 байта — запрещаем более длинные
    if len(password.encode("utf-8")) > 72:
        raise forms.ValidationError("Пароль слишком длинный (максимум 72 байта)")
    return password


def normalize_phone(raw):
    """Нормализует российский номер к +7XXXXXXXXXX; None при неверном формате."""
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 11 and digits[0] in "78":
        digits = digits[1:]
    if len(digits) != 10:
        return None
    return "+7" + digits


class RegisterForm(forms.Form):
    name = forms.CharField(min_length=2, max_length=100, strip=True,
                           error_messages={"required": "Введите имя", "min_length": "Минимум 2 символа"})
    email = forms.EmailField(required=False, error_messages={"invalid": "Некорректный email"})
    phone = forms.CharField(required=False, max_length=30)
    password = forms.CharField(min_length=8, error_messages={"required": "Введите пароль",
                                                             "min_length": "Минимум 8 символов"})
    confirm_password = forms.CharField(error_messages={"required": "Повторите пароль"})
    consent = forms.BooleanField(error_messages={"required": "Необходимо согласие на обработку персональных данных"})
    terms = forms.BooleanField(error_messages={"required": "Необходимо принять Пользовательское соглашение"})
    ads = forms.BooleanField(required=False)

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").lower()
        if email and User.objects.filter(email=email).exists():
            raise forms.ValidationError("Пользователь с таким email уже существует")
        return email or None

    def clean_phone(self):
        raw = self.cleaned_data.get("phone") or ""
        if not raw.strip():
            return None
        phone = normalize_phone(raw)
        if phone is None:
            raise forms.ValidationError("Введите российский номер в формате +7 (999) 123-45-67")
        if User.objects.filter(phone=phone).exists():
            raise forms.ValidationError("Пользователь с таким телефоном уже существует")
        return phone

    def clean_password(self):
        return _check_bcrypt_len(self.cleaned_data["password"])

    def clean(self):
        data = super().clean()
        if not data.get("email") and not data.get("phone"):
            self.add_error(None, "Укажите email или телефон")
        if data.get("password") and data.get("confirm_password") and data["password"] != data["confirm_password"]:
            self.add_error("confirm_password", "Пароли не совпадают")
        return data


class LoginForm(forms.Form):
    login = forms.CharField(max_length=254, strip=True, error_messages={"required": "Введите email или телефон"})
    password = forms.CharField(error_messages={"required": "Введите пароль"})


class ProfileForm(forms.Form):
    name = forms.CharField(min_length=2, max_length=100, strip=True)
    email = forms.EmailField(required=False)
    phone = forms.CharField(required=False, max_length=30)

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").lower()
        if email and User.objects.filter(email=email).exclude(pk=self.user.pk).exists():
            raise forms.ValidationError("Этот email уже занят")
        return email or None

    def clean_phone(self):
        raw = self.cleaned_data.get("phone") or ""
        if not raw.strip():
            return None
        phone = normalize_phone(raw)
        if phone is None:
            raise forms.ValidationError("Введите российский номер в формате +7 (999) 123-45-67")
        if User.objects.filter(phone=phone).exclude(pk=self.user.pk).exists():
            raise forms.ValidationError("Этот телефон уже занят")
        return phone

    def clean(self):
        data = super().clean()
        if not data.get("email") and not data.get("phone"):
            self.add_error(None, "Укажите email или телефон")
        return data


class PasswordChangeForm(forms.Form):
    old_password = forms.CharField()
    new_password = forms.CharField(min_length=8, error_messages={"min_length": "Минимум 8 символов"})
    confirm_password = forms.CharField()

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_old_password(self):
        if not verify_password(self.cleaned_data["old_password"], self.user.password_hash):
            raise forms.ValidationError("Неверный текущий пароль")
        return self.cleaned_data["old_password"]

    def clean_new_password(self):
        return _check_bcrypt_len(self.cleaned_data["new_password"])

    def clean(self):
        data = super().clean()
        if data.get("new_password") and data.get("new_password") != data.get("confirm_password"):
            self.add_error("confirm_password", "Пароли не совпадают")
        return data


class FeedbackForm(forms.Form):
    consent = forms.BooleanField(error_messages={"required": "Необходимо согласие на обработку персональных данных"})
    subject = forms.CharField(min_length=3, max_length=200, strip=True,
                              error_messages={"required": "Укажите тему", "min_length": "Минимум 3 символа"})
    message = forms.CharField(min_length=10, strip=True,
                              error_messages={"required": "Введите сообщение", "min_length": "Минимум 10 символов"})
    rating = forms.IntegerField(required=False, min_value=1, max_value=5,
                                error_messages={"min_value": "Оценка от 1 до 5", "max_value": "Оценка от 1 до 5",
                                                "invalid": "Оценка от 1 до 5"})


# ---------- админ-панель ----------
class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        exclude = ["created_at"]
        widgets = {"categories": forms.CheckboxSelectMultiple,
                   "description": forms.Textarea(attrs={"rows": 5})}

    def clean_alias(self):
        # если алиас не введён — строим из названия
        alias = self.cleaned_data.get("alias") or slugify(self.data.get("name", ""), allow_unicode=True)
        if not alias:
            raise forms.ValidationError("Не удалось построить алиас — введите вручную")
        if Product.objects.filter(alias=alias).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Такой алиас уже есть")
        return alias


PropertyFormSet = forms.inlineformset_factory(
    Product, ProductProperty, fields=["property_name", "property_value", "property_price"],
    extra=2, can_delete=True)
ImageFormSet = forms.inlineformset_factory(
    Product, ProductImage, fields=["image", "title"], extra=1, can_delete=True)


class CheckoutConsentForm(forms.Form):
    consent = forms.BooleanField(error_messages={"required": "Необходимо согласие на обработку персональных данных"})
    consent_third = forms.BooleanField(error_messages={"required": "Необходимо согласие на передачу данных третьим лицам"})
    terms = forms.BooleanField(error_messages={"required": "Необходимо принять Пользовательское соглашение"})
