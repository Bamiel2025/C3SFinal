# C3S Climate Lab — v2

Application web pédagogique pour découvrir le climat avec les **données réelles
ERA5** (Copernicus Climate Data Store / C3S), reconstruite en FastAPI +
JavaScript sans Streamlit : graphiques interactifs, cartes, et **12 activités
séquencées en une question par étape**, corrigées avec les valeurs mesurées.

- Données : ERA5, moyennes mensuelles **1991-2020** (normale OMM), série
  continue **1940-2026** (2026 partielle : relevés jusqu'à août ; les activités
  restent calées sur 1940-2024).
- Langue de l'interface : français.
- Attribution obligatoire : *Generated using Copernicus Climate Change Service
  information 2024 (C3S/CAMS)* — elle est affichée dans l'application.

## Fonctionnalités

| Module | Ce qu'il fait |
| --- | --- |
| **Accueil** | Page simple pour les élèves : présentation, 3 chiffres clés, accès rapide. Aucune information technique. |
| **Explorateur** | Climatogramme, diagramme ombrothermique, série annuelle + tendance, anomalies, comparaison de deux périodes de 30 ans, pour 31 villes et 6 variables. |
| **Activités** | 12 fiches séquencées en **4 étapes**, chacune ouverte par une **consigne unique** (verbe d'action + livrable), avec piste, durée et **deux documents à interprimer** (graphique principal + carte, schéma ou second graphique sur les étapes 3-4). Les corrigés ne s'affichent qu'avec le **code enseignant**. La fiche *jours de chaleur* (données journalières) est suspendue en attendant `scripts/prepare_data.py heat`. |
| **Sujet type brevet** | Les activités *Paris se réchauffe-t-il vraiment ?* et *El Niño* comportent en plus un **sujet type DNB** : contexte, 3 documents (graphiques, tableaux), 4 questions de difficulté croissante pour **16 points en 25 min**, corrigés verrouillés. |
| **Cartes** | 6 cartes statiques ERA5 (température janvier/juillet, précipitations janvier/juillet, pression janvier, vent + flèches). |
| **Aide · prof** | Réservée au professeur (**code enseignant requis**) : sources, unités, état des fichiers pré-calculés, diagnostic de la clé CDS. |

## Structure

```
c3s2/            application FastAPI (config, CDS, séries, analyses, cartes, activités)
api/index.py     point d'entrée Vercel (adapte c3s2.server:app)
run_local.py     serveur de développement (uvicorn)
public/          frontend statique (index.html, assets/js, assets/maps, assets/geo)
scripts/         préparation des données (villes, cartes, chaleur journalière)
data/            CSV pré-calculés, cache CDS, journaux
tests/           pytest (API + cohérence chiffrée des corrigés)
```

## Démarrage local

```bash
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux : source .venv/bin/activate
pip install -r requirements.txt

copy .env.example .env          # puis coller votre jeton CDS
python run_local.py             # http://127.0.0.1:8000
```

Variables d'environnement (fichier `.env` ou *Environment Variables* sur
Vercel) :

