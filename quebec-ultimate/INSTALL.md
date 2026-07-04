# 📥 OSIN Chain Quebec v3.0 — Guide d'installation

> Backend FastAPI + dashboard Nocturne · multi-plateforme.

## 🎯 Prérequis

| Item | Requis | Note |
|------|--------|------|
| **OS** | Kali / Debian / Ubuntu / macOS / Termux | Linux recommandé |
| **Python** | 3.10+ (3.12 idéal) | FastAPI 0.100+ |
| **RAM** | 200 MB | |
| **Disque** | 20 MB | |
| **Neo4j** | optionnel | Pour graph persistence |
| **Ports** | 8000 (FastAPI) | Modifiable |

## ⚡ Méthode 1 — Installateur (recommandée)

```bash
# 1. Clone
git clone https://github.com/187Ghost101/quebec-ultimate.git
cd quebec-ultimate/quebec-ultimate

# 2. Install
chmod +x install.sh
./install.sh
```

Le script :
1. Crée `venv/`
2. Installe `requirements.txt` + `requirements-face.txt` (optionnel)
3. Crée dossiers `data/`, `logs/`, `exports/`
4. Teste l'import des 17 core + 12 modules

## 🔧 Méthode 2 — Manuel

### 2.1 Cloner

```bash
git clone https://github.com/187Ghost101/quebec-ultimate.git
cd quebec-ultimate/quebec-ultimate
```

### 2.2 Python deps

```bash
# Minimal (sans face)
pip3 install -r requirements.txt

# Avec face (deepface + tf)
pip3 install -r requirements-face-minimal.txt
```

### 2.3 Lancer backend

```bash
python3 main.py
```

Output attendu :
```
╔═══════════════════════════════════════════╗
║  OSIN CHAIN QUEBEC ULTIMATE v3.0          ║
║  FastAPI + WebSocket + NetworkX           ║
╠═══════════════════════════════════════════╣
║  API    : http://0.0.0.0:8000            ║
║  WS     : ws://0.0.0.0:8000/ws           ║
║  Docs   : http://0.0.0.0:8000/docs       ║
╚═══════════════════════════════════════════╝
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### 2.4 Lancer dashboard

```bash
# Nouvelle fenêtre terminal
python3 -m http.server 8090
# Ouvre http://localhost:8090/nocturne.html
```

## 🐧 Kali Linux

```bash
sudo apt update
sudo apt install -y python3-pip python3-venv git
git clone https://github.com/187Ghost101/quebec-ultimate.git
cd quebec-ultimate/quebec-ultimate
pip3 install -r requirements.txt
chmod +x install.sh
./install.sh
python3 main.py &
python3 -m http.server 8090 &
firefox http://localhost:8090/nocturne.html
```

## 🍎 macOS

```bash
brew install python3 git
git clone https://github.com/187Ghost101/quebec-ultimate.git
cd quebec-ultimate/quebec-ultimate
pip3 install -r requirements.txt
python3 main.py
```

## 📱 Termux (Android)

```bash
pkg update && pkg install python git
git clone https://github.com/187Ghost101/quebec-ultimate.git
cd quebec-ultimate/quebec-ultimate
pip install -r requirements.txt
nohup python3 main.py > osin.log 2>&1 &
```

## 🪟 Windows (WSL2)

```powershell
wsl --install
wsl --set-default-version 2

# Dans WSL Ubuntu
sudo apt install python3-pip python3-venv git
git clone https://github.com/187Ghost101/quebec-ultimate.git
cd quebec-ultimate/quebec-ultimate
pip3 install -r requirements.txt
python3 main.py
```

## 🕸 Neo4j (optionnel)

Pour activer la persistance graph via Neo4j :

```bash
# 1. Install Neo4j (Docker)
docker run -d --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:latest

# 2. Config
export NEO4J_URI=bolt://localhost:7687
export NEO4J_USER=neo4j
export NEO4J_PASS=password
```

## 📊 Test inputs

Dans le dashboard Nocturne, panel **Dashboard** :

| Type | Value | Modules déclenchés |
|------|-------|---------------------|
| Email | `torvalds@linux.foundation` | Email Tracer + GitHub |
| Username | `octocat` | Username Sherlock (25 sites) |
| IP | `8.8.8.8` | IP Tracker + Shodan |
| Domain | `github.com` | Domain Mapper |
| Phone | `+14155552671` | Phone Intel |
| Name | `Linus Torvalds` | Name Resolver |

## ✅ Vérification

### Backend health
```bash
curl http://localhost:8000/health
# {"status":"ok","version":"3.0","uptime":...}
```

### Modules
```bash
python3 -c "from modules import phone_intel, email_tracer; print('✓ 12 modules OK')"
```

### Dashboard
- Ouvre `http://localhost:8090/nocturne.html`
- 14 panels dans sidebar
- Topbar affiche `OSIN CHAIN QUEBEC v3.0 · NOCTURNE`

## 🆘 Troubleshooting

### Module non trouvé
```bash
pip3 install -r requirements.txt --force-reinstall
# Vérifier Python >= 3.10
python3 --version
```

### Port 8000 occupé
```bash
# Changer
export OSIN_PORT=9000
python3 main.py
# OU dans config.py
PORT = 9000
```

### Neo4j connection failed
- C'est **optionnel** — le moteur fonctionne sans
- Vérifie `NEO4J_URI` dans env vars
- Teste : `python3 -c "from core.neo4j_manager import Neo4jManager; n=Neo4jManager(); n.connect()"`

### Face module ne charge pas
- Nécessite `requirements-face.txt` (lourd : tensorflow)
- Optionnel — désactive via config

## 🔄 Mise à jour

```bash
git pull origin main
pip3 install -r requirements.txt --upgrade
```

---

**Prêt ?** → [USAGE.md](USAGE.md) pour le guide d'utilisation.

🏴‍☠️ **ghost1o1** — *"There is no lock."*
