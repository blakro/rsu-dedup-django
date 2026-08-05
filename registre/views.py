"""Vues d'arbitrage des paires suspectes.

Deux écrans : la liste des paires à traiter, et l'écran de comparaison
côte à côte d'une paire. Le changement de statut est le seul effet de bord
autorisé ici — jamais de modification d'un Menage (voir CLAUDE.md, section
« Règle métier non négociable »). Pas d'authentification dans ce
démonstrateur : l'agent renseigne son identifiant à chaque arbitrage, comme
code_enqueteur le fait déjà à l'import.
"""

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import PaireSuspecte

# Champs comparés côte à côte sur l'écran d'arbitrage, dans l'ordre d'affichage.
CHAMPS_COMPARES = [
    ("nom_chef", "Nom du chef"),
    ("prenom_chef", "Prénom du chef"),
    ("surnom", "Surnom"),
    ("sexe", "Sexe"),
    ("age", "Âge"),
    ("situation_matrimoniale", "Situation matrimoniale"),
    ("nb_epouses", "Nombre d'épouses"),
    ("type_piece", "Type de pièce"),
    ("num_piece", "Numéro de pièce"),
    ("telephone", "Téléphone"),
    ("telephone_alt", "Téléphone secondaire"),
    ("commune", "Commune"),
    ("village", "Village"),
    ("taille_declaree", "Taille déclarée"),
    ("statut_residence", "Statut de résidence"),
    ("code_enqueteur", "Enquêteur"),
    ("date_soumission", "Date de soumission"),
]

# Les trois boutons de l'écran d'arbitrage. "à revoir" ramène la paire en
# attente : ce n'est pas un statut à part, mais un aveu explicite et tracé
# qu'aucune décision n'a pu être prise.
ACTIONS_VERS_STATUT = {
    "doublon_confirme": PaireSuspecte.Statut.DOUBLON_CONFIRME,
    "menages_distincts": PaireSuspecte.Statut.MENAGES_DISTINCTS,
    "a_revoir": PaireSuspecte.Statut.EN_ATTENTE,
}


def liste_paires(request):
    statut = request.GET.get("statut", "")
    paires = PaireSuspecte.objects.select_related("menage_a", "menage_a__commune", "menage_b", "menage_b__commune")
    if statut:
        paires = paires.filter(statut=statut)

    contexte = {
        "paires": paires.order_by("-score"),
        "statut_actif": statut,
        "statuts": PaireSuspecte.Statut.choices,
    }
    return render(request, "registre/liste_paires.html", contexte)


def arbitrage(request, pk):
    paire = get_object_or_404(
        PaireSuspecte.objects.select_related("menage_a__commune", "menage_b__commune"), pk=pk
    )

    if request.method == "POST":
        return _traiter_arbitrage(request, paire)

    champs = [
        {
            "libelle": libelle,
            "valeur_a": getattr(paire.menage_a, champ),
            "valeur_b": getattr(paire.menage_b, champ),
            "divergent": getattr(paire.menage_a, champ) != getattr(paire.menage_b, champ),
        }
        for champ, libelle in CHAMPS_COMPARES
    ]

    contexte = {
        "paire": paire,
        "champs": champs,
        "membres_a": paire.menage_a.membres.all(),
        "membres_b": paire.menage_b.membres.all(),
    }
    return render(request, "registre/arbitrage.html", contexte)


def _traiter_arbitrage(request, paire):
    nouveau_statut = ACTIONS_VERS_STATUT.get(request.POST.get("action"))
    if nouveau_statut is None:
        messages.error(request, "Action inconnue.")
        return redirect("registre:arbitrage", pk=paire.pk)

    arbitre_par = request.POST.get("arbitre_par", "").strip()
    if not arbitre_par:
        messages.error(request, "Merci d'indiquer votre identifiant avant de valider.")
        return redirect("registre:arbitrage", pk=paire.pk)

    paire.statut = nouveau_statut
    paire.arbitre_par = arbitre_par
    paire.commentaire = request.POST.get("commentaire", "").strip()
    paire.date_arbitrage = timezone.now()
    paire.save(update_fields=["statut", "arbitre_par", "commentaire", "date_arbitrage"])

    messages.success(request, f"Paire #{paire.pk} enregistrée : {paire.get_statut_display()}.")
    return redirect("registre:liste_paires")
