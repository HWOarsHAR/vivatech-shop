from django.urls import path

from . import views_api as api, views_pages as pages, views_panel as panel, views_legal as legal

urlpatterns = [
    # ----- страницы -----
    path("", pages.index, name="index"),
    path("product/<int:pk>/", pages.product_detail, name="product"),
    path("search/", pages.search_page, name="search"),
    path("register/", pages.register_page, name="register"),
    path("login/", pages.login_page, name="login"),
    path("feedback/", pages.feedback_page, name="feedback"),
    path("profile/", pages.profile_page, name="profile"),
    path("cart/", pages.cart_page, name="cart"),
    path("privacy/", legal.legal_page, {"slug": "privacy"}, name="privacy"),
    path("terms/", legal.legal_page, {"slug": "terms"}, name="terms"),
    path("docs/<slug:slug>.<str:fmt>", legal.legal_download, name="legal_download"),

    # ----- API (Задание 6) -----
    path("api/register", api.register),
    path("api/login", api.login),
    path("api/logout", api.logout),
    path("api/token/refresh", api.refresh),
    path("api/profile", api.profile),
    path("api/profile/password", api.change_password),
    path("api/feedback", api.feedback),
    path("api/search", api.search),
    path("api/actions", api.actions),
    path("api/cart", api.cart),
    path("api/orders", api.orders),

    # ----- админ-панель -----
    path("panel/", panel.dashboard, name="panel"),
    path("panel/products/", panel.products, name="panel_products"),
    path("panel/products/new/", panel.product_edit, name="panel_product_new"),
    path("panel/products/<int:pk>/", panel.product_edit, name="panel_product_edit"),
    path("panel/products/<int:pk>/delete/", panel.product_delete, name="panel_product_delete"),
    path("panel/users/", panel.users, name="panel_users"),
    path("panel/users/<int:pk>/", panel.user_action, name="panel_user_action"),
    path("panel/feedback/", panel.feedback, name="panel_feedback"),
    path("panel/feedback/<int:pk>/", panel.feedback_action, name="panel_feedback_action"),
]
