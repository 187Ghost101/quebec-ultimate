<div align="center">

```
   ▄█████ █  ██  ▄█████ ▄█████▄  ██   ██ ▄█████ █    ██  ██ ██    ██
  ██      ██▄██  ██     ██   ██  ██▄▄▄██ ██     ██    ██  ██ ██    ██
  ██  ███ ██▀██  █████  ██████   ██   ██ █████  ██    ██  ██ ██    ██
  ██   ██ ██  ██ ██     ██   ██  ██   ██ ██      ██  ▄██  ██  ██  ██
   ▀████▀ ██  ██ ▀█████ ██   ██  ██   ██ ▀█████   ▀███▀██▄██  ▀███▀
```

![GHOST1O1](https://img.shields.io/badge/GHOST1O1-L'EVEIL_NOCTURNE-e63946?style=for-the-badge&logo=ghost&logoColor=white)
![Version](https://img.shields.io/badge/VERSION-3.0-00d4ff?style=for-the-badge)
![Status](https://img.shields.io/badge/STATUS-OPERATIONAL-2ecc71?style=for-the-badge)
![Engine](https://img.shields.io/badge/ENGINE-RECURSIVE_OSINT-9b59b6?style=for-the-badge)

# 🔍 QUEBEC ULTIMATE
## *Recursive OSINT Chain Engine*

**Pivot récursif d'OSINT : ASN → IP → domains → emails → leaks → cartographie complète.**

[Hub](https://github.com/187Ghost101/ghost1o1) · [Tutorial](https://github.com/187Ghost101/ghost1o1/blob/main/tutorials/TUTORIAL_02_CARTOGRAPHIER.md) · [SECURITY](SECURITY.md)

> *L'éveil commence par voir ce que personne ne regarde.*

</div>

---

## 🔥 C'est quoi ?

QUEBEC ULTIMATE est un **moteur de chaînage OSINT récursif**. À partir d'un point d'entrée unique (un email, un domaine, une IP, un pseudo), il pivote automatiquement à travers :

- **Whois** → registrar, contacts, dates
- **DNS** → tous les records, subdomains
- **ASN** → BGP, ranges IP, neighbours
- **Certificats** → CT logs, subdomains cachés
- **Leaks** → HIBP, dehashed.com, intelligenceX
- **Social** → LinkedIn, GitHub, Twitter pivots
- **Géolocalisation** → IP → ASN → région → data center
- **Corrélation** → graphique de relations

---

## ✨ Features

- **Chaînage récursif** : chaque résultat génère de nouvelles cibles
- **Graph viz** : visualisation des relations (D3.js)
- **Multi-source** : 15+ sources OSINT intégrées
- **Cache intelligent** : évite les requêtes redondantes
- **Rapport multi-format** : JSON, GraphML, Mermaid, HTML
- **Mode passif strict** : aucun contact direct avec la cible
- **API REST** : intégration avec d'autres outils GHOST1O1

---

## 🚀 Démarrage 60 secondes

```bash
git clone https://github.com/187Ghost101/quebec-ultimate.git
cd quebec-ultimate
bash install.sh

# Pivot depuis un email
python3 quebec.py chain --email victim@target.com --depth 3

# Pivot depuis un domaine
python3 quebec.py chain --domain target.com --depth 2

# Pivot depuis une IP
python3 quebec.py chain --ip 192.168.1.77 --depth 2

# Interface web
python3 quebec.py web --port 8088
firefox http://localhost:8088
```

---

## 🎯 Cas d'usage

### Cas 1 — Audit pre-engagement

```bash
# Input : nom de domaine du client
python3 quebec.py chain --domain client.com --depth 3 --output rapport_pre_engagement.html
```

→ Tu obtiens : tous les subdomains exposés, les leaks connus, la cartographie réseau externe, les contacts techniques, et un **graphique de relations**.

### Cas 2 — Investigation d'email

```bash
# Input : email de phishing reçu
python3 quebec.py chain --email phishing@scammer.com --depth 4
```

→ Tu obtiens : les domaines associés, les autres emails, l'infra réseau, et des pistes pour le sinkhole/disclosure.

### Cas 3 — Threat intelligence

```bash
# Input : IP d'un C2 connu
python3 quebec.py chain --ip 198.51.100.42 --depth 3
```

→ Tu obtiens : l'ASN, les autres domaines/IPs sur cet ASN, les leaks, et des **patterns** d'infra réutilisables.

---

## 🏗️ Architecture

```
quebec-ultimate/
├── core/
│   ├── chain.py          # Moteur récursif
│   ├── pivot.py          # Logique de pivot
│   └── graph.py          # Construction du graph
├── modules/
│   ├── whois.py          # Whois lookup
│   ├── dns.py            # DNS enumeration
│   ├── asn.py            # BGP/ASN
│   ├── certs.py          # CT logs
│   ├── leaks.py          # HIBP, dehashed
│   ├── social.py         # Social pivots
│   └── geo.py            # Geolocation
├── api/                  # REST API
├── frontend/             # Web UI (D3 graph viz)
├── data/                 # Cache + datasets
└── docs/                 # Methodology
```

---

## 🔐 Légalité & Éthique

**OSINT = données publiquement accessibles.** Mais :

- **Pas de scraping agressif** : respecter rate limits
- **Pas d'accès à des données payantes** sans abonnement
- **Pas de corrélation avec des données personnelles** au-delà du cadre légal
- **RGPD** : si tu es en UE, anonymise après usage

**Pour les investigations offensives :** autorisation écrite obligatoire, conservation des preuves, disclosure responsable.

📜 **[SECURITY.md](SECURITY.md)**

---

## 🤝 Contribution

Recherché :
- Nouveaux modules OSINT ( Shodan, Censys, FOFA, etc.)
- Heuristiques de corrélation
- Visualisations améliorées
- Traductions

📜 **[CONTRIBUTING.md](CONTRIBUTING.md)**

---

## 📜 Licence

**MIT License**

---

<div align="center">

**L'ÉVEIL NOCTURNE** · [ghost1o1](https://github.com/187Ghost101) — 2026

*There is no lock.*

</div>