| Variable | Rôle | Défaut |
| --- | --- | --- |
| `CDSAPI_URL` | Endpoint du CDS | `https://cds.climate.copernicus.eu/api` |
| `CDSAPI_KEY` | Jeton CDS (**jamais renvoyé par l'API**, seul `a4b4…d32f** est exposé) | — |
| `C3S2_TEACHER_CODE` | Code qui déverrouille les corrigés | `2027` |

### Obtenir une clé CDS

1. Créer un compte sur <https://cds.climate.copernicus.eu>.
2. Ouvrir <https://cds.climate.copernicus.eu/api-clients> puis
   *Set up the CDS API personal access token*.
3. Coller le jeton dans `CDSAPI_KEY`.

## Préparation des données

Les données affichées proviennent de fichiers **pré-calculés** (aucun appel CDS
nécessaire à l'affichage) :

```bash
python scripts/prepare_data.py cities    # 31 villes, température + précipitations
python scripts/prepare_maps.py           # 6 cartes statiques (≈ 2 min)
python scripts/prepare_data.py heat      # journalier tmax/tmin (activité canicule)
powershell -File scripts/prepare_all.ps1 # tout d'un coup
```

`prepare_maps.py` écrit les cartes dans `public/assets/maps/` (CDN) **et**
synchronise une copie dans `data/static_maps/` : le dossier `public/` n'étant
pas visible des fonctions déployées (Vercel), l'API (`/api/places`,
`/api/maps`) bascule automatiquement sur cette copie versionnée — l'accueil
et la page Cartes affichent toujours 6 cartes, sans appel CDS.

> **Blocage connu :** `derived-era5-single-levels-daily-statistics` renvoie
> `403 — Conditions d'utilisation non acceptées` tant que les conditions du
> jeu de données ne sont pas acceptées dans le navigateur :
> <https://cds.climate.copernicus.eu/datasets/derived-era5-single-levels-daily-statistics>.
> Après acceptation, relancer `python scripts/prepare_data.py heat`.
> L'application affiche alors un message français explicite à la place d'une
> erreur brute.

Les cartes et séries restent utilisables en l'absence de données journalières :
seule l'activité *Compter les jours de chaleur* est concernée.

Données particulières (déjà versionnées, à régénérer seulement si besoin) :

- `data/precomputed/nino34_sst.csv` — température mensuelle de la mer en
  surface moyennée sur la boîte Niño 3.4 (5° N–5° S, 170° O–120° O),
  1991 à mi-2026, téléchargée du jeu mensuel ERA5 (variable
  `sea_surface_temperature`, ajoutée à `c3s2/datasets.py`).
- `public/assets/schemas/courants_atlantique.png` — **schéma pédagogique
  simplifié** des courants (Gulf Stream, Labrador) et des vents d'ouest,
  dessiné par `scripts/build_activities.py` : le CDS ne fournit pas de
  courants, la fiche et l'application le signalent explicitement.
- `public/assets/situation/*.png` — **cartes de localisation** dessinées par
  `scripts/build_activities.py` avec un contexte régional (côtes, frontières,
  mers voisines) tracé depuis Natural Earth 50 m (`data/maps/ne_50m_*`,
  repli sur 110 m si les fichiers 50 m sont absents).

## Fiches d'activités autonomes (HTML + PDF)

Le dossier `public/activites/` contient les **12 fiches projetables et
imprimables**, chacune dans un fichier HTML unique (CSS, JavaScript,
graphiques et cartes inclus — aucune connexion requise une fois le fichier
téléchargé) :

- `index.html` — sommaire des 12 fiches ;
- `<clé>.html` — fiche élève : questions, pistes, graphiques et cartes
  (chaque activité propose **deux documents à interpréter**, le second
  affiché sous le graphique principal aux étapes 3-4) ;
- `pdf/<clé>.pdf` — version imprimable élève (sans corrigé) ;
- `corriges/<clé>-corrige.pdf` — version enseignant (corrigés inclus),
  volontairement **hors de `public/`** : aucun hébergeur statique ne la sert.
  Depuis le serveur : `/api/corriges/<clé>-corrige.pdf?code=2027` (403 sans
  le bon code enseignant).

Les corrigés sont embarqués **chiffrés** dans chaque fiche : ils n'apparaissent
ni à l'écran ni dans le code source tant que le **code enseignant (2027)**
n'est pas saisi. Le code est mémorisé par le navigateur ; le bouton
*Verrouiller* le réinitialise. Les fiches *rechauffement* et *elnino*
portent en plus la section **Sujet type brevet** (documents, questions et
corrigés verrouillés de la même façon).

Régénérer les fiches après modification des données ou des corrigés :

```bash
python scripts/build_activities.py            # les 12 fiches + sommaire
python scripts/build_activities.py --keys latitude,pluies_europe
```

Puis, serveur local lancé (`python run_local.py`), générer les PDF avec
Playwright (`C:\Users\brice\.agents\skills\playwright`, script
`pw-export-pdf.js` via `node run.js`) : chaque fiche est imprimée verrouillée
(élève) puis déverrouillée au code 2027 (enseignant).

## Tests

```bash
pytest -q
```

Trois familles : contrat de l'API (`/api/*`, SPA, fichiers statiques) ;
**cohérence chiffrée des corrigés** — les valeurs citées dans les corrigés sont
recalculées à partir des CSV (amplitudes Brest/Strasbourg/Marseille, totaux
Marseille/Dakar, tendance de Paris…) ; et **charte de rédaction** — les 48
consignes doivent commencer par un verbe d'action, poser au plus une question,
ne jamais livrer la réponse, et les sujets type brevet doivent passer la
grille qualité (contexte ≥ 180 signes, 3 documents rendables, 4 questions,
barème cohérent, tableau recalculé depuis les données, corrigés masqués sans
code). Un corrigé qui contredit les données fait échouer la suite de tests.

## Déploiement sur Vercel

1. Pousser le dépôt (`.env` est ignoré : ne jamais le committer) :
   `git remote add origin https://github.com/Bamiel2025/C3SFinal.git && git push -u origin main`.
2. Sur <https://vercel.com> → *Add New → Project* → importer le dépôt.
   Aucun *Framework Preset*, aucun *Build Command* : `vercel.json` s'en charge.
3. *Project Settings → Environment Variables* : renseigner `CDSAPI_URL`,
   `CDSAPI_KEY`, `C3S2_TEACHER_CODE`.
4. Déployer.

Notes :

- `public/` est servi en statique, `api/index.py` en fonction Python
  (`maxDuration: 300` dans `vercel.json`).
- Le système de fichiers Vercel est **en lecture seule** : les CSV de
  `data/precomputed/` sont donc versionnés et livrés avec le déploiement ;
  les appels CDS en direct n'écrivent rien (cache mémoire).
- Plan Hobby : la durée maximale d'exécution peut être plafonnée à 60 s ;
  les routes longues (`/api/field`, `/api/cds/test` en mode profond) peuvent
  alors expirer sans remettre en cause l'explorateur ni les cartes.

## Licence et données

Code : libre d'utilisation en contexte pédagogique.
Données : ERA5 © Copernicus / ECMWF, licence **CC BY 4.0**, attribution
obligatoire (déjà affichée dans l'application).
