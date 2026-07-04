# ⛓ OSIN Chain Quebec Ultimate v3.0 — Nocturne

> **"There is no lock."** — **ghost1o1**

Moteur de **chaîne OSINT récursive** : 17 core engines + 12 modules OSINT + 5 niveaux de profondeur. Vraies sources HTTP (ip-api, GitHub, DDG, HIBP, RDAP, Telegram, Gravatar). Dashboard Nocturne + FastAPI backend.

```
OSIN Chain Quebec Ultimate v3.0
   ╔═══════════════════════════════════════╗
   ║  12 MODULES · 17 ENGINES · 5-DEPTH   ║
   ║  REAL HTTP · NEO4J OPTIONAL · NOCTURNE║
   ╚═══════════════════════════════════════╝
```

## ⚡ Aperçu

| Spec | Valeur |
|------|--------|
| **Version** | 3.0 "Nocturne" |
| **Dashboard** | 24 KB (single-file) |
| **Backend** | FastAPI + uvicorn |
| **Modules** | 12 OSINT (4099 lignes) |
| **Core** | 17 engines (3107 lignes) |
| **Compatibilité** | Kali / Debian / Ubuntu / macOS / Termux |

## 🎯 12 OSINT modules

1. **Phone Intel** — NANP + carrier + reverse lookup
2. **Email Tracer** — GitHub commits + Gravatar + HIBP
3. **Username Sherlock** — 25+ platform HTTP checks
4. **IP Tracker** — Geo + ASN + ISP + reverse DNS
5. **Domain Mapper** — DNS + MX + NS + subdomains
6. **Breach Hunter** — HIBP k-anon + leak corpora
7. **Doc Analyzer** — PDF/Office metadata
8. **Name Resolver** — Name → handle platforms
9. **Geoloc Intel** — Reverse geocode + timezone
10. **Social Graph** — Cross-platform relations
11. **Image Deepscan** — EXIF + reverse image
12. **Darkweb Scout** — Tor .onion + paste + breach

## 🎯 17 core engines

`chain_engine` · `dispatcher` · `graph_manager` · `correlation_v2` · `footprint` · `geo` · `movement` · `tasks` · `rate_limiter` · `logger` · `neo4j_manager` · `face_service` · `exporters` · `correlation` + 3 autres.

## 📦 Installation

Voir [INSTALL.md](INSTALL.md).

Quick start :
```bash
git clone https://github.com/187Ghost101/quebec-ultimate.git
cd quebec-ultimate/quebec-ultimate
chmod +x install.sh
./install.sh
python3 main.py
# Backend FastAPI : http://localhost:8000
# Ouvre nocturne.html dans navigateur
```

## 📖 Utilisation

Voir [USAGE.md](USAGE.md).

### Workflow
1. Dashboard → **Dashboard** panel
2. Query : type (email/phone/username/IP/domain) + value
3. Max depth : 1-5 (cascade récursive)
4. **RUN CHAIN** → cascade exécute 1+ modules
5. Résultats : entities + relations + chain steps
6. Export : JSON / HTML / Neo4j Cypher

## 🔒 Usage autorisé uniquement

⚠️ OSIN Chain Quebec est destiné à la **recherche OSINT éthique** et **red team autorisé**. Respecte RGPD + scope écrit.

## 📂 Structure

```
quebec-ultimate/
├── main.py                # FastAPI entry
├── config.py              # Config
├── api/                   # Routes FastAPI
├── core/                  # 17 engines
│   ├── chain_engine.py
│   ├── dispatcher.py
│   ├── graph_manager.py
│   ├── correlation_v2.py
│   └── ... (13 autres)
├── modules/               # 12 OSINT
│   ├── phone_intel.py
│   ├── email_tracer.py
│   ├── username_sherlock.py
│   └── ... (9 autres)
├── frontend/              # Existing FastAPI frontend (Leaflet+Cytoscape)
├── nocturne.html          # 24 KB — Nocturne brand layer
├── ghost1o1.{css,js}      # design system
├── install.sh
├── requirements.txt
├── README.md
├── INSTALL.md
├── USAGE.md
└── GHOST1O1_BRAND.md
```

---

**© 2026 ghost1o1 · GHOST1O1 Nocturne v1.1**
