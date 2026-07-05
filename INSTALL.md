# 🔧 Quebec Ultimate — Guide d'installation

---

## 🐧 Kali / Debian / Ubuntu

```bash
sudo apt update && sudo apt install -y python3 python3-pip git
cd ~
git clone https://github.com/187Ghost101/quebec-ultimate.git
cd quebec-ultimate
pip3 install -r requirements.txt
python3 main.py --help
```

## 🏔️ Arch / Manjaro

```bash
sudo pacman -S python python-pip git
cd ~
git clone https://github.com/187Ghost101/quebec-ultimate.git
cd quebec-ultimate
pip3 install -r requirements.txt
```

## 🍎 macOS

```bash
brew install python3 git
cd ~
git clone https://github.com/187Ghost101/quebec-ultimate.git
cd quebec-ultimate
pip3 install -r requirements.txt
```

## 🪟 Windows (WSL2)

```powershell
wsl --install -d Ubuntu
```
```bash
sudo apt update && sudo apt install -y python3 python3-pip git
git clone https://github.com/187Ghost101/quebec-ultimate.git
cd quebec-ultimate
pip3 install -r requirements.txt
```

## 📱 Termux (Android)

```bash
pkg update && pkg install python git
cd ~
git clone https://github.com/187Ghost101/quebec-ultimate.git
cd quebec-ultimate
pip3 install -r requirements.txt
```

## 🐳 Docker

```bash
docker run -it --rm -v $(pwd):/data 187ghost101/quebec-ultimate
```

## ✅ Vérification

```bash
python3 main.py --help
# → usage: main.py [-h] --target TARGET [--depth DEPTH] [--format FORMAT]
```

---

*"There is no lock." — ghost1o1*
