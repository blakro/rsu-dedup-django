"""Modèles du registre RSU.

Aucune fusion automatique de ménages : le rapprochement produit des
PaireSuspecte avec un score et des motifs, jamais une modification directe
d'un Menage. Le changement de statut d'une paire est un acte humain, tracé
et réversible (voir CLAUDE.md, section « Règle métier non négociable »).
Une fusion erronée exclut un ayant droit d'un transfert monétaire, alors
qu'un doublon non détecté coûte un versement en trop : l'asymétrie penche
du côté du contrôle humain.
"""

from django.db import models

SEXE_CHOICES = [
    ("M", "Masculin"),
    ("F", "Féminin"),
]


class Commune(models.Model):
    """Découpage administratif nigérien, chargé depuis data/communes.csv."""

    code = models.CharField(max_length=20, primary_key=True)
    nom = models.CharField(max_length=100)
    departement = models.CharField(max_length=100)
    region = models.CharField(max_length=100)

    class Meta:
        verbose_name = "commune"
        verbose_name_plural = "communes"
        ordering = ["region", "departement", "nom"]

    def __str__(self):
        return f"{self.nom} ({self.code})"


class Menage(models.Model):
    """Ménage enquêté, importé depuis une soumission KoBoToolbox."""

    # Identifiants KoBo
    submission_id = models.CharField(max_length=100, unique=True)
    cle_menage = models.CharField(max_length=100, blank=True)

    # Chef de ménage
    nom_chef = models.CharField(max_length=100)
    prenom_chef = models.CharField(max_length=100)
    surnom = models.CharField(max_length=100, blank=True)
    sexe = models.CharField(max_length=1, choices=SEXE_CHOICES)
    age = models.PositiveSmallIntegerField(null=True, blank=True)
    situation_matrimoniale = models.CharField(max_length=50, blank=True)
    nb_epouses = models.PositiveSmallIntegerField(null=True, blank=True)

    # Pièce d'identité
    type_piece = models.CharField(max_length=50, blank=True)
    num_piece = models.CharField(max_length=50, blank=True)

    # Contact
    telephone = models.CharField(max_length=20, blank=True)
    telephone_alt = models.CharField(max_length=20, blank=True)

    # Localisation
    commune = models.ForeignKey(Commune, on_delete=models.PROTECT, related_name="menages")
    village = models.CharField(max_length=100, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    # Ciblage
    taille_declaree = models.PositiveSmallIntegerField(null=True, blank=True)
    statut_residence = models.CharField(max_length=50, blank=True)
    score_vulnerabilite = models.FloatField(null=True, blank=True)

    # Traçabilité
    code_enqueteur = models.CharField(max_length=50, blank=True)
    date_soumission = models.DateTimeField(null=True, blank=True)
    date_import = models.DateTimeField(auto_now_add=True)

    # Champs dérivés stockés, calculés à l'import (pas à la volée) par le
    # service de rapprochement — registre/services/rapprochement.py.
    # Laissés vides tant que ce service n'existe pas (soirée 2 du CLAUDE.md) ;
    # cle_blocage est indexée car elle sert de clé de partitionnement au
    # rapprochement (commune + squelette consonantique + sexe).
    nom_normalise = models.CharField(max_length=150, blank=True, db_index=True)
    prenom_normalise = models.CharField(max_length=150, blank=True, db_index=True)
    cle_blocage = models.CharField(max_length=50, blank=True, db_index=True)

    class Meta:
        verbose_name = "ménage"
        verbose_name_plural = "ménages"
        ordering = ["-date_import"]

    def __str__(self):
        return f"{self.nom_chef} {self.prenom_chef} ({self.submission_id})"


class Membre(models.Model):
    """Membre d'un ménage, rattaché au chef par un lien de parenté."""

    menage = models.ForeignKey(Menage, on_delete=models.CASCADE, related_name="membres")
    rang = models.PositiveSmallIntegerField()
    nom_complet = models.CharField(max_length=150)
    lien_parente = models.CharField(max_length=50)
    sexe = models.CharField(max_length=1, choices=SEXE_CHOICES)
    age = models.PositiveSmallIntegerField(null=True, blank=True)
    scolarise = models.BooleanField(null=True, blank=True)
    handicap = models.BooleanField(default=False)

    # Indicateurs nutritionnels (dépistage lors de l'enquête)
    perimetre_brachial = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    oedemes = models.BooleanField(default=False)
    mas = models.BooleanField(default=False, verbose_name="malnutrition aiguë sévère")

    class Meta:
        verbose_name = "membre"
        verbose_name_plural = "membres"
        ordering = ["menage", "rang"]

    def __str__(self):
        return f"{self.nom_complet} ({self.lien_parente})"


class PaireSuspecte(models.Model):
    """Paire de ménages jugés potentiellement en doublon par le rapprochement.

    Le service de rapprochement se contente d'enregistrer cette paire avec
    un score et des motifs ; il ne modifie jamais un Menage. Le statut n'est
    changé que par un arbitrage humain (écran d'arbitrage, soirée 3).
    """

    class Statut(models.TextChoices):
        EN_ATTENTE = "en_attente", "En attente"
        DOUBLON_CONFIRME = "doublon_confirme", "Doublon confirmé"
        MENAGES_DISTINCTS = "menages_distincts", "Ménages distincts"

    menage_a = models.ForeignKey(Menage, on_delete=models.CASCADE, related_name="paires_comme_a")
    menage_b = models.ForeignKey(Menage, on_delete=models.CASCADE, related_name="paires_comme_b")
    score = models.PositiveSmallIntegerField()
    motifs = models.TextField(blank=True)
    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.EN_ATTENTE)
    arbitre_par = models.CharField(max_length=100, blank=True)
    date_arbitrage = models.DateTimeField(null=True, blank=True)
    commentaire = models.TextField(blank=True)

    class Meta:
        verbose_name = "paire suspecte"
        verbose_name_plural = "paires suspectes"
        ordering = ["-score"]
        constraints = [
            # Empêche d'enregistrer deux fois la même paire (A, B) et (B, A).
            models.UniqueConstraint(fields=["menage_a", "menage_b"], name="paire_couple_unique"),
            # Impose l'ordre canonique menage_a < menage_b, condition dont
            # dépend l'unicité ci-dessus pour être réellement effective.
            models.CheckConstraint(
                check=models.Q(menage_a__lt=models.F("menage_b")),
                name="paire_ordre_menages",
            ),
        ]

    def __str__(self):
        return f"{self.menage_a_id} / {self.menage_b_id} — score {self.score}"
