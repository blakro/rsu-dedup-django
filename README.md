# rsu-dedup-django

Démonstrateur technique accompagnant une candidature de consultant national
« Développement de bases de données » à l'UNICEF Niger (RSU / RRM).

Le projet reprend en Django la chaîne construite dans le dépôt
[`kobo-rsu-niger`](https://github.com/blakro/kobo-rsu-niger) : import des
soumissions KoBoToolbox, rapprochement d'identité des ménages, arbitrage
humain des doublons.

**Contrainte dominante : le code doit être défendable en entretien
technique.** Toute abstraction que l'auteur ne pourrait pas expliquer de
mémoire est un défaut, pas une qualité.

## Règle non négociable

**Aucune fusion automatique de ménages.** Le service de rapprochement
produit des `PaireSuspecte` avec un score et des motifs ; il ne modifie
jamais un `Menage`. Le changement de statut d'une paire est un acte humain,
tracé, réversible.

Une fusion erronée exclut un ayant droit d'un transfert monétaire, alors
qu'un doublon non détecté coûte un versement en trop : l'asymétrie penche
du côté du contrôle humain.

## Contenu

- Django 5.x, SQLite, pas de conteneur.
- Une seule app : `registre`, quatre modèles (`Commune`, `Menage`, `Membre`,
  `PaireSuspecte`).
- Deux commandes de gestion : `importer_kobo` (lit un export CSV KoBo) et
  `rapprocher` (calcule les paires suspectes).
- Un service : [`registre/services/rapprochement.py`](registre/services/rapprochement.py)
  — normalisation des noms, blocage, scoring pondéré sur 100 (seuil 55).
- Deux vues : liste des paires suspectes, écran d'arbitrage d'une paire.
- Admin Django activé sur les quatre modèles.
- Tests sur la normalisation et le scoring (`registre/tests.py`).

## Installation

Python 3.10+ requis (Django 5.x). Le dépôt inclut un
[`.devcontainer`](.devcontainer/devcontainer.json) prêt pour GitHub
Codespaces (Python 3.12, migrations générées et appliquées automatiquement
à la création du conteneur).

```bash
pip install -r requirements.txt
python manage.py migrate
```

## Jeu de données de démonstration

```bash
python manage.py loaddata registre/fixtures/communes_demo.json
python manage.py importer_kobo demo/menages_demo.csv
python manage.py rapprocher
python manage.py runserver
```

Puis ouvrir `http://127.0.0.1:8000/` pour la liste des paires suspectes.

Le jeu de données ([`demo/menages_demo.csv`](demo/menages_demo.csv)) contient
six ménages illustrant les trois comportements attendus du rapprochement :

- **Garba Fati** et **Garba Halima** (coépouses : même nom, même village,
  même téléphone, concessions à ~1,5 m) remontent au-dessus du seuil et
  forment une paire suspecte ;
- **Issoufou Moussa** et **Issoufou Abdou** (frères du même village, écart
  d'âge de 15 ans) restent sous le seuil : aucune paire ;
- **Moussa Ibrahim** (Agadez) et **Moussa Ibrahim** (Diffa) sont des
  homonymes stricts mais ne sont jamais comparés, faute de bloc commun
  (communes différentes).

## Tests

```bash
python manage.py test registre
```

Priorité à la normalisation et au scoring, cœur métier du projet et sujet le
plus probable en entretien : gémination des consonnes, racines onomastiques
zarma/haoussa, particules Ag/Ould/El, seuil de 55, blocage par commune.

## Intégration continue

Un workflow GitHub Actions ([`.github/workflows/ci.yml`](.github/workflows/ci.yml))
génère les migrations, les applique, exécute `manage.py check`, la suite de
tests, puis importe le jeu de données de démonstration et vérifie que les
deux vues répondent — à chaque push sur `master`.

## Hors périmètre

Volontairement absents de ce démonstrateur : Django REST Framework, Celery,
Redis, Docker, PostgreSQL, authentification personnalisée, framework CSS
compilé, signals, middleware sur mesure, système de permissions granulaire.

Ce sont des extensions plausibles pour une mise en production réelle du
RSU, pas des besoins de ce démonstrateur :

- **PostgreSQL** deviendrait nécessaire au-delà de quelques dizaines de
  milliers de ménages (verrouillage en écriture concurrente sous SQLite).
- **DRF** aurait du sens pour exposer le rapprochement à une application
  mobile de terrain (saisie hors-ligne, synchronisation).
- **Celery + Redis** permettraient de lancer `rapprocher` en tâche de fond
  sur la table complète, plutôt qu'en commande bloquante.
- **Authentification et permissions granulaires** seraient indispensables
  dès que plusieurs agents arbitrent en parallèle, pour tracer qui a le
  droit de faire quoi (aujourd'hui, `arbitre_par` est une simple saisie
  libre, sans contrôle d'identité).
- **Docker** faciliterait le déploiement multi-environnements une fois
  PostgreSQL introduit.

## Limites connues du rapprochement

- La table de variantes onomastiques (`RACINES`) couvre les formes les plus
  fréquentes en zarma et haoussa. Elle est incomplète pour le tamasheq, le
  kanouri et le peul, et doit être enrichie campagne après campagne.
- Le blocage par commune fait manquer les doublons inter-communaux, cas
  fréquent chez les personnes déplacées. Une passe complémentaire bloquée
  sur le seul couple téléphone/numéro de pièce serait nécessaire.
- Le seuil de 55 est repris tel quel de `kobo-rsu-niger` ; à recalibrer sur
  les premières centaines de fiches réelles.

Pondérations et justification détaillées : [`scoring.md`](scoring.md).
