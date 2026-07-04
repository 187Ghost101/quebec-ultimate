# 🏴‍☠️ OSIN CHAIN QUEBEC ULTIMATE v12 — Install Kali

## Quick Install (Core Only — always works)

```bash
mkdir -p ~/osin && cd ~/osin
rm -rf quebec-ultimate
wget -q https://d.uguu.se/PnAUdhbj.tar.gz -O v12.tar.gz
tar xzf v12.tar.gz && cd quebec-ultimate
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt
```

That's it — core 13 modules work out of the box.

## Add Face Recognition (Module 14)

**Option A — SOTA ArcFace 512-d (best)** :
```bash
./venv/bin/pip install insightface onnxruntime
```
First launch downloads buffalo_l (~300MB into `~/.insightface/`).

**Option B — dlib 128-d (lighter, needs compilation)** :
```bash
sudo apt install -y cmake g++ libboost-all-dev
./venv/bin/pip install face-recognition
```

**Option C — No install, OpenCV Haar fallback** :
Already bundled. Module 14 works in basic mode (face detection only, no embeddings).

## Launch

```bash
nohup ./venv/bin/python3 -m uvicorn main:create_app --factory --host 0.0.0.0 --port 8000 > /tmp/osin.log 2>&1 & disown
sleep 5
curl -s http://127.0.0.1:8000/api/v1/modules | python3 -c "import sys,json;d=json.load(sys.stdin);print(f'{len(d[\"modules\"])} modules loaded');[print(f'  [{m[\"id\"]:2d}] {m[\"icon\"]} {m[\"name\"]}') for m in d['modules']]"
```

## What you get

| # | Module | Available |
|---|--------|-----------|
| 1-12 | PhoneIntel, ImageDeepScan, EmailTracer, UsernameSherlock, DomainMapper, IPTracker, NameResolver, SocialGraph, BreachHunter, DarkWebScout, GeoLocIntel, DocAnalyzer | ✅ Always |
| 13 | 🧬 ContentMiner (avatar pHash + bio link mining + GitHub API) | ✅ Always |
| 14 | 🧬👤 FaceMatch (face detection + EXIF GPS + clustering) | ✅ Always (basic) / ⭐ ArcFace with Option A |

## Module 14 — Face Tiers

| Tier | Backend | When | Quality |
|------|---------|------|---------|
| ⭐ | InsightFace + ArcFace 512-d + RetinaFace | Option A installed | SOTA |
| 🥈 | face_recognition + dlib 128-d | Option B installed | Very good |
| 🥉 | OpenCV Haar + pHash crop | Always (no install) | Basic |

The module auto-picks the best available backend on first use.

## Verify module 14

```bash
./venv/bin/python3 -c "
import sys; sys.path.insert(0,'.')
from modules import list_all_modules
for m in list_all_modules():
    print(f\"[{m['id']:2d}] {m['icon']} {m['name']}\")
"
```

Should show 14 modules including `[14] 🧬👤 FaceMatch`.

## Python 3.13 Note

Kali uses Python 3.13. Some face libs have no wheel for 3.13 yet:
- `onnxruntime==1.18.1` — not available, use `>=1.20.0` (auto-picked)
- `face-recognition==1.3.0` — needs dlib, might need `cmake`/`g++`
- `dlib-bin` — only Python ≤3.12

If Option B fails on 3.13, use Option C (just don't install face libs). Module 14 still works with OpenCV fallback.