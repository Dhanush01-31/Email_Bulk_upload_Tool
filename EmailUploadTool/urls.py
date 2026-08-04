from django.contrib import admin
from django.urls import path,include
from App import views

handler404 = "App.views.custom_404"
handler500 = "App.views.custom_500"

urlpatterns = [
    path('admin/', admin.site.urls),
    path("",include('App.urls'))
]
