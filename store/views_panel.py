"""Админ-панель (Задание 6.2): товары (CRUD + сортировка), пользователи, модерация отзывов."""
from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .auth import admin_required, log_action
from .forms import ImageFormSet, ProductForm, PropertyFormSet
from .models import Feedback, Product, User

PRODUCT_SORT_FIELDS = {"id": "ID", "name": "Название", "price": "Цена",
                       "created_at": "Дата", "available": "Наличие"}


@admin_required
def dashboard(request):
    return render(request, "panel/dashboard.html", {
        "stats": {"products": Product.objects.count(), "users": User.objects.count(),
                  "new_feedback": Feedback.objects.filter(status="new").count()}})


@admin_required
def products(request):
    sort = request.GET.get("sort", "id")
    if sort not in PRODUCT_SORT_FIELDS:       # whitelist — защита от произвольного order_by
        sort = "id"
    direction = "-" if request.GET.get("dir") == "desc" else ""
    q = request.GET.get("q", "").strip()
    qs = Product.objects.select_related("manufacturer").order_by(direction + sort)
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(alias__icontains=q))
    return render(request, "panel/products.html", {
        "products": qs, "sort": sort, "dir": request.GET.get("dir", "asc"), "q": q,
        "fields": PRODUCT_SORT_FIELDS})


@admin_required
def product_edit(request, pk=None):
    instance = get_object_or_404(Product, pk=pk) if pk else None
    form = ProductForm(request.POST or None, instance=instance)
    props = PropertyFormSet(request.POST or None, instance=instance, prefix="props")
    imgs = ImageFormSet(request.POST or None, instance=instance, prefix="imgs")
    if request.method == "POST" and form.is_valid() and props.is_valid() and imgs.is_valid():
        product = form.save()
        props.instance = imgs.instance = product
        props.save()
        imgs.save()
        log_action(request.current_user, "admin_save_product", f"/panel/products/{product.id}/")
        messages.success(request, "Товар сохранён")
        return redirect("panel_products")
    return render(request, "panel/product_form.html", {"form": form, "props": props,
                                                       "imgs": imgs, "obj": instance})


@admin_required
@require_POST
def product_delete(request, pk):
    get_object_or_404(Product, pk=pk).delete()
    log_action(request.current_user, "admin_delete_product", f"/panel/products/{pk}/")
    messages.success(request, "Товар удалён")
    return redirect("panel_products")


@admin_required
def users(request):
    return render(request, "panel/users.html", {"users": User.objects.order_by("id")})


@admin_required
@require_POST
def user_action(request, pk):
    target = get_object_or_404(User, pk=pk)
    if target.pk == request.current_user.pk:
        messages.error(request, "Нельзя изменять самого себя")
        return redirect("panel_users")
    act = request.POST.get("act")
    if act == "delete":
        target.delete()                      # каскадно удалятся отзывы, действия, сессии
        messages.success(request, "Пользователь удалён")
    elif act in ("user", "admin"):
        target.role = act
        target.save(update_fields=["role"])
        messages.success(request, "Роль изменена")
    return redirect("panel_users")


@admin_required
def feedback(request):
    status = request.GET.get("status", "")
    qs = Feedback.objects.select_related("user")
    if status in dict(Feedback.STATUSES):
        qs = qs.filter(status=status)
    return render(request, "panel/feedback.html", {"items": qs, "statuses": Feedback.STATUSES,
                                                   "status": status})


@admin_required
@require_POST
def feedback_action(request, pk):
    fb = get_object_or_404(Feedback, pk=pk)
    if request.POST.get("act") == "delete":
        fb.delete()
    elif request.POST.get("status") in dict(Feedback.STATUSES):
        fb.status = request.POST["status"]
        fb.save(update_fields=["status"])
    messages.success(request, "Готово")
    return redirect("panel_feedback")
