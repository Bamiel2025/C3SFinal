# C3S Climate Lab — v2

Application web pédagogique pour découvrir le climat avec les **données réelles
ERA5** (Copernicus Climate Data Store / C3S), reconstruite en FastAPI +
JavaScript sans Streamlit : graphiques interactifs, cartes, et **8 activités
séquencées en une question par étape**, corrigées avec les valeurs mesurées.

- Données : ERA5, moyennes mensuelles **1991-2020** (normale OMM), série
  continue **1940-2024**.
- Langue de l'interface : français.
- Attribution obligatoire : *Generated using Copernicus Climate Change Service
  information 2024 (C3S/CAMS)* — elle est affichée dans l'application.

## Fonctionnalités

| Module | Ce qu'il fait |
| --- | --- |
| **Accueil** | État des données, de la clé CDS, accès rapide aux activités. |
| **Explorateur** | Climatogramme, diagramme ombrothermique, série annuelle + tendance, anomalies, comparaison de deux périodes de 30 ans, pour 31 villes et 6 variables. |
| **Activités** | 10 fiches (une question par étape, indice, durée, graphique associé). Les corrigés ne s'affichent qu'avec le **code enseignant**. La fiche *jours de chaleur* (données journalières) est suspendue en attendant `scripts/prepare_data.py heat`. |
| **Cartes** | 6 cartes statiques ERA5 (température janvier/juillet, précipitations janvier/juillet, pression janvier, vent + flèches). |
| **Aide** | Sources, unités, état des fichiers pré-calculés, diagnostic de la clé CDS. |

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

> **Blocage connu :** `derived-era5-single-levels-daily-statistics` renvoie
> `403 — Conditions d'utilisation non acceptées` tant que les conditions du
> jeu de données ne sont pas acceptées dans le navigateur :
> <https://cds.climate.copernicus.eu/datasets/derived-era5-single-levels-daily-statistics>.
> Après acceptation, relancer `python scripts/prepare_data.py heat`.
> L'application affiche alors un message français explicite à la place d'une
> erreur brute.

Les cartes et séries restent utilisables en l'absence de données journalières :
seule l'activité *Compter les jours de chaleur* est concernée.

## Fiches d'activités autonomes (HTML + PDF)

Le dossier `public/activites/` contient les **10 fiches projetables et
imprimables**, chacune dans un fichier HTML unique (CSS, JavaScript,
graphiques et cartes inclus — aucune connexion requise une fois le fichier
téléchargé) :

- `index.html` — sommaire des 10 fiches ;
- `<clé>.html` — fiche élève : questions, pistes, graphiques et cartes ;
- `pdf/<clé>.pdf` — version imprimable élève (sans corrigé) ;
- `pdf/<clé>-corrige.pdf` — version enseignant (corrigés inclus).

Les corrigés sont embarqués **chiffrés** dans chaque fiche : ils n'apparaissent
ni à l'écran ni dans le code source tant que le **code enseignant (2027)**
n'est pas saisi. Le code est mémorisé par le navigateur ; le bouton
*Verrouiller* le réinitialise.

Régénérer les fiches après modification des données ou des corrigés :

```bash
python scripts/build_activities.py            # les 10 fiches + sommaire
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

Deux familles : contrat de l'API (`/api/*`, SPA, fichiers statiques) et
**cohérence chiffrée des corrigés** — les valeurs citées dans les corrigés sont
recalculées à partir des CSV (amplitudes Brest/Strasbourg/Marseille, totaux
Marseille/Dakar, tendance de Paris…). Un corrigé qui contredit les données fait
échouer la suite de tests.

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
