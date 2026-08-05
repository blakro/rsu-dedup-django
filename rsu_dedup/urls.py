"""Configuration des URLs du projet rsu_dedup."""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("registre.urls")),
]
