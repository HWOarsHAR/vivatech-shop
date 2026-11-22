"""Выгрузка каталога (товары, категории, производители, свойства, изображения) в JSON.

Запускается ЛОКАЛЬНО, перед публикацией: файл fixtures/catalog.json попадает в архив,
а на сервере команда bootstrap загружает его в пустую базу.
Пользователи, заказы и отзывы не выгружаются.
"""
import json
from pathlib import Path

from django.conf import settings
from django.core import serializers
from django.core.management.base import BaseCommand

from store.models import Category, Manufacturer, Product, ProductImage, ProductProperty


class Command(BaseCommand):
    help = "Выгружает каталог в fixtures/catalog.json (UTF-8)"

    def add_arguments(self, parser):
        parser.add_argument("--output", default=str(Path(settings.BASE_DIR) / "fixtures" / "catalog.json"))

    def handle(self, *args, **opts):
        objs = (list(Manufacturer.objects.order_by("pk")) + list(Category.objects.order_by("pk"))
                + list(Product.objects.order_by("pk")) + list(ProductProperty.objects.order_by("pk"))
                + list(ProductImage.objects.order_by("pk")))
        text = serializers.serialize("json", objs, indent=2, ensure_ascii=False)
        out = Path(opts["output"])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")          # явно UTF-8 (в Windows по умолчанию cp1251)
        counts = {k: len([o for o in objs if o._meta.model_name == k]) for k in
                  ("manufacturer", "category", "product", "productproperty", "productimage")}
        self.stdout.write(self.style.SUCCESS(f"Каталог выгружен в {out}: {json.dumps(counts, ensure_ascii=False)}"))
