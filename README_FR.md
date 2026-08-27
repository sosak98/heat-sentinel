# 🔥 HEATSENTINEL — Urban Heat Intelligence, prouvé sur données réelles

**IA agentique de mesure, de prévision et d'action face à la chaleur urbaine**,
construite sur la **FortyGuard Temperature API®** pour le **Hackathon'26 —
Building the World's Temperature AI**.

> *« De la donnée à 2 mètres du sol à l'action en 60 secondes. »*

---

## 1. Le problème

La chaleur est le **dangers climatique le plus mortel** (≈ 2 millions de morts
prématurées/an, OMS) et le moins préparé. À **Cotonou** (~700 000 habitants
la commune, **1,5 M+ avec l'agglomération**), la chaleur humide pèse :
**ressenti > 40 °C** avec l'humidité (les max moyens de 31–32 °C sont
largement dépassés en vague de chaleur). Et il n'existe **aucun système
d'alerte précoce hyperlocal** : les bulletins météo sont trop grossiers
(l'aéroport est loin des rues), arrivent trop tôt (8 h le matin, pic à 15 h)
et personne ne traduit la prévision en **actions concrètes** (hôpital, écoles,
marchés, travailleurs extérieurs).

## 2. La solution

**HeatSentinel** est un système complet qui boucle la chaîne
**Monitor → Predict → Decide → Act** :

| Couche | Quoi |
|---|---|
| 📡 **Data** | 20 **points de mesure du maillage Temperature API®** (résolution 20 m², température modélisée à 2 m du sol — le maillage est celui de FortyGuard, **nous n'installons aucun capteur**) sur les zones clés : port/industriel, centres denses, plage (brise maritime) |
| 🧠 **AI core** | **Modèle hybride** (composante de tendances linéaires Ridge + LightGBM) : nowcast du **pic de température 6 heures à l'avance** par point — **Cotonou : MAE 0,26 °C, R² 0,95** · **Phoenix : MAE 0,46 °C, R² 0,99** (hold-out 24 h, ~2 Mo). + **z-score 48 h** (simple, seuil \|z\| ≥ 2,5) : anomalies — micro-pics locaux, dérives capteur |
| 🤖 **Agent** | Moteur de politique **transparent** (pas de black box, pas de dépendance LLM) : déduplication, escalade uniquement, registre d'audit JSONL, alertes **FR + fon** (+ EN) avec **actions concrètes** |
| 📤 **Notifications** | Agent → **Twilio SMS/WhatsApp** (credentials optionnelles ; sans clés : journal local `artifacts/{ville}/notifications.jsonl`) |
| 🗺️ **Dashboard** | Carte de chaleur temps réel, jauge de risque ville, détail par nœud (24 h + nowcast), flux d'alertes, journal de l'agent — **100 % auto-suffisant (fonctionne hors-ligne)** |

**Tracks couverts (3 en 1) :** Resilient Cities & Infrastructure × Agentic AI ×
Data Analysis & Correlation.

### Angle NVIDIA (le jury est NVIDIA — Konstantin Cvetanov, AI Factories)
- **Edge-first** : modèle ~2 Mo → export **ONNX** → inférence < 10 ms sur un
  **NVIDIA Jetson** (le kit gagnant = notre premier nœud du maillage).
- **Scale** : chemin d'entraînement **RAPIDS/cuML** (GPU) quand le maillage
  passe de 20 nœuds à des millions de cellules 20 m².
- **Pipeline CUDA-X** : les features (cycle diurne, UHI, bulbe humide, tendances)
  sont vectorisées et mappables sur le traitement accéléré CUDA-X.

## 3. Démarrer (2 minutes)

```bash
# Python 3.10+
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python train.py          # 1. entraîne le modèle + génère le snapshot du dashboard
python run_server.py     # 2. dashboard + API sur http://0.0.0.0:8000
```

Le serveur sert **un site complet + la démo live** sur http://localhost:8000 :

| Page | Contenu |
|---|---|
| `/` | **Accueil** — l'histoire de Cotonou (cible de déploiement), le problème, la solution |
| `/demo` | **Démo live** — la carte de chaleur temps réel, alertes FR + fon, données réelles (mode SIMULÉ ×4 : 1 h ≈ 15 s) |
| `/how-it-works` | L'agent expliqué simplement : Observer → Prédire → Décider → Agir |
| `/real-data` | Les 60 mesures réelles Temperature API® (Phoenix, 24–26 août) + méthodologie honnête |
| `/team` | L'équipe ClimVision + ce qu'on demande après le hackathon |

> **Ville par défaut de la démo : Phoenix** (plan B — voir §4 : Cotonou n'est
> pas encore couvert par la mesh, Phoenix l'est et la démo y tourne sur
> données réelles). Cotonou (cible de déploiement) :
> `python train.py --city cotonou && HS_CITY=cotonou python run_server.py`.
>
> Le modèle s'entraîne en **< 30 s sur un laptop ordinaire** (aucun GPU requis).
> Sur Colab : `!pip install -r requirements.txt && !python train.py`.

## 4. Brancher la vraie API (dès réception de la clé trial)

La démo utilise un flux **simulé physiquement plausible** (même schéma que
l'API). Le client `backend/data/fortyguard.py` est écrit **conformément à la
doc officielle** (docs-api.fortyguard.com) :

- **Auth** : header `api-key: VOTRE_CLÉ` sur chaque requête (pas de Bearer)
- **Base URL** : `https://api.fortyguard.com`
- **Flux** : `POST /v1/heatmap` (task asynchrone) → `GET /v1/status/{id}`
  jusqu'à `Completed` → `map_data` (GeoJSON de tuiles °C) + `stats_data`
- **Capacités utilisées** : `analytic_type` `tcm` (températures),
  `time_of_measure` (heure du pic — valide notre nowcast), `exceedance`
  (heures > seuil — métrique de risque réelle), historique 2019→maintenant,
  prévisions jusqu'à +12 h (benchmark de notre modèle 6 h)

**Workflow (les crédits trial sont limités — on les consomme intelligemment)** :

```bash
export FORTYGUARD_API_KEY="votre_clé"     # ou dans .env (gitignored)

# 1. TEST DE COUVERTURE — 1 requête : est-ce que la ville est dans la mesh ?
python check_coverage.py --city cotonou    # → 0 tuiles (non couvert, vérifié 27/08)
python check_coverage.py --city phoenix    # → 37 tuiles (couvert ✓)

# 2. Récolte des jours réels (1 req par point×jour, filter_type=3, mis en cache
#    dans artifacts/{ville}/real/ — jamais re-demandé, reprise à l'identique)
python harvest.py --city phoenix --days 7

# 3. Ré-entraînement : le simulateur est recalé jour par jour sur les min/moy/max
#    RÉELS du maillage (artifacts/{ville}/fortyguard_real_daily.csv), et le
#    dashboard affiche un panneau « Données réelles — Temperature API® ».
python train.py --city phoenix
python run_server.py      # → le dashboard affiche la source "fortyguard"
```

Le client est défensif (normalise les réponses, bascule sur le mock si l'API
est indisponible) : la démo ne peut jamais tomber en panne devant le jury.

### Priorité n°1 dès réception de la clé : tester la couverture

```bash
python check_coverage.py            # 1 requête (~1 crédit) : Cotonou est-elle couverte ?
```

FortyGuard couvre surtout les US + quelques pays ; **l'Afrique n'est pas
garantie**. **Testé le 27/08 avec la clé trial — résultat** :

- **Cotonou : non couvert** (0 tuiles, fenêtre jour complète, 2 points testés)
- **Phoenix : couvert** (37 tuiles pour un polygone 600 m × 600 m, granularity 100 m ;
  Downtown 2026-08-26 : min 32,05 / moy 37,00 / max 42,92 °C réels)
- **Granularité réelle : journalière** (`filter_type=3` → min/moy/max par tuile et
  par jour ; `filter_type=1` = heure unique retourne 0 cellules)

→ **plan B activé** : la démo tourne sur **Phoenix avec données réelles**
(défaut du dépôt) et **Cotonou reste la cible de déploiement** dans le pitch —
crédible : leur propre étude Tripoli combine ERA5 + Landsat quand la mesh est
absente, c'est exactement le pattern que HeatSentinel embarque (calibration
Open-Meteo quand l'API n'est pas disponible) :

```bash
python run_server.py                    # Phoenix (défaut, plan B)
HS_CITY=cotonou python run_server.py    # Cotonou (cible de déploiement, flux simulé calibré)
```

## 5. Architecture du code

```
heat-sentinel/
├── train.py                  # entraînement one-shot (--city cotonou|phoenix)
├── run_server.py             # dashboard + API temps réel (port 8000, HS_CITY=…)
├── check_coverage.py         # TEST COUVERTURE — priorité n°1 dès réception de la clé
├── harvest.py                # récolte des données réelles FortyGuard (dès clé trial)
├── Dockerfile                # image « Jetson-ready » (vision edge, non testée sur matériel)
├── requirements.txt
├── backend/
│   ├── data/
│   │   ├── cities.py         # Cotonou + Phoenix (nœuds, climat, seuils) — plan B
│   │   ├── nodes.py          # ré-export rétrocompatible (Cotonou par défaut)
│   │   ├── mock.py           # simulateur du maillage API, calibré (multi-villes)
│   │   └── fortyguard.py     # client réel de la Temperature API® (mock sans clé)
│   ├── models/
│   │   ├── features.py       # features : diurne, UHI, bulbe humide, trends, z_hod
│   │   └── heat_risk.py      # hybride Ridge+LightGBM nowcast + z-score 48 h + scoring
│   ├── agent/
│   │   ├── sentinel.py       # boucle agentique + alertes FR/fon/EN + registre d'audit
│   │   └── notifier.py       # notifications Twilio SMS/WhatsApp (+ fallback local)
│   └── api/
│       └── server.py         # FastAPI : site multi-pages + /demo + /api/…
├── site/                     # LE SITE (multi-pages, thème clair)
│   ├── index.html            # ACCUEIL — Phoenix (vitrine 100 % données réelles), Cotonou = cible de déploiement
│   ├── how-it-works.html   # l'agent expliqué simplement (Observer→Prédire→Décider→Agir)
│   ├── real-data.html      # les 60 mesures réelles Temperature API® (Phoenix)
│   ├── team.html           # l'équipe ClimVision
│   ├── assets/               # style.css, cartes OSM intégrées (hors-ligne), realdata.js
│   └── build_maps.py         # régénère les cartes OpenStreetMap (© OSM contributors)
├── demo/
│   ├── dashboard.template.html  # dashboard (tokens SNAPSHOT + carte OSM injectés par train.py)
│   └── dashboard.html           # version avec snapshot + carte embarqués (généré, servie sur /demo)
├── edge/jetson/              # référence de déploiement edge (ONNX + capteur)
├── pitch/
│   ├── make_deck.py          # génère pitch_deck.pptx (10 slides, EN)
│   ├── pitch_deck.pptx       # le deck du jury
│   └── pitch_script.md       # script oral 3 min (FR)
└── artifacts/{ville}/        # modèles, metrics, snapshot, registres (cotonou, phoenix)
```

## 6. Méthodologie scientifique (pour le Q&A du jury)

- **Cible** : `max(T[t+1..t+6])` par nœud — horizon d'action utile pour une ville.
- **Évaluation** : hold-out **temporel** 24 h (aucun leakage : les features
  n'utilisent que le passé). **Cotonou : MAE 0,26 °C · R² 0,95 — Phoenix :
  MAE 0,46 °C · R² 0,99** (le désert est plus difficile : amplitude diurne
  ~17 °C, et le hold-out tombe sur une vraie vague de chaleur 46 °C).
- **Pourquoi un modèle hybride** : les arbres (LightGBM) ne savent pas
  extrapoler — en fin de vague de chaleur, la tendance sort de la plage
  d'entraînement et le pic est sous-estimé (surtout la nuit). Une composante
  linéaire (Ridge) sur les tendances 6 h/12 h/24 h/72 h gère l'extrapolation,
  LightGBM capture le cycle diurne et les interactions. Les deux sont
  interprétables et combinés en additif.

### Calibration du simulateur sur données réelles (Open-Meteo, gratuit, sans clé)

Le flux simulé est ancré sur des mesures réelles de Cotonou
(Open-Meteo, 21→27 août 2026) : moyenne 26,6 °C, pic après-midi ~27,6 °C,
minuit ~25,6 °C, RH ~83 %. Résultat de la validation
(`python validate.py` → `artifacts/validation_openmeteo.json`) :

| Date | Réel min/max/moy | Sim min/max/moy |
|---|---|---|
| 21/08 | 25,4 / 27,6 / 26,4 | 25,9 / 28,5 / 27,1 |
| 22/08 | 25,6 / 28,1 / 26,6 | 25,8 / 28,6 / 27,2 |
| 23/08 | 25,5 / 27,6 / 26,2 | 25,9 / 28,4 / 27,2 |
| 24/08 | 24,9 / 27,6 / 26,2 | 25,8 / 28,5 / 27,2 |
| 25/08 | 25,6 / 28,3 / 26,7 | 25,9 / 28,5 / 27,2 |
| 26/08 | 25,5 / 29,2 / 27,2 | 25,9 / 28,4 / 27,1 |

**Bias horaire : −0,63 °C** (la sim est légèrement plus chaude : 16/20 nœuds
urbains avec UHI, contre 1 point centre-ville). La vague de chaleur simulée
(+5,5 °C) correspond à un événement extrême documenté pour Cotonou
(record ~38 °C en saison chaude).

**Phoenix — double ancrage (réel + Open-Meteo).** Le flux Phoenix est ancré
(i) sur Open-Meteo réelles 21→27 août 2026 (vague de chaleur en cours :
moyenne 38,5 °C, min 29,0 / max 46,3 °C, RH jour 10–13 %) et (ii) sur les
**tuiles réelles de la Temperature API®** récoltées les 24→26/08 — 60 cellules, 3 jours × 20 points (Downtown :
min 32,05 / moy 37,00 / max 42,92 °C). À chaque jour réel disponible, la
simulation est **recalée jour par jour** sur ses min/moy/max réels
(`backend/data/real_data.py`) — c'est le même pipeline que Cotonou utilisera
dès que la mesh la couvrira.
- **Features** (19, toutes interprétables) : lags réels 24 h/48 h, moyennes
  glissantes 3–72 h, tendances, cycle diurne sin/cos, jour de semaine,
  coefficient UHI par zone, bulbe humide (Stull 2011) = proxy du ressenti.
- **Score de risque 0–100** (transparent) : `0,65·score_temp(pic 6h) +
  0,35·score_humidité` — seuils alignés sur les plans de chaleur OMS
  (28 °C neutre → 38 °C extrême). Niveaux : Faible / Vigilance / Élevé /
  Critique / Extrême.
- **Anomalies** : **z-score 48 h** — température actuelle vs sa valeur normale
  à la même heure (3 dernières occurrences), seuil \|z\| ≥ 2,5. Simple,
  transparent, interprétable : capte les micro-pics locaux ET les dérives
  de capteur.
- **Agent** : politique déterministe (dédup 6 h simulées, escalade seulement)
  → reproductible, auditable, testable. Un LLM peut être branché en option pour
  la rédaction de rapports, jamais dans la boucle de sécurité.

## 7. Déploiement — l'URL publique (~5 min, gratuit, sans carte bancaire)

L'app tourne sur n'importe quel hébergeur Python. On utilise **Render** (plan
gratuit) : il déploie directement depuis le repo GitHub, en 1 clic, via le
fichier `render.yaml` déjà dans le projet. Testé : l'app démarre **sans clé
API** (mode « calibrated » sur les 60 lectures réelles récoltées).

**Étape 1 — pousser le repo sur GitHub (depuis ton terminal) :**

1. Sur github.com → bouton **+** → **New repository** : nom `heat-sentinel`,
   **Public**, sans README → **Create repository**.
2. Dans le terminal (dossier propre, partir du zip v4) :

```bash
cd ~/Telechargements
rm -rf ~/hs-deploy && mkdir -p ~/hs-deploy
unzip heat-sentinel-v4-deploy.zip -d ~/hs-deploy
cd ~/hs-deploy/heat-sentinel

git init -b main
git add -A
git commit -m "HeatSentinel — FortyGuard Hackathon'26 (Temperature API®)"
git remote add origin https://github.com/climvision/heat-sentinel.git
git push -u origin main
```

> Si git demande le mot de passe GitHub : GitHub n'accepte plus le mot de
> passe du compte en ligne de commande. Deux solutions :
> (a) créer un token — github.com → **Settings → Developer settings →
> Personal access tokens → Generate new token** (case `repo`) — et le coller
> comme « mot de passe » ;
> (b) si l'outil `gh` est installé : `gh auth login` puis
> `gh repo create heat-sentinel --public --source . --push` remplace tout le
> bloc de commandes ci-dessus.

**Étape 2 — Render (depuis le navigateur) :**

1. [render.com](https://render.com) → **Log in with GitHub** (compte gratuit).
2. **New +** → **Blueprint** → choisir le repo `heat-sentinel` → **Apply
   blueprint**.
3. Le blueprint crée le service web `heatsentinel` (plan **free**, région
   Oregon). Attendre 2–4 min (build + démarrage).
4. L'URL (ex. `https://heatsentinel.onrender.com`) apparaît dans le dashboard
   → **c'est le lien à coller dans le formulaire de soumission**, et à
   remonter dans le README.md (ligne « Live demo ») puis `git push`.
5. **Brancher l'API réelle sur le serveur (fortement recommandé)** : dans le
   dashboard Render → service → *Environment* → **Add environment variable** :
   `FORTYGUARD_API_KEY` = ta clé trial. (La clé ne doit **jamais** être dans
   le repo — elle reste sur Render, en variable d'environnement.)

**Le « live sync » (codé dans `backend/data/livesync.py`) :**
Au démarrage du service (et à chaque réveil après endormissement, puis toutes
les 24 h), le backend **appelle lui-même la Temperature API®** : il récupère
les derniers jours réels terminés pour les 20 points, **recalibre le flux**
et **recalcule les prédictions** — sans aucune intervention. Le dashboard
affiche alors « last live sync … » et « last real day … (measured max … °C) ».

- **Coût : ~20 crédits par jour réel** (1 requête par point) — le cache rend
  les re-syncs à 0 crédit quand rien de nouveau n'est arrivé. Sur la période
  de jugement (1–15 sept) : ≈ 300 crédits au total.
- Sans clé (ou crédits épuisés) : l'app bascule proprement en mode
  « calibrated » sur les lectures déjà récoltées — **elle ne plante jamais**.
- Pour limiter le coût : variable `SYNC_HOURS` (défaut 24) ou `SYNC_HOURS=0`
  pour désactiver.

**Bon à savoir :**
- Plan gratuit : le service **s'endort après ~15 min** sans visite ; le
  premier chargement après l'endormissement prend 30–60 s. Avant une démo
  live ou l'enregistrement de la vidéo, **ouvrir l'URL une fois** et attendre.
- Chaque `git push` redéploie automatiquement le service (`autoDeploy`).
- Pour montrer la version **Cotonou** (cible de déploiement, alertes FR + fon)
  : créer un 2ᵉ service avec `HS_CITY=cotonou` (sans clé API, car Cotonou est
  hors mesh — il tournera en mode calibré Open-Meteo).

## 8. Checklist soumission

> **Deadline : dimanche 30 août.** La page officielle indique 23h59 GST
> (≈ 20h59 Bénin) ; votre email d'équipe mentionne 22h59 — dans tous les cas,
> **on vise la soumission samedi soir** pour avoir de la marge.

Fait ✓ (27/08) : clé trial reçue · couverture testée (Cotonou ❌ / Phoenix ✅) ·
récolte terminée **60/60 lectures** (24–26/08) · simulateur recalé sur les
min/moy/max réels · panneau « données réelles » dans le dashboard · site 100 %
EN Phoenix-first (4 pages) · dashboard EN · app validée sans clé API ·
**live sync codé et testé** (le backend appelle l'API à l'exécution :
démarrage + 24 h, ~20 crédits/jour, cache = 0 crédit si rien de nouveau).

- [ ] **Vendredi 28 août, 14h (Bénin) : session mentor NVIDIA (CUDA-X)** —
      le juge y est, y aller et poser une question précise
- [ ] **DÉPLOIEMENT (section 7)** : repo GitHub public → Render → URL live
- [ ] Remonter l'URL dans le README.md (ligne « Live demo ») + `git push`
- [ ] **Vidéo de démo 3 min** (après le déploiement, sur l'URL live) :
      enregistrer le dashboard pendant qu'une vague de chaleur se déclenche —
      montrer la carte OSM, le panneau **données réelles**, le nowcast 6 h,
      les alertes, le journal agentique
- [ ] Remplacer les `[Nom]` dans le pitch deck (slide 10)
- [ ] Remplir le formulaire de soumission (URL + vidéo + repo) — samedi soir

## 9. Limites honnêtes (à assumer avec confiance)

- **Cotonou n'est pas encore dans la mesh Temperature API®** (vérifié le
  27/08) : la démo Cotonou tourne sur un flux simulé calibré Open-Meteo ; la
  démo **Phoenix tourne sur des tuiles réelles récoltées** (min/moy/max
  journaliers ; la forme horaire entre jours réels est simulée). La récolte
  est en cache et reprend à l'identique — chaque nouveau jour réel ré-ancore
  le modèle.
- Le nowcast 6 h est entraîné par ville ; `train.py` l'adapte à n'importe
  quelle ville en < 30 s sur ses données.
- Le maillage Jetson est une référence de déploiement documentée ; le nœud
  physique est le 1er deliverable post-hackathon (financé par le kit gagnant).
