"""Service de rapprochement des ménages.

Porte la logique de scripts/dedup_menages.py (dépôt kobo-rsu-niger) :
normalisation des noms, blocage par commune + squelette consonantique +
sexe, scoring pondéré sur 100. Pondérations reprises telles quelles depuis
scoring.md (dépôt d'origine).

Aucune fusion automatique : ce service ne fait jamais que lire des Menage et
écrire des PaireSuspecte. Le changement de statut d'une paire reste un acte
humain (voir CLAUDE.md, section « Règle métier non négociable »).
"""

import re
import unicodedata
from difflib import SequenceMatcher
from itertools import combinations
from math import atan2, cos, radians, sin, sqrt

from django.db.models import Q

from registre.models import Menage, PaireSuspecte

# --- Normalisation des noms -------------------------------------------------

# Particules onomastiques retirées lors de la normalisation (Ag Mohamed ->
# Mohamed), pour ne pas pénaliser un patronyme composé par comparaison à sa
# forme simple.
PARTICULES = {"ag", "ould", "el"}

# Table de variantes onomastiques zarma/haoussa. Volontairement minimale et
# incomplète (cf. scoring.md, « Limites connues ») : à enrichir campagne
# après campagne plutôt que de prétendre à l'exhaustivité.
RACINES = {
    "mahamadou": "mohamed",
    "mahamane": "mohamed",
    "mohammed": "mohamed",
    "mamadou": "mohamed",
}

VOYELLES = "aeiouy"


def _sans_accents(valeur):
    forme_decomposee = unicodedata.normalize("NFKD", valeur)
    return "".join(c for c in forme_decomposee if not unicodedata.combining(c))


def _reduire_geminees(valeur):
    """Réduit les consonnes géminées à une seule occurrence (Abdoullaye ->
    Abdoulaye), sans toucher aux voyelles doublées."""
    return re.sub(r"([^aeiouy])\1+", r"\1", valeur)


def normaliser_nom(valeur):
    """Normalise un nom ou un prénom pour la comparaison de doublons :
    minuscules, sans accents ni apostrophes, particules Ag/Ould/El retirées,
    consonnes géminées réduites, ramené à sa racine onomastique si RACINES la
    répertorie."""
    if not valeur:
        return ""

    tokens = valeur.split()
    tokens_sans_particules = [t for t in tokens if _sans_accents(t.lower()) not in PARTICULES]
    tokens_utiles = tokens_sans_particules or tokens

    tokens_normalises = []
    for token in tokens_utiles:
        forme = _sans_accents(token.lower())
        forme = forme.replace("'", "").replace("’", "")
        forme = _reduire_geminees(forme)
        forme = RACINES.get(forme, forme)
        tokens_normalises.append(forme)

    return " ".join(tokens_normalises).strip()


def squelette_consonantique(nom_normalise):
    """Retire les voyelles et espaces d'un nom déjà normalisé, pour une clé
    de blocage insensible aux variations vocaliques."""
    return "".join(c for c in nom_normalise if c not in VOYELLES and c != " ")


def calculer_cle_blocage(code_commune, nom_normalise, sexe):
    """Clé de blocage : commune + squelette consonantique du nom + sexe."""
    return f"{code_commune}|{sexe}|{squelette_consonantique(nom_normalise)}"


def renseigner_champs_derives(menage):
    """Calcule et affecte (sans sauvegarder) nom_normalise, prenom_normalise
    et cle_blocage à partir des champs bruts du ménage. À appeler avant
    chaque sauvegarde d'un Menage, à l'import comme au backfill."""
    menage.nom_normalise = normaliser_nom(menage.nom_chef)
    menage.prenom_normalise = normaliser_nom(menage.prenom_chef)
    menage.cle_blocage = calculer_cle_blocage(menage.commune_id, menage.nom_normalise, menage.sexe)


# --- Scoring -----------------------------------------------------------------
# Pondérations reprises telles quelles depuis scoring.md (dépôt d'origine).

