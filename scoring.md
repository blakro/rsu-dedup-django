# Note méthodologique

## 1. Score de vulnérabilité du formulaire

Le formulaire calcule un `score_vulnerabilite` sur 148 points, réparti en cinq
blocs : démographie (50), habitat et WASH (27), actifs (24), sécurité
alimentaire (35), choc et déplacement (12).

**Ce score n'est pas un PMT.** Un *proxy means test* opérationnel se dérive
d'une régression de la consommation des ménages sur des variables observables,
estimée à partir d'une enquête de référence — au Niger, l'ECVMA puis l'EHCVM
de l'INS. Les coefficients en sortent, ils ne se décrètent pas.

L'indice implémenté ici est un **indice additif transparent**, construit pour
trois usages :

- rendre le formulaire immédiatement utilisable en atelier de test ;
- donner à l'agent un retour visuel qui l'oblige à relire la fiche ;
- servir de tri provisoire tant que les coefficients officiels ne sont pas
  intégrés.

Les seuils (30 / 50 / 70) sont arbitraires et calés pour produire une
distribution lisible, non pour reproduire un taux de pauvreté connu.

**Avant tout usage réel :** remplacer le bloc `s8_score` par les coefficients du
modèle retenu par le dispositif national, et ne recalculer le score qu'au niveau
central — jamais sur le terminal. Un score affiché sur l'appareil devient un
score négociable avec le répondant, et donc manipulable.

### Ciblage catégoriel maintenu à part

Trois situations déclenchent une prise en charge indépendamment du score, et
sont donc isolées dans des variables dédiées plutôt que noyées dans le total :

- `nb_mas > 0` — malnutrition aiguë sévère, référencement CRENAS immédiat ;
- `nb_non_scolarises > 0` — enfant de 6 à 17 ans hors école ;
- `statut_residence` en PDI, réfugié ou retourné.

## 2. Pondérations de la déduplication

`dedup_menages.py` produit un score de 0 à 100 :

| Signal | Points | Justification |
|---|---|---|
| Similarité du nom | 0-30 | Le patronyme est stable, mais très partagé dans un village |
| Similarité du prénom | 0-25 | Discriminant seulement combiné au nom |
| Téléphone identique | +20 | Fort, mais un téléphone se partage entre coépouses |
| Numéro de pièce identique | +20 | Le signal le plus fiable quand la pièce existe |
| Écart d'âge ≤ 1 an | +10 | |
| Écart d'âge de 2 à 3 ans | +6 | Compatible avec un âge estimé, courant en milieu rural |
| Écart d'âge > 8 ans | −12 | |
| Concessions à moins de 150 m | +12 | |
| Concessions à plus de 15 km | −15 | |
| Même village | +5 | |
| Sexe différent | −25 | |

Seuil par défaut : 55. À recalibrer sur les premières centaines de fiches en
mesurant le taux de faux positifs sur un échantillon arbitré à la main.

**Aucune fusion automatique.** En protection sociale, une fusion erronée exclut
un ayant droit d'un transfert monétaire ; un doublon non détecté coûte un
versement en trop. L'asymétrie est nette, et elle penche du côté du contrôle
humain.

### Cas qu'aucun algorithme ne tranche

Deux coépouses d'un ménage polygame déclarant chacune un ménage : même
patronyme, même concession, même téléphone. C'est mécaniquement un doublon fort
au sens du score, et c'est parfois une situation légitime — les deux unités de
consommation peuvent être réellement distinctes. Le script les fait remonter,
la validation communautaire tranche. C'est exactement la raison pour laquelle
le paramètre `cm_nb_epouses` est collecté.

## 3. Limites connues

- La table de variantes onomastiques (`RACINES`) couvre les formes les plus
  fréquentes en zarma et haoussa. Elle est incomplète pour le tamasheq, le
  kanouri et le peul, et doit être enrichie campagne après campagne.
- Le blocage par commune fait manquer les doublons inter-communaux, cas
  fréquent chez les déplacés. Prévoir une passe complémentaire bloquée sur le
  seul couple téléphone / numéro de pièce.
- La corruption d'encodage UTF-8 en amont (accents transformés en séquences
  parasites) casse la normalisation avant qu'elle ne commence. Le contrôle
  d'encodage doit se faire à l'import, pas au rapprochement.
