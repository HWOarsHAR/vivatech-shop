"""Модели БД (Задание 1). Имена таблиц заданы явно (db_table) по условию ЛР.

Таблицы: products, product_properties, product_images, categories, users,
feedback, user_sessions, user_actions + manufacturers, product_categories (M2M),
cart_items, orders, order_items (для корзины и истории заказов).
"""
from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.templatetags.static import static


class Manufacturer(models.Model):
    name = models.CharField("Название", max_length=150, unique=True)

    class Meta:
        db_table = "manufacturers"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Category(models.Model):
    name = models.CharField("Название", max_length=150)
    alias = models.SlugField("Алиас (URL)", max_length=160, unique=True, allow_unicode=True)

    class Meta:
        db_table = "categories"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Product(models.Model):
    # SET_NULL: удаление производителя не должно удалять товары
    manufacturer = models.ForeignKey(Manufacturer, null=True, blank=True,
                                     on_delete=models.SET_NULL, related_name="products",
                                     verbose_name="Производитель")
    categories = models.ManyToManyField(Category, db_table="product_categories",
                                        related_name="products", blank=True,
                                        verbose_name="Категории")
    name = models.CharField("Название", max_length=200)
    alias = models.SlugField("Алиас (URL)", max_length=220, unique=True, allow_unicode=True,
                             blank=True)
    short_description = models.CharField("Краткое описание", max_length=300, blank=True)
    description = models.TextField("Описание", blank=True)
    price = models.DecimalField("Цена, ₽", max_digits=10, decimal_places=2,
                                validators=[MinValueValidator(Decimal("0"))])
    image = models.CharField("Изображение (URL/путь)", max_length=300, blank=True)
    available = models.BooleanField("В наличии", default=True)
    meta_keywords = models.CharField(max_length=300, blank=True)
    meta_description = models.CharField(max_length=300, blank=True)
    meta_title = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "products"
        ordering = ["-created_at"]
        constraints = [  # валидация на уровне БД (CHECK)
            models.CheckConstraint(condition=models.Q(price__gte=0), name="products_price_gte_0"),
        ]

    def __str__(self):
        return self.name

    @property
    def image_url(self):
        return self.image or static("img/placeholder.svg")


class ProductProperty(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="properties")
    property_name = models.CharField("Свойство", max_length=100)
    property_value = models.CharField("Значение", max_length=200)
    property_price = models.DecimalField("Доплата, ₽", max_digits=10, decimal_places=2,
                                         default=0, validators=[MinValueValidator(Decimal("0"))])

    class Meta:
        db_table = "product_properties"


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    image = models.CharField("Изображение (URL/путь)", max_length=300)
    title = models.CharField("Подпись", max_length=150, blank=True)

    class Meta:
        db_table = "product_images"


class User(models.Model):
    ROLES = [("user", "Пользователь"), ("admin", "Администратор")]
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True, null=True, blank=True)
    phone = models.CharField(max_length=16, unique=True, null=True, blank=True)
    password_hash = models.CharField(max_length=128)             # bcrypt-хэш
    role = models.CharField(max_length=10, choices=ROLES, default="user")
    created_at = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(null=True, blank=True)
    consent_at = models.DateTimeField(null=True, blank=True)     # согласие на обработку ПДн (152-ФЗ)
    ads_consent_at = models.DateTimeField(null=True, blank=True)
    terms_accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "users"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(email__isnull=False) | models.Q(phone__isnull=False),
                name="users_email_or_phone",
            ),
        ]

    def __str__(self):
        return self.email or self.phone or f"User {self.pk}"

    @property
    def is_admin(self):
        return self.role == "admin"


class Feedback(models.Model):
    STATUSES = [("new", "Новое"), ("in_progress", "В работе"), ("resolved", "Решено")]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="feedbacks")
    subject = models.CharField(max_length=200)
    message = models.TextField()
    rating = models.PositiveSmallIntegerField(null=True, blank=True,
                                              validators=[MinValueValidator(1), MaxValueValidator(5)])
    status = models.CharField(max_length=12, choices=STATUSES, default="new")
    consent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "feedback"
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(condition=models.Q(rating__isnull=True) |
                                   (models.Q(rating__gte=1) & models.Q(rating__lte=5)),
                                   name="feedback_rating_1_5"),
        ]


class UserSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sessions")
    session_token = models.CharField(max_length=64, unique=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        db_table = "user_sessions"


class UserAction(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="actions")
    action = models.CharField(max_length=50)
    page = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "user_actions"
        ordering = ["-created_at", "-id"]


class CartItem(models.Model):
    """Корзина, привязанная к пользователю в БД (Задание 7)."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="cart_items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveSmallIntegerField(default=1,
                                                validators=[MinValueValidator(1), MaxValueValidator(99)])

    class Meta:
        db_table = "cart_items"
        constraints = [models.UniqueConstraint(fields=["user", "product"], name="cart_user_product_uniq")]


class Order(models.Model):
    STATUSES = [("new", "Новый"), ("paid", "Оплачен"), ("done", "Выполнен"), ("canceled", "Отменён")]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="orders")
    status = models.CharField(max_length=10, choices=STATUSES, default="new")
    total = models.DecimalField(max_digits=12, decimal_places=2)
    consent_at = models.DateTimeField(null=True, blank=True)
    third_party_consent_at = models.DateTimeField(null=True, blank=True)
    terms_accepted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "orders"
        ordering = ["-created_at"]


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    # SET_NULL + снимок названия/цены: история заказа не ломается при удалении товара
    product = models.ForeignKey(Product, null=True, on_delete=models.SET_NULL)
    name = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveSmallIntegerField()

    class Meta:
        db_table = "order_items"
