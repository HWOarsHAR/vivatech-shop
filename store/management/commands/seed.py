from django.core.management.base import BaseCommand

from store.auth import hash_password
from store.models import Category, Manufacturer, Product, ProductImage, ProductProperty, User

DATA = [  # (название, алиас, категория, производитель, цена, краткое, свойства)
    ("Смартфон Nova X1", "nova-x1", "smartphones", "Nova", 39990, "6.5\" AMOLED, 128 ГБ", [("Память", "128 ГБ", 0), ("Память", "256 ГБ", 5000), ("Цвет", "Графит", 0)]),
    ("Смартфон Nova X1 Pro", "nova-x1-pro", "smartphones", "Nova", 59990, "6.7\" AMOLED 120 Гц, 256 ГБ", [("Память", "256 ГБ", 0), ("Камера", "108 Мп", 0)]),
    ("Смартфон Orbit Lite", "orbit-lite", "smartphones", "Orbit", 17990, "Бюджетный, 64 ГБ", [("Память", "64 ГБ", 0)]),
    ("Ноутбук Orbit Book 14", "orbit-book-14", "laptops", "Orbit", 74990, "14\" IPS, 16 ГБ ОЗУ, SSD 512 ГБ", [("ОЗУ", "16 ГБ", 0), ("SSD", "512 ГБ", 0)]),
    ("Ноутбук Nova Pro 16", "nova-pro-16", "laptops", "Nova", 129990, "16\" 2.5K, RTX, 32 ГБ", [("ОЗУ", "32 ГБ", 0), ("SSD", "1 ТБ", 0)]),
    ("Беспроводные наушники Pulse", "pulse-buds", "accessories", "Pulse", 6990, "Bluetooth 5.3, шумоподавление", [("Автономность", "24 ч", 0)]),
    ("Зарядное устройство 65 Вт", "charger-65w", "accessories", "Pulse", 2490, "GaN, USB-C ×2", [("Мощность", "65 Вт", 0)]),
    ("Умные часы Orbit Watch", "orbit-watch", "accessories", "Orbit", 12990, "AMOLED, GPS, пульсометр", [("Ремешок", "Силикон", 0), ("Ремешок", "Металл", 1500)]),
]


class Command(BaseCommand):
    help = "Заполняет БД демонстрационными данными (идемпотентно)"

    def add_arguments(self, parser):
        parser.add_argument("--no-users", action="store_true",
                            help="не создавать демо-пользователей с известными паролями (для боевого сервера)")

    def handle(self, *args, **opts):
        cats = {a: Category.objects.get_or_create(alias=a, defaults={"name": n})[0] for a, n in
                [("smartphones", "Смартфоны"), ("laptops", "Ноутбуки"), ("accessories", "Аксессуары")]}
        for name, alias, cat, man, price, short, props in DATA:
            m, _ = Manufacturer.objects.get_or_create(name=man)
            p, created = Product.objects.get_or_create(alias=alias, defaults=dict(
                name=name, manufacturer=m, price=price, short_description=short,
                description=f"{name}. {short}. Гарантия 12 месяцев, официальная поставка.",
                meta_title=name, meta_keywords=f"{name}, купить", meta_description=short))
            if created:
                p.categories.add(cats[cat])
                for n, v, pr in props:
                    ProductProperty.objects.create(product=p, property_name=n, property_value=v, property_price=pr)
                ProductImage.objects.create(product=p, image="/static/img/placeholder.svg", title=name)
        if opts["no_users"]:
            self.stdout.write(self.style.SUCCESS("Демо-каталог готов (пользователи не создавались)."))
            return
        for name, email, pwd, role in [("Администратор", "admin@example.com", "Admin12345", "admin"),
                                       ("Тестовый пользователь", "user@example.com", "User12345", "user")]:
            User.objects.get_or_create(email=email, defaults=dict(
                name=name, role=role, password_hash=hash_password(pwd)))
        self.stdout.write(self.style.SUCCESS(
            "Готово. admin@example.com / Admin12345 ; user@example.com / User12345"))
