# GHOST1O1 BRAND — OSIN Chain Quebec Ultimate v3.0

> The norm for avant-garde hacker UIs. Established by **ghost1o1**.

This project follows the **GHOST1O1 Nocturne** design system.

## Signature (anchored deep)
- **Text**: `GHOST1O1`
- **Tagline**: `"There is no lock."`
- **Logo**: `QC` in conic-gradient square (cyan/violet — OSIN chain house style)

## 5-layer signature system
1. **Watermark bg** — repeating `GHOST1O1` text (`.09` opacity, drift animation 60s)
2. **Corner stamp** — fixed vertical "GHOST1O1 · NOCTURNE" bottom-right
3. **Brand mark** — `QC` conic gradient in topbar
4. **Sig block** — About + splash pages
5. **Sig inline** — topbar, footer, all major cards

## Palette
```
--g1-void:    #05050d   background
--g1-blood:   #e3063e   primary (GHOST1O1 red)
--g1-violet:  #a855f7   secondary
--g1-cyan:    #00f3ff   tertiary (QC accent)
--g1-magenta: #ec4899   quaternary
--g1-neon:    #00ff9d   success
--g1-gold:    #fbbf24   warning
```

## OSIN-specific colors
The dashboard uses **cyan `#00f3ff`** as the OSIN house accent (data/intel — replacing the usual violet for differentiation). All other GHOST1O1 norms apply.

## Files using the design system
- `nocturne.html` — Nocturne web dashboard (12 modules + chain engine)
- `ghost1o1.css` + `ghost1o1.js` — shared design system
- `frontend/index.html` — existing FastAPI frontend (untouched, uses Leaflet + Cytoscape)

## Design system
- CSS: `ghost1o1.css` (34KB)
- JS: `ghost1o1.js` (10KB)
- 0 dependencies · 0 CDN (in brand layer) · 0 telemetry

## Tone
- Avant-garde cyberpunk
- Hacker-first
- Direct, no corporate fluff
- 100% offensive-grade

## License
MIT-style — Educational use only.
© 2026 ghost1o1
