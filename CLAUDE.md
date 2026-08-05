# CLAUDE.md — rsu-dedup-django

## Contexte

Démonstrateur technique accompagnant une candidature de consultant national
« Développement de bases de données » à l'UNICEF Niger (RSU / RRM).

Le projet reprend en Django la chaîne construite dans le dépôt
`kobo-rsu-niger` : import des soumissions KoBoToolbox, rapprochement d'identité
des ménages, arbitrage humain des doublons.

**Contrainte dominante : le code doit être défendable en entretien technique.**
Toute abstraction que l'auteur ne pourrait pas expliquer de mémoire est un
défaut, pas une qualité. En cas d'arbitrage entre élégance et lisibilité,
choisir la lisibilité.

## Périmètre — ce qui est dans le projet

- Django 5.x, SQLite, pas de conteneur.
- Une seule app : `registre`.
- Quatre modèles : `Commune`, `Menage`, `Membre`, `PaireSuspecte`.
- Une commande de gestion : `importer_kobo` (lit un CSV export KoBo).
- Un service : `registre/services/rapprochement.py`.
- Deux vues : liste des paires suspectes, écran d'arbitrage d'une paire.
- Django admin activé sur les quatre modèles.
- Tests unitaires sur la normalisation des noms et le scoring.

## Périmètre — ce qui est explicitement hors sujet

Ne pas ajouter : Django REST Framework, Celery, Redis, Docker, PostgreSQL,
authentification personnalisée, Tailwind ou tout framework CSS compilé,
signals, middleware sur mesure, système de permissions granulaire.

Si une de ces briques semble nécessaire, l'écrire dans le README comme
extension possible plutôt que l'implémenter.

## Modèles — spécification

**Commune** : `code` (PK, ex. `NE006_09_01`), `nom`, `departement`,
`region`. Chargée depuis `data/communes.csv` du dépôt `kobo-rsu-niger`.

**Menage** : identifiant KoBo `submission_id` (unique), `cle_menage`,
nom et prénom du chef, `surnom`, `sexe`, `age`, `situation_matrimoniale`,
`nb_epouses`, `type_piece`, `num_piece`, `telephone`, `telephone_alt`,
FK `commune`, `village`, `latitude`, `longitude`, `taille_declaree`,
`statut_residence`, `score_vulnerabilite`, `code_enqueteur`,
`date_soumission`, `date_import`.

Champs dérivés stockés (calculés à l'import, pas à la volée) :
`nom_normalise`, `prenom_normalise`, `cle_blocage`.

**Membre** : FK `menage`, `rang`, `nom_complet`, `lien_parente`, `sexe`,
`age`, `scolarise`, `handicap`, `perimetre_brachial`, `oedemes`, `mas`.

**PaireSuspecte** : FK `menage_a`, FK `menage_b`, `score`, `motifs` (texte),
`statut` parmi `en_attente` / `doublon_confirme` / `menages_distincts`,
`arbitre_par`, `date_arbitrage`, `commentaire`.
Contrainte d'unicité sur le couple ordonné (`menage_a` < `menage_b`) pour
éviter d'enregistrer deux fois la même paire.

## Règle métier non négociable

**Aucune fusion automatique de ménages.** Le service produit des
`PaireSuspecte` avec un score et des motifs ; il ne modifie jamais un `Menage`.
Le changement de statut d'une paire est un acte humain, tracé, réversible.

Justification à conserver dans le code et le README : une fusion erronée exclut
un ayant droit d'un transfert monétaire, alors qu'un doublon non détecté coûte
un versement en trop. L'asymétrie penche du côté du contrôle humain.

## Logique de rapprochement

Porter la logique de `scripts/dedup_menages.py` du dépôt `kobo-rsu-niger` :
normalisation (accents, particules Ag / Ould / El, apostrophes, consonnes
géminées, table de variantes onomastiques zarma et haoussa), blocage par
commune + squelette consonantique + sexe, scoring pondéré sur 100, seuil à 55.

Les pondérations et leur justification sont dans `docs/scoring.md` du dépôt
d'origine. Les reprendre telles quelles, comme constantes nommées en tête de
module — jamais comme nombres magiques dans le corps des fonctions.

## Performance

Le RSU vise plusieurs centaines de milliers de ménages. Le rapprochement doit
donc rester linéaire en nombre de blocs, jamais quadratique sur la table
entière. Un `Menage.objects.all()` suivi d'une double boucle est un défaut
disqualifiant, même si le jeu de test est petit.

Attendus : `cle_blocage` indexée, itération bloc par bloc via `iterator()`,
comparaisons faites en mémoire à l'intérieur d'un bloc seulement, insertion des
paires en `bulk_create`.

## Interface

Deux gabarits, HTML et CSS écrits à la main, sans framework. Sobriété : c'est un
outil d'arbitrage pour un agent d'un dispositif national, pas une vitrine.

La vue de comparaison affiche les deux ménages côte à côte, champ par champ,
avec mise en évidence des divergences, la composition des deux ménages, et trois
boutons : doublon confirmé, ménages distincts, à revoir.

## Tests

Priorité aux tests de la normalisation, parce que c'est le cœur métier et le
sujet le plus probable en entretien :

- `Abdoullaye` et `Abdoulaye` produisent la même forme normalisée ;
- `Mahamadou` et `Mohamed` sont ramenés à la même racine ;
- `Ag Mohamed` et `Mohamed` aussi ;
- deux frères du même village restent sous le seuil ;
- deux coépouses remontent au-dessus du seuil (c'est le comportement voulu) ;
- un homonyme d'une autre région n'est pas comparé du tout, faute de bloc
  commun.

## Rythme de travail

Trois soirées, un commit fonctionnel par soirée.

1. Projet, modèles, migrations, admin, commande `importer_kobo`.
2. Service de rapprochement, commande `rapprocher`, tests.
3. Vues d'arbitrage, gabarits, README, jeu de données de démonstration.

Après chaque soirée : relire chaque fichier produit et être capable de
l'expliquer sans le rouvrir. Ce qui ne passe pas ce test est supprimé ou
réécrit plus simplement.

## Langue

Code, commentaires, noms de variables, messages de commit et documentation en
français. Les données portent sur des ménages nigériens et le dispositif
national travaille en français.
