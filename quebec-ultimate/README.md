# OSIN CHAIN QUEBEC ULTIMATE v3.0
**By Ghost1o1 — Real OSINT chain with REAL HTTP calls**

## Sources (REAL, no theater)
- **ip-api.com** + **ipapi.co** + **HackerTarget** — IP geolocation, ISP, ASN, subdomains
- **GitHub API** — commits by email, user search, repos
- **DuckDuckGo HTML** — public web mentions
- **phonenumbers lib** + **NANP area database** — offline phone parsing
- **DNS (dnspython)** — A/MX/NS/TXT records
- **RDAP** — IP ownership
- **Telegram t.me** — public channel preview
- **Gravatar** — hash-based profile lookup

## What REQUIRES API keys (documented in warnings)
- Phone → Name (TrueCaller / Numverify / Canada411)
- Reverse image (TinEye / Yandex / PimEyes)
- Darkweb intel (Intel471 / DarkOwl / Flashpoint)
- HIBP full email (k-anon is free)

## Install
```bash
./install.sh /root/supreme
cd /root/supreme && python3 main.py
```

## Test inputs
- `torvalds@linux.foundation` — email → GitHub commits, LinkedIn, etc.
- `octocat` — username → GitHub profile + 25 platform HTTP checks
- `8.8.8.8` — IP → geo, ISP, ASN, reverse DNS
- `github.com` — domain → DNS, subdomains, MX
- `+15145550199` — phone → carrier, country, area city

## Architecture
- **NetworkX graph backend** (Neo4j optional via env)
- **12 modules** with source attribution + confidence scores
- **Cascade engine** with WS broadcasts (depth=0 verified; depth=1 partial)
- **FastAPI + WebSocket** for live updates
- **Cytoscape.js** frontend

## Honest disclosure
This is NOT magic. Without paid APIs, we CANNOT do:
- Phone → full name + address (Canada411 does this with paid DB)
- Reverse face search
- Darkweb content (Tor + intel feeds required)

What we CAN do: extract everything public, correlate, cross-reference.
