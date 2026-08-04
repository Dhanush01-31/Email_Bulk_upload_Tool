from django.urls import path
from .views import *
urlpatterns = [
    path("",home, name="home"),
    path("login/",login_view, name="login"),
    path("register/",register_view, name="register"),
    path("logout/",logout_view, name="logout"),
    path("dashboard/",dashboard, name="dashboard"),
    path(
        "send-bulk-email/",
        send_bulk_email_view,
        name="send_bulk_email",
    ),
     path(
        "email-logs/",
        email_logs,
        name="email_logs"
    ),
     path(
        "download-template/",
        download_template,
        name="download_template",
    ),
     
    path('supply_chain/',supply_chain,name='supply_chain')
]