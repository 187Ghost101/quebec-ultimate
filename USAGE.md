# 🎮 OSIN Chain Quebec v3.0 — Guide d'utilisation

> 12 modules · 17 engines · chain cascade · multi-export.

## 🎯 Premier lancement

```bash
# Terminal 1 : backend FastAPI
cd quebec-ultimate/quebec-ultimate
python3 main.py

# Terminal 2 : dashboard
python3 -m http.server 8090
firefox http://localhost:8090/nocturne.html
```

## 🧭 Navigation dashboard Nocturne

### 14 panels (sidebar)

**Modules** :
1. Dashboard (défaut)
2. Phone Intel
3. Email Tracer
4. Username Sherlock
5. IP Tracker
6. Domain Mapper
7. Breach Hunter
8. Face Match
9. Darkweb Scout

**Output** :
10. Chain Engine
11. Live Stream
12. Graph
13. Report
14. About

### Raccourcis
| Touche | Action |
|--------|--------|
| `1-9` | Switch panel |
| `?` | Help |

## 🎯 Les 12 modules OSINT

### 1. Phone Intel
```bash
# Dashboard
Panel Phone Intel → +14155552671 → RESOLVE

# API
curl -X POST http://localhost:8000/phone \
  -H 'Content-Type: application/json' \
  -d '{"phone":"+14155552671"}'
```

Output : Country · Area · Carrier · Line type · Timezone

### 2. Email Tracer
```bash
# Dashboard
Panel Email → torvalds@linux.foundation → TRACE
```

Output :
- MX records
- GitHub commits count
- Gravatar hash
- HIBP breaches count
- Web mentions count

### 3. Username Sherlock
```bash
Panel Username → octocat → SHERLOCK
```

Teste 25+ plateformes : GitHub · Twitter · Reddit · Instagram · HackerNews · Medium · Dev.to · StackOverflow · GitLab · Keybase · etc.

### 4. IP Tracker
```bash
Panel IP → 8.8.8.8 → TRACK
```

Output : Country · Region · City · ISP · ASN · Reverse DNS · Open ports

### 5. Domain Mapper
```bash
Panel Domain → github.com → MAP
```

Output : A · MX · NS · TXT · Subdomains

### 6. Breach Hunter
```bash
Panel Breach → test@example.com → HUNT
```

Output : Liste breaches (LinkedIn 2012, Adobe 2013, Canva 2019, etc.)

### 7. Doc Analyzer
```bash
# API
curl -X POST http://localhost:8000/doc/analyze \
  -F 'file=@document.pdf'
```

Output : Metadata (author, created, modified, software, GPS si présent)

### 8. Name Resolver
```bash
Panel (via API) → Linus Torvalds
```

Output : Profils trouvés sur plateformes

### 9. Geoloc Intel
```bash
# API
curl -X POST http://localhost:8000/geo/reverse \
  -d '{"lat":37.4,"lng":-122.0}'
```

Output : Adresse · Timezone · ISP · ASN

### 10. Social Graph
Construit relations cross-platform entre entités trouvées.

### 11. Image Deepscan
```bash
# API
curl -X POST http://localhost:8000/image/scan \
  -F 'image=@photo.jpg'
```

Output : EXIF · GPS · Reverse image (TinEye/Yandex — API key requise)

### 12. Darkweb Scout
⚠️ Nécessite API key (Intel471 / DarkOwl / Flashpoint)
```bash
export DARKOWL_API_KEY=xxx
# API
curl -X POST http://localhost:8000/darkweb/scan \
  -d '{"target":"user@example.com"}'
```

## ⛓ Chain Engine — Workflow principal

### Concept
Le **chain engine** exécute une **cascade récursive** : à partir d'une entité de départ, il explore les relations (email → GitHub → repos → autres emails, etc.) jusqu'à la profondeur max.

### Configuration

Dashboard → **Dashboard** panel :
```
Type      : email
Value     : torvalds@linux.foundation
Max depth : 3
→ RUN CHAIN
```

### Sortie
- **Entities** : 2-4 par profondeur
- **Relations** : graphe d'attachement
- **Modules** : combien déclenchés
- **Elapsed** : temps total

### Visualisation
Panel **Chain Engine** : steps + entités
Panel **Graph** : vue NetworkX/Neo4j

## 🧪 Test inputs (quick)

Dashboard → **Dashboard** panel → section "Quick Test Inputs" :

| Bouton | Input |
|--------|-------|
| 📧 Linus Torvalds | `torvalds@linux.foundation` |
| ⌖ octocat | `octocat` |
| ⊕ 8.8.8.8 | `8.8.8.8` |
| ◈ github.com | `github.com` |
| 📞 +1 415-555-2671 | `+14155552671` |
| ⌬ Linus Torvalds | `Linus Torvalds` |

## 📊 Export rapport

### JSON
```bash
Panel Report → EXPORT JSON
```

### HTML
```bash
Panel Report → EXPORT HTML
```

### Neo4j Cypher
```bash
Panel Report → NEO4J EXPORT
```

Génère un script Cypher pour import direct :
```cypher
MERGE (q:Query {value:"torvalds@linux.foundation"})
MERGE (q)-[:FOUND {depth:1}]->(e:Entity {value:"...",type:"email"});
```

## 🛠️ Commandes utiles

### Lancer backend
```bash
python3 main.py 8000
```

### Tail logs
```bash
tail -f logs/osin.log
```

### Test API direct
```bash
# Health
curl http://localhost:8000/health

# Email
curl -X POST http://localhost:8000/email/trace \
  -H 'Content-Type: application/json' \
  -d '{"email":"test@example.com"}'

# Docs Swagger
open http://localhost:8000/docs
```

### Stopper
```bash
pkill -f "main.py"
```

## 🎯 Workflow mission typique

### Étape 1 — Cible unique
```
1. Dashboard → Email → target@corp.com
2. Trace → MX, GitHub, Gravatar, HIBP
3. Identifier : vrais noms, employers, leak data
```

### Étape 2 — Cascade
```
1. Chain Engine → depth 3
2. Suit les relations : email → GH commits → autres emails → phone
3. Construit graph
```

### Étape 3 — Corrélation
```
1. Panel Chain Engine → voir steps
2. Panel Graph → visualiser
3. Identifier pivot points
```

### Étape 4 — Export
```
1. JSON pour raw data
2. HTML pour presentation
3. Cypher pour Neo4j analysis
```

## 🔒 OPSEC + RGPD

### OPSEC
- ✅ VPN/Tor avant queries
- ✅ Rate limit respecté (config : `rate_limiter.py`)
- ✅ User-Agent rotatif
- ✅ Pas de logs sur cibles

### RGPD
- ✅ Scope écrit signé
- ✅ Données personnelles minimisées
- ✅ Rapports chiffrés GPG
- ✅ Retention policy 30j max
- ✅ Suppression post-mission

## 🆘 Help

`?` dans dashboard ou `python3 main.py --help`.

API Swagger complète : `http://localhost:8000/docs`.

---

🏴‍☠️ **ghost1o1** — *"There is no lock."*
