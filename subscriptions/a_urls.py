from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("signup/", views.signup, name="signup"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("analytics/", views.analytics, name="analytics"),
    path("add-subscription/", views.add_sub, name="add_sub"),
    path("delete-account/", views.delete_acc, name="delete_account"),
    path("register-gmail/", views.register, name="register_gmail"),
    path("google/callback/", views.google_callback, name="google_callback"),
    path("remove-gmail/", views.remove_gmail , name="remove_gmail"),
]