# MITCHÔ — Système d'Intelligence Publique pour la Sécurité Alimentaire au Bénin

> **MITCHÔ** transforme des signaux économiques, agricoles et médiatiques dispersés en analyses stratégiques claires, pour que l'État béninois décide **avant**, pas après.

---

## Sommaire

1. [Présentation du projet](#présentation-du-projet)
2. [Architecture globale](#architecture-globale)
3. [Frontend](#frontend)
4. [Backend — État actuel](#backend--état-actuel)
5. [Système RAG & GDELT](#système-rag--gdelt)
6. [Sources de données](#sources-de-données)
7. [Lancer le projet en local](#lancer-le-projet-en-local)
8. [Variables d'environnement](#variables-denvironnement)
9. [Contribuer](#contribuer)

---

## Présentation du projet

MITCHÔ est une plateforme d'intelligence publique orientée décision, conçue pour répondre à un problème structurel : **les crises alimentaires au Bénin sont détectables bien avant qu'elles deviennent visibles**, mais les signaux sont dispersés, mal connectés, et rarement transformés en recommandations actionnables pour les décideurs publics.

### Problème adressé

- Les prix vivriers fluctuent selon des dynamiques régionales, climatiques, et géopolitiques que personne ne synthétise en temps réel.
- Les signaux médiatiques (tensions sociales, blocages de routes, événements climatiques) sont ignorés des outils de suivi habituels.
- Les institutions publiques n'ont pas accès à un outil leur permettant d'**anticiper** plutôt que de réagir.

### Solution MITCHÔ

Un système en trois couches :

| Couche | Rôle |
|--------|------|
| **Collecte** | Prix WFP/HDX (CSV), événements GDELT, base locale |
| **Analyse** | Pipeline RAG (LLM Llama 3.3 + ChromaDB) — analyse, prévisions, recommandations |
| **Action** | Rapport PDF mensuel téléchargeable, chatbot IA, alertes email |

---

## Architecture globale

```
┌─────────────────────────────────────────────────────────────────────┐
│                         MITCHÔ PLATFORM                             │
├──────────────────┬──────────────────────────────────────────────────┤
│   FRONTEND       │                  BACKEND                         │
│   (Static HTML)  │          (Python / FastAPI)                      │
│                  │                                                   │
│  index.html      │   ┌──────────────┐    ┌──────────────────────┐  │
│  tendances.html  │   │  Data Layer  │    │   RAG Pipeline       │  │
│  mitcho-chat.js  │──▶│  WFP / HDX   │───▶│  GDELT Embeddings    │  │
│  mitcho-auth.js  │   │  GDELT API   │    │  LLM (Llama 3.3)     │  │
│  prices-loader.js│   │  CSV local   │    │  ChromaDB            │  │
│                  │   └──────────────┘    └──────────────────────┘  │
│                  │                                │                  │
│                  │   ┌────────────────────────────▼──────────────┐  │
│                  │   │          Report Generator                  │  │
│                  │   │        (fpdf2 → PDF binaire)               │  │
│                  │   └───────────────────────────────────────────┘  │
│                  │                                                   │
│                  │   ┌───────────────────────────────────────────┐  │
│                  │   │        Auth & Email Service                │  │
│                  │   │  (JWT + SQLite + Resend)                   │  │
│                  │   └───────────────────────────────────────────┘  │
└──────────────────┴──────────────────────────────────────────────────┘
```

---

## Frontend

### Structure des fichiers

```
mitcho-frontend/
├── index.html          # Page d'accueil : contexte, problème, solution + hero image
├── tendances.html      # Prévisions Mensuelles : prix, signaux, téléchargement PDF
├── mitcho-chat.js      # Assistant IA (chatbot flottant — backend ou Groq direct)
├── mitcho-auth.js      # Authentification (inscription, connexion, modal, JWT)
└── prices-loader.js    # Chargement dynamique des prix (backend → HDX → statique)
```

### Fonctionnalités actives

- **Page d'accueil** (`index.html`) : hero avec image de fond, contexte, problème, solution.
- **Prévisions mensuelles** (`tendances.html`) : indicateurs de prix animés, signaux détectés, recommandations, téléchargement du rapport PDF conditionnel à l'authentification.
- **Chatbot IA** : fenêtre flottante, historique de conversation. Appelle d'abord `/analysis/chat` (backend RAG) ; bascule en direct Groq si le backend est indisponible.
- **Authentification** : modal dynamique, inscription avec abonnement email optionnel, connexion, JWT stocké en sessionStorage. Fallback localStorage si backend indisponible.
- **Prix en temps réel** : chargement depuis `/prices` (backend) → HDX API → statique en dernier recours. Bouton de rafraîchissement manuel.
- **Téléchargement PDF** : appel authentifié `GET /report/pdf/stream` → blob → déclenchement navigateur.

### Technologies frontend

| Technologie | Usage |
|-------------|-------|
| HTML5 / CSS3 / JS (Vanilla) | Structure, style, interactions |
| Tailwind CSS (CDN) | Système de design, responsive |
| Google Fonts — Poppins | Typographie (pas d'italique) |
| Material Symbols (Google) | Iconographie |
| Groq API (Llama 3.3 70B) | Chatbot IA (fallback direct) |
| WFP HDX API | Prix vivriers (fallback) |

---

## Backend — État actuel

Le backend FastAPI est **entièrement fonctionnel** en développement local.

### Ce qui fonctionne aujourd'hui

| Fonctionnalité | Statut |
|----------------|--------|
| Authentification (register / login / JWT) | Opérationnel |
| Récupération des prix WFP | Opérationnel (CSV local en priorité) |
| Génération d'analyse par LLM (Groq Llama 3.3) | Opérationnel |
| Génération et téléchargement de rapport PDF | Opérationnel (~6 secondes) |
| Pipeline RAG (ChromaDB + sentence-transformers) | Actif — base vide tant que GDELT n'alimente pas |
| Ingestion GDELT automatique (scheduler) | Partiel — limité par le rate-limiting de l'API publique |
| Envoi d'emails (Resend) | Configuré — nécessite une clé Resend valide |
| Scheduler APScheduler | Actif (GDELT toutes les 6h, WFP toutes les 24h) |

### Stack technique

| Composant | Technologie | Rôle |
|-----------|------------|------|
| API Web | FastAPI + Uvicorn | Endpoints REST |
| Base de données | SQLite (aiosqlite) | Utilisateurs, sessions (dev) |
| Base vectorielle | ChromaDB (local) | Embeddings pour le RAG |
| Embeddings | `sentence-transformers` (paraphrase-multilingual-MiniLM-L12-v2) | Vectorisation des textes |
| LLM | Groq API — `llama-3.3-70b-versatile` | Analyse et génération du rapport |
| Génération PDF | fpdf2 | Rapport mensuel PDF |
| Email | Resend.com | Bienvenue + rapports mensuels |
| Scheduler | APScheduler | Ingestion automatique |
| Auth | bcrypt + python-jose (JWT) | Sessions sécurisées |
| HTTP client | httpx (async) | Appels WFP, GDELT, Groq |

### Structure backend

```
mitcho-backend/
├── main.py                  # Point d'entrée FastAPI + lifespan (startup/shutdown)
├── requirements.txt
├── .env                     # Variables d'environnement (non commité)
├── .env.example             # Template variables
├── start.ps1                # Script PowerShell de démarrage (venv + install + uvicorn)
│
├── app/
│   ├── api/
│   │   ├── auth.py          # POST /auth/register, /auth/login, GET /auth/me, /auth/subscribe
│   │   ├── prices.py        # GET /prices
│   │   ├── analysis.py      # GET /analysis/status, POST /analysis/generate, /analysis/chat
│   │   └── report.py        # POST /report/generate, GET /report/download/{f}, /report/pdf/stream
│   │
│   ├── core/
│   │   ├── config.py        # Settings (pydantic-settings, .env)
│   │   └── security.py      # bcrypt, JWT create/decode
│   │
│   ├── data/
│   │   ├── wfp_loader.py    # Fetch WFP HDX CSV (local en priorité, live en fallback)
│   │   ├── gdelt_loader.py  # Fetch GDELT API (événements Bénin)
│   │   └── scheduler.py     # APScheduler — ingestion GDELT/WFP en thread pool
│   │
│   ├── rag/
│   │   ├── embedder.py      # sentence-transformers (chargé à la demande)
│   │   ├── vector_store.py  # Interface ChromaDB (court-circuit si base vide)
│   │   ├── retriever.py     # Recherche sémantique + formatage du contexte
│   │   └── generator.py     # Prompt engineering + appel Groq
│   │
│   ├── reports/
│   │   ├── builder.py       # Orchestration : prix + analyse LLM (sans bloquer sur embedder)
│   │   └── pdf.py           # fpdf2 — mise en page PDF avec nettoyage Latin-1
│   │
│   └── email/
│       └── sender.py        # Envoi emails Resend (bienvenue, rapport mensuel)
│
└── db/
    ├── database.py          # SQLAlchemy async (aiosqlite)
    └── models.py            # User, Report, KnowledgeChunk
```

### Points techniques notables

- **CORS** : `allow_origins=["*"]` en développement pour supporter les fichiers `file://`.
- **WFP** : le CSV local (`prix_vivriers_benin_region_2020_2026.csv`) est utilisé en priorité pour éviter le re-téléchargement S3 (~60s). Le live HDX ne se déclenche que si le CSV local est absent.
- **Embedder** : `sentence-transformers` est chargé **uniquement dans le thread d'indexation** (via `run_in_executor`) — il ne bloque jamais l'event loop principal.
- **PDF** : tout le texte LLM est nettoyé (`_clean()`) pour remplacer les caractères Unicode hors Latin-1 (em-dash, guillemets typographiques, etc.) avant rendu fpdf2.

---

## Système RAG & GDELT

### Pourquoi un système RAG ?

Un **RAG (Retrieval-Augmented Generation)** est indispensable ici car :

- Le LLM seul ne connaît pas les prix de la semaine dernière à Malanville.
- Le LLM seul ne sait pas que des camions ont été bloqués à la frontière Bénin-Nigeria le 12 mai.
- Avec un RAG, on **injecte ces faits récents** dans le contexte du prompt LLM, qui raisonne alors sur des données actualisées.

### Pipeline RAG — Fonctionnement

```
1. COLLECTE (scheduler — WFP toutes les 24h, GDELT toutes les 6h)
   ├── WFP HDX → prix vivriers (CSV) → chunks texte
   └── GDELT API → événements Bénin/Afrique de l'Ouest (JSON)
       └── filtres : food, market, transport, weather, conflict

2. INDEXATION (dans un thread dédié, non bloquant)
   ├── Chaque chunk → embedding (paraphrase-multilingual-MiniLM-L12-v2)
   └── Upsert dans ChromaDB avec métadonnées (date, source, type)

3. GÉNÉRATION DE RAPPORT (sur demande — GET /report/pdf/stream)
   ├── fetch_latest_prices()  — données WFP depuis le cache ou CSV local
   ├── collection_count() == 0 ?
   │   ├── OUI → retrieve_context() retourne "" (court-circuit, pas d'embedder)
   │   └── NON → retrieval sémantique dans ChromaDB
   ├── Prompt = prix WFP + contexte RAG + instructions de structuration
   ├── Groq Llama 3.3 70B → analyse structurée (~2000-3000 tokens)
   └── fpdf2 → PDF téléchargeable

4. CHATBOT (POST /analysis/chat)
   ├── Retrieval contextuel (si KB non vide)
   └── Groq Llama 3.3 → réponse conversationnelle
```

### GDELT — État et limitations

L'API publique GDELT 2.0 (sans clé) est sujette à un rate-limiting agressif (HTTP 429) qui empêche l'ingestion fiable en développement.

**Solution prévue** : intégration d'une base GDELT locale (CSV fourni) pour alimenter le pipeline RAG sans dépendre de l'API temps réel lors des tests.

```
Endpoint GDELT : https://api.gdeltproject.org/api/v2/doc/doc
Paramètres :
  query      = "Benin food market" OR "securite alimentaire"
  mode       = artlist
  maxrecords = 50
  format     = json
  timespan   = LAST7DAYS
  sourcelang = French,English
```

---

## Sources de données

| Source | Type | Fréquence | Accès |
|--------|------|-----------|-------|
| [WFP HDX — Bénin](https://data.humdata.org/dataset/global-wfp-food-prices) | Prix vivriers par marché | Mensuel | CSV public |
| `prix_vivriers_benin_region_2020_2026.csv` | Historique prix 2020-2026 | Statique | CSV local inclus |
| [GDELT 2.0 API](https://blog.gdeltproject.org/gdelt-2-0-our-global-database-of-society/) | Événements médiatiques mondiaux | Temps réel (15 min) | API publique (rate-limited) |
| Base GDELT locale | Événements pré-filtrés Bénin | Statique | CSV fourni |
| [FEWS NET](https://fews.net/west-africa/benin) | Bulletins sécurité alimentaire | Trimestriel | RSS / HTML |
| [Open-Meteo](https://open-meteo.com/) | Données météo Bénin | Quotidien | API gratuite |

---

## Lancer le projet en local

### Pré-requis

- Python 3.10+
- Un navigateur moderne (Chrome, Firefox, Edge)
- Clé API Groq (gratuite sur [console.groq.com](https://console.groq.com))

### 1. Backend

```powershell
cd mitcho-backend

# Option A — script automatique (recommandé sur Windows)
.\start.ps1

# Option B — manuel
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt

# Configurer les variables d'environnement
copy .env.example .env
# Éditer .env : renseigner GROQ_API_KEY au minimum

# Lancer le serveur
.\.venv\Scripts\uvicorn.exe main:app --port 8000 --host 0.0.0.0

# Documentation interactive disponible sur :
# http://localhost:8000/docs
```

### 2. Frontend

```bash
# Option A — ouvrir directement (fonctionne grâce au CORS allow_origins=["*"])
start mitcho-frontend/index.html
start mitcho-frontend/tendances.html

# Option B — serveur local (recommandé)
npx serve mitcho-frontend
# Ouvrir http://localhost:3000
```

### 3. Tester le téléchargement PDF

1. Ouvrir `tendances.html` dans le navigateur
2. Cliquer sur **"Télécharger le rapport PDF"**
3. Créer un compte ou se connecter
4. Le PDF est généré (~6 secondes) et téléchargé automatiquement

---

## Variables d'environnement

Créer `.env` dans `mitcho-backend/` (ne jamais le committer) :

```env
# Base de données (SQLite pour le dev, PostgreSQL en production)
DATABASE_URL=sqlite+aiosqlite:///./mitcho.db

# Sécurité JWT
SECRET_KEY=votre_cle_secrete_jwt_longue_et_aleatoire
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# LLM — obligatoire
GROQ_API_KEY=gsk_...
GROQ_MODEL=llama-3.3-70b-versatile

# Email (optionnel)
RESEND_API_KEY=re_...
FROM_EMAIL=alertes@mitchobenin.org

# RAG / ChromaDB
CHROMA_PERSIST_DIR=./chroma_db
CHROMA_COLLECTION=mitcho_knowledge

# GDELT (API publique, pas de clé)
GDELT_MAX_RECORDS=50

# CORS (liste séparée par virgules)
ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:5500
```

---

## Contribuer

MITCHÔ est un projet d'intérêt public. Les contributions sont bienvenues dans les domaines suivants :

- Intégration de la base GDELT locale (CSV pré-filtré Bénin)
- Amélioration des prompts d'analyse (prompt engineering)
- Intégration de nouvelles sources (ANASEB, INStaD Bénin, FEWS NET)
- Amélioration du design et contenu du rapport PDF
- Traduction des analyses en langue locale (Fon, Yoruba)
- Tests et validation des prévisions avec des experts terrain
- Migration vers PostgreSQL + déploiement cloud (Render / Railway)

---

*MITCHÔ — Décider avant, pas après.*