POINTS_NOM_MAX = 30
POINTS_PRENOM_MAX = 25
POINTS_TELEPHONE_IDENTIQUE = 20
POINTS_PIECE_IDENTIQUE = 20
POINTS_ECART_AGE_FAIBLE = 10
POINTS_ECART_AGE_MODERE = 6
POINTS_ECART_AGE_FORT = -12
POINTS_PROXIMITE_FORTE = 12
POINTS_PROXIMITE_FAIBLE = -15
POINTS_MEME_VILLAGE = 5
POINTS_SEXE_DIFFERENT = -25

ECART_AGE_FAIBLE_MAX = 1
ECART_AGE_MODERE_MIN = 2
ECART_AGE_MODERE_MAX = 3
ECART_AGE_FORT_MIN = 8

DISTANCE_PROXIMITE_FORTE_M = 150
DISTANCE_PROXIMITE_FAIBLE_M = 15_000
RAYON_TERRE_M = 6_371_000

SEUIL_SCORE = 55


def _similarite(a, b):
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _telephones_communs(menage_a, menage_b):
    numeros_a = {n for n in (menage_a.telephone, menage_a.telephone_alt) if n}
    numeros_b = {n for n in (menage_b.telephone, menage_b.telephone_alt) if n}
    return bool(numeros_a & numeros_b)


