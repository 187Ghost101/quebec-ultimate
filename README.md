<div align="center">

```
   ▄█████ █  ██  ▄█████ ▄█████▄  ██   ██ ▄█████ █    ██  ██ ██    ██
  ██      ██▄██  ██     ██   ██  ██▄▄▄██ ██     ██    ██  ██ ██    ██
  ██  ███ ██▀██  █████  ██████   ██   ██ █████  ██    ██  ██ ██    ██
  ██   ██ ██  ██ ██     ██   ██  ██   ██ ██      ██  ▄██  ██  ██  ██
   ▀████▀ ██  ██ ▀█████ ██   ██  ██   ██ ▀█████   ▀███▀██▄██  ▀███▀
```

![GHOST1O1](https://img.shields.io/badge/GHOST1O1-NOCTURNE-e63946?style=for-the-badge&logo=ghost&logoColor=white)
![Version](https://img.shields.io/badge/VERSION-3.0-00d4ff?style=for-the-badge)
![Status](https://img.shields.io/badge/STATUS-OPERATIONAL-2ecc71?style=for-the-badge)

# 🔍 Quebec Ultimate
## *Recursive OSINT Chain Engine*

**Chaînage OSINT récursif · Corrélation ASN/Domain/Email/IP · Threat intelligence**

</div>

---

## 🔥 C'est quoi ?

Quebec Ultimate est un **moteur de chaînage OSINT récursif** : à partir d'une seule entrée (domaine, IP, email, ASN), il explore en profondeur toutes les entités liées, puis recommence sur les nouvelles entités, jusqu'à 5 niveaux de profondeur.

**Cas d'usage :**
- Cartographie d'infrastructure d'une cible
- Threat intelligence (qui parle à qui)
- Investigation d'email/username
- Pivot entre identités numériques
- Cartographie ASN/domaine/IP

---

## ✨ Features

- 🔄 **Chaînage récursif** : 5 niveaux de profondeur
- 🌐 **Multi-source** : Shodan, Censys, VirusTotal, HIBP, Hunter.io
- 📊 **Graph viz** : représentation ASCII des liens
- 💾 **Cache intelligent** : pas de requêtes dupliquées
- 📤 **Export multi-format** : JSON, GraphML, CSV, Mermaid
- 🐧 **Multi-OS** : Linux, macOS, Windows, Termux
- 🔌 **API REST** : intégration dans tes outils

---

## 🚀 Démarrage 60 secondes

```bash
git clone https://github.com/187Ghost101/quebec-ultimate.git
cd quebec-ultimate
bash install.sh
python3 main.py --target example.com --depth 3
```

---

## 🎯 Usage rapide

```bash
# À partir d'un domaine
python3 main.py --target example.com --depth 3

# À partir d'une IP
python3 main.py --target 8.8.8.8 --depth 2

# À partir d'un email
python3 main.py --target user@example.com --depth 2

# Export GraphML pour Gephi/Maltego
python3 main.py --target example.com --depth 3 --format graphml --output graph.graphml
```

---

## 📚 Documentation

- **[INSTALL.md](INSTALL.md)** — Installation par OS
- **[USAGE.md](USAGE.md)** — Exemples détaillés
- **[SECURITY.md](SECURITY.md)** — Éthique
- **[CHANGELOG.md](CHANGELOG.md)** — Historique

---

## 🔗 Liens

- **Hub GHOST1O1** : [github.com/187Ghost101/ghost1o1](https://github.com/187Ghost101/ghost1o1)
- **Protocole** : [PROTOCOL.md](https://github.com/187Ghost101/ghost1o1/blob/main/PROTOCOL.md)

---

## 📜 Licence

MIT — voir [LICENSE](LICENSE)

---

<div align="center">

### Forged in the dark by [ghost1o1](https://github.com/187Ghost101) — 2026

*"There is no lock."*

</div>
