"""Commande de gestion : importer_kobo.

Lit un export CSV de soumissions KoBoToolbox et crée ou met à jour les
ménages et leurs membres correspondants.

Les champs dérivés du ménage (nom_normalise, prenom_normalise, cle_blocage)
sont calculés à l'import, pas à la volée, via le service de rapprochement
(registre/services/rapprochement.py).

La commune de chaque ménage doit déjà exister en base (via l'admin ou un
fixture) : cet import ne crée pas de Commune.

Format attendu : une colonne par champ simple du ménage (submission_id,
nom_chef, commune_code, ...) et, pour les membres, des colonnes indexées
membre_1_nom_complet, membre_1_lien_parente, ... membre_N_*, une ligne CSV
par ménage.
"""

import csv
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from registre.models import Commune, Menage, Membre
from registre.services.rapprochement import renseigner_champs_derives

# Nombre maximal de membres pris en charge par ménage dans l'export CSV
# (colonnes membre_1_*, membre_2_*, ... membre_N_*).
NB_MAX_MEMBRES = 30

FORMAT_DATE_SOUMISSION = "%Y-%m-%d %H:%M:%S"


def _lire_entier(valeur):
    valeur = (valeur or "").strip()
    return int(valeur) if valeur.lstrip("-").isdigit() else None


def _lire_decimal(valeur):
    valeur = (valeur or "").strip()
    return valeur or None


def _lire_booleen(valeur):
    return (valeur or "").strip().lower() in {"1", "true", "vrai", "oui"}


def _lire_date(valeur):
    valeur = (valeur or "").strip()
    if not valeur:
        return None
    try:
        return datetime.strptime(valeur, FORMAT_DATE_SOUMISSION)
    except ValueError:
        return None


class Command(BaseCommand):
    help = "Importe les ménages et leurs membres depuis un export CSV KoBoToolbox."

    def add_arguments(self, parser):
        parser.add_argument("chemin_csv", type=str, help="Chemin du fichier CSV à importer.")

    def handle(self, *args, **options):
        chemin_csv = options["chemin_csv"]

        try:
            fichier = open(chemin_csv, newline="", encoding="utf-8")
        except OSError as erreur:
            raise CommandError(f"Impossible de lire {chemin_csv} : {erreur}")

        nb_crees = nb_maj = nb_ignores = 0

        with fichier:
            lecteur = csv.DictReader(fichier)
            for ligne in lecteur:
                with transaction.atomic():
                    menage, cree, ignore = self._importer_menage(ligne)
                    if ignore:
                        nb_ignores += 1
                        continue
                    nb_crees += 1 if cree else 0
                    nb_maj += 0 if cree else 1
                    self._importer_membres(menage, ligne)

        self.stdout.write(self.style.SUCCESS(
            f"Import terminé : {nb_crees} ménage(s) créé(s), "
            f"{nb_maj} mis à jour, {nb_ignores} ignoré(s)."
        ))

    def _importer_menage(self, ligne):
        submission_id = (ligne.get("submission_id") or "").strip()
        code_commune = (ligne.get("commune_code") or "").strip()

        if not submission_id:
            self.stderr.write(self.style.WARNING("Ligne ignorée : submission_id manquant."))
            return None, False, True

        try:
            commune = Commune.objects.get(code=code_commune)
        except Commune.DoesNotExist:
            self.stderr.write(self.style.WARNING(
                f"Ligne ignorée ({submission_id}) : commune inconnue « {code_commune} »."
            ))
            return None, False, True

        menage, cree = Menage.objects.update_or_create(
            submission_id=submission_id,
            defaults={
                "cle_menage": (ligne.get("cle_menage") or "").strip(),
                "nom_chef": (ligne.get("nom_chef") or "").strip(),
                "prenom_chef": (ligne.get("prenom_chef") or "").strip(),
                "surnom": (ligne.get("surnom") or "").strip(),
                "sexe": (ligne.get("sexe") or "").strip().upper(),
                "age": _lire_entier(ligne.get("age")),
                "situation_matrimoniale": (ligne.get("situation_matrimoniale") or "").strip(),
                "nb_epouses": _lire_entier(ligne.get("nb_epouses")),
                "type_piece": (ligne.get("type_piece") or "").strip(),
                "num_piece": (ligne.get("num_piece") or "").strip(),
                "telephone": (ligne.get("telephone") or "").strip(),
                "telephone_alt": (ligne.get("telephone_alt") or "").strip(),
                "commune": commune,
                "village": (ligne.get("village") or "").strip(),
                "latitude": _lire_decimal(ligne.get("latitude")),
                "longitude": _lire_decimal(ligne.get("longitude")),
                "taille_declaree": _lire_entier(ligne.get("taille_declaree")),
                "statut_residence": (ligne.get("statut_residence") or "").strip(),
                "score_vulnerabilite": _lire_decimal(ligne.get("score_vulnerabilite")),
                "code_enqueteur": (ligne.get("code_enqueteur") or "").strip(),
                "date_soumission": _lire_date(ligne.get("date_soumission")),
            },
        )
        renseigner_champs_derives(menage)
        menage.save(update_fields=["nom_normalise", "prenom_normalise", "cle_blocage"])
        return menage, cree, False

    def _importer_membres(self, menage, ligne):
        menage.membres.all().delete()

        membres = []
        for indice in range(1, NB_MAX_MEMBRES + 1):
            prefixe = f"membre_{indice}_"
            nom_complet = (ligne.get(f"{prefixe}nom_complet") or "").strip()
            if not nom_complet:
                continue
            membres.append(Membre(
                menage=menage,
                rang=indice,
                nom_complet=nom_complet,
                lien_parente=(ligne.get(f"{prefixe}lien_parente") or "").strip(),
                sexe=(ligne.get(f"{prefixe}sexe") or "").strip().upper(),
                age=_lire_entier(ligne.get(f"{prefixe}age")),
                scolarise=_lire_booleen(ligne.get(f"{prefixe}scolarise")),
                handicap=_lire_booleen(ligne.get(f"{prefixe}handicap")),
                perimetre_brachial=_lire_decimal(ligne.get(f"{prefixe}perimetre_brachial")),
                oedemes=_lire_booleen(ligne.get(f"{prefixe}oedemes")),
                mas=_lire_booleen(ligne.get(f"{prefixe}mas")),
            ))

        if membres:
            Membre.objects.bulk_create(membres)