def _distance_metres(lat1, lon1, lat2, lon2):
    phi1, phi2 = radians(float(lat1)), radians(float(lat2))
    delta_phi = radians(float(lat2) - float(lat1))
    delta_lambda = radians(float(lon2) - float(lon1))
    a = sin(delta_phi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(delta_lambda / 2) ** 2
    return RAYON_TERRE_M * 2 * atan2(sqrt(a), sqrt(1 - a))


def calculer_score(menage_a, menage_b):
    """Calcule le score de rapprochement entre deux ménages et les motifs qui
    le justifient. Ne modifie jamais les ménages comparés."""
    score = 0
    motifs = []

    similarite_nom = _similarite(menage_a.nom_normalise, menage_b.nom_normalise)
    points_nom = round(similarite_nom * POINTS_NOM_MAX)
    if points_nom:
        score += points_nom
        motifs.append(f"nom similaire à {similarite_nom:.0%} (+{points_nom})")

    similarite_prenom = _similarite(menage_a.prenom_normalise, menage_b.prenom_normalise)
    points_prenom = round(similarite_prenom * POINTS_PRENOM_MAX)
    if points_prenom:
        score += points_prenom
        motifs.append(f"prénom similaire à {similarite_prenom:.0%} (+{points_prenom})")

    if _telephones_communs(menage_a, menage_b):
        score += POINTS_TELEPHONE_IDENTIQUE
        motifs.append(f"téléphone identique (+{POINTS_TELEPHONE_IDENTIQUE})")

    if menage_a.num_piece and menage_a.num_piece == menage_b.num_piece:
        score += POINTS_PIECE_IDENTIQUE
        motifs.append(f"numéro de pièce identique (+{POINTS_PIECE_IDENTIQUE})")

    if menage_a.age is not None and menage_b.age is not None:
        ecart_age = abs(menage_a.age - menage_b.age)
        if ecart_age <= ECART_AGE_FAIBLE_MAX:
            score += POINTS_ECART_AGE_FAIBLE
            motifs.append(f"âges très proches, écart {ecart_age} an(s) (+{POINTS_ECART_AGE_FAIBLE})")
        elif ECART_AGE_MODERE_MIN <= ecart_age <= ECART_AGE_MODERE_MAX:
            score += POINTS_ECART_AGE_MODERE
            motifs.append(f"âges proches, écart {ecart_age} ans (+{POINTS_ECART_AGE_MODERE})")
        elif ecart_age > ECART_AGE_FORT_MIN:
            score += POINTS_ECART_AGE_FORT
            motifs.append(f"écart d'âge important, {ecart_age} ans ({POINTS_ECART_AGE_FORT})")

    if (
        menage_a.latitude is not None and menage_a.longitude is not None
        and menage_b.latitude is not None and menage_b.longitude is not None
    ):
        distance = _distance_metres(menage_a.latitude, menage_a.longitude, menage_b.latitude, menage_b.longitude)
        if distance < DISTANCE_PROXIMITE_FORTE_M:
            score += POINTS_PROXIMITE_FORTE
            motifs.append(f"concessions à {distance:.0f} m (+{POINTS_PROXIMITE_FORTE})")
        elif distance > DISTANCE_PROXIMITE_FAIBLE_M:
            score += POINTS_PROXIMITE_FAIBLE
            motifs.append(f"concessions distantes de {distance / 1000:.1f} km ({POINTS_PROXIMITE_FAIBLE})")

    if menage_a.village and menage_a.village.strip().lower() == (menage_b.village or "").strip().lower():
        score += POINTS_MEME_VILLAGE
        motifs.append(f"même village (+{POINTS_MEME_VILLAGE})")

    if menage_a.sexe != menage_b.sexe:
        score += POINTS_SEXE_DIFFERENT
        motifs.append(f"sexe différent ({POINTS_SEXE_DIFFERENT})")

    score = max(0, min(100, score))
    return score, motifs


# --- Blocage et parcours ------------------------------------------------------


def _backfill_champs_derives():
    """Renseigne les champs dérivés des ménages importés avant l'existence de
    ce service (cle_blocage encore vide). Idempotent."""
    a_mettre_a_jour = []
    for menage in Menage.objects.filter(cle_blocage="").iterator():
        renseigner_champs_derives(menage)
        a_mettre_a_jour.append(menage)
    if a_mettre_a_jour:
        Menage.objects.bulk_update(a_mettre_a_jour, ["nom_normalise", "prenom_normalise", "cle_blocage"])


def _comparer_bloc(menages):
    paires = []
    for menage_1, menage_2 in combinations(menages, 2):
        score, motifs = calculer_score(menage_1, menage_2)
        if score < SEUIL_SCORE:
            continue
        menage_a, menage_b = (menage_1, menage_2) if menage_1.pk < menage_2.pk else (menage_2, menage_1)
        paires.append(PaireSuspecte(
            menage_a=menage_a,
            menage_b=menage_b,
            score=score,
            motifs="; ".join(motifs),
        ))
    return paires


def rapprocher_menages():
    """Parcourt les ménages bloc par bloc (commune + squelette consonantique
    + sexe) et enregistre les paires suspectes au-dessus du seuil.

    Reste linéaire en nombre de blocs : la comparaison quadratique ne porte
    que sur les ménages d'un même bloc, jamais sur la table entière. Un
    homonyme dans un autre bloc (autre commune, par exemple) n'est jamais
    comparé, faute de bloc commun.

    Idempotent : rejouer la commande n'écrase pas l'arbitrage déjà fait sur
    une paire existante. On exclut explicitement les paires déjà en base
    avant l'insertion plutôt que de compter sur ignore_conflicts, qui ne
    permet pas de savoir combien de lignes ont réellement été ajoutées sur
    SQLite (nécessaire pour renvoyer un nombre de *nouvelles* paires exact).
    """
    _backfill_champs_derives()

    candidats = []
    bloc_courant = None
    menages_du_bloc = []

    menages = Menage.objects.exclude(cle_blocage="").order_by("cle_blocage").iterator()
    for menage in menages:
        if menage.cle_blocage != bloc_courant:
            candidats.extend(_comparer_bloc(menages_du_bloc))
            bloc_courant = menage.cle_blocage
            menages_du_bloc = []
        menages_du_bloc.append(menage)
    candidats.extend(_comparer_bloc(menages_du_bloc))

    nouvelles_paires = _exclure_paires_existantes(candidats)
    PaireSuspecte.objects.bulk_create(nouvelles_paires, ignore_conflicts=True)
    return len(nouvelles_paires)


def _exclure_paires_existantes(candidats):
    if not candidats:
        return []

    condition = Q()
    for paire in candidats:
        condition |= Q(menage_a_id=paire.menage_a_id, menage_b_id=paire.menage_b_id)
    couples_existants = set(PaireSuspecte.objects.filter(condition).values_list("menage_a_id", "menage_b_id"))

    return [p for p in candidats if (p.menage_a_id, p.menage_b_id) not in couples_existants]
