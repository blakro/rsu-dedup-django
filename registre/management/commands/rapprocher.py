"""Commande de gestion : rapprocher.

Calcule les scores de rapprochement entre ménages d'un même bloc (commune +
squelette consonantique du nom + sexe) et enregistre les paires dont le
score dépasse le seuil comme PaireSuspecte. Ne modifie jamais un Menage.
"""

from django.core.management.base import BaseCommand

from registre.services.rapprochement import rapprocher_menages


class Command(BaseCommand):
    help = "Calcule les paires de ménages suspectées d'être des doublons."

    def handle(self, *args, **options):
        nb_paires = rapprocher_menages()
        self.stdout.write(self.style.SUCCESS(
            f"Rapprochement terminé : {nb_paires} nouvelle(s) paire(s) suspecte(s)."
        ))
