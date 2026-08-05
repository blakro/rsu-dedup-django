from django.contrib import admin

from .models import Commune, Menage, Membre, PaireSuspecte


@admin.register(Commune)
class CommuneAdmin(admin.ModelAdmin):
    list_display = ["code", "nom", "departement", "region"]
    search_fields = ["code", "nom"]
    list_filter = ["region", "departement"]


class MembreInline(admin.TabularInline):
    model = Membre
    extra = 0


@admin.register(Menage)
class MenageAdmin(admin.ModelAdmin):
    list_display = ["submission_id", "nom_chef", "prenom_chef", "commune", "village", "date_import"]
    search_fields = ["submission_id", "nom_chef", "prenom_chef", "cle_menage"]
    list_filter = ["commune", "sexe"]
    inlines = [MembreInline]


@admin.register(Membre)
class MembreAdmin(admin.ModelAdmin):
    list_display = ["nom_complet", "menage", "lien_parente", "age"]
    search_fields = ["nom_complet"]


@admin.register(PaireSuspecte)
class PaireSuspecteAdmin(admin.ModelAdmin):
    list_display = ["menage_a", "menage_b", "score", "statut", "date_arbitrage"]
    list_filter = ["statut"]
