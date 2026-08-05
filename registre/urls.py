"""URLs de l'app registre : liste des paires suspectes et écran d'arbitrage."""

from django.urls import path

from . import views

app_name = "registre"

urlpatterns = [
    path("", views.liste_paires, name="liste_paires"),
    path("paires/<int:pk>/", views.arbitrage, name="arbitrage"),
]
