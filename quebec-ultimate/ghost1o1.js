/* ════════════════════════════════════════════════════════════════════
   GHOST1O1 DESIGN SYSTEM — v1.1 NOCTURNE
   JavaScript runtime · particles · cursor · tilt · nav · sound
   "There is no lock." · ghost1o1
   ════════════════════════════════════════════════════════════════════
   Usage:
     <link rel="stylesheet" href="ghost1o1.css">
     <body class="g1-body">
     ...
     <script src="ghost1o1.js"></script>
     <script>G1.init({watermarkDeep: true});</script>
   ════════════════════════════════════════════════════════════════════ */
(function(){
  'use strict';

  const G1 = {
    version: '1.1.0-nocturne',
    author: 'ghost1o1',

    init(opts = {}){
      this.opts = Object.assign({
        particles: true,
        cursorGlow: true,
        watermark: true,
        watermarkDeep: true,    // signature ancrée deep
        watermarkText: 'GHOST1O1',
        watermarkCount: 8,
        tilt: true,
        aurora: true,
        grid: true,
        signature: 'There is no lock.',
        sound: false
      }, opts);

      if (this.opts.aurora) this._injectAurora();
      if (this.opts.grid) this._injectGrid();
      if (this.opts.particles) this._injectParticles();
      if (this.opts.cursorGlow) this._injectCursorGlow();
      if (this.opts.watermark) this._injectWatermark();
      if (this.opts.tilt) this.tilt();
      this._hashNav();
      this._shortcuts();

      console.log('%c◆ GHOST1O1 · ' + this.version + ' ◆', 'color:#a855f7;font-weight:800;font-size:14px;letter-spacing:.1em');
      console.log('%c"' + this.opts.signature + '" — ghost1o1', 'color:#e3063e;font-style:italic;font-size:12px');
      return this;
    },

    // ─── DOM injection ───
    _injectAurora(){
      if (document.getElementById('g1-aurora')) return;
      const a = document.createElement('div');
      a.id = 'g1-aurora';
      a.className = 'g1-aurora';
      document.body.appendChild(a);
    },
    _injectGrid(){
      if (document.getElementById('g1-grid')) return;
      const g = document.createElement('div');
      g.id = 'g1-grid';
      g.className = 'g1-grid';
      document.body.appendChild(g);
    },
    _injectParticles(){
      if (document.getElementById('g1-particles')) return;
      const c = document.createElement('canvas');
      c.id = 'g1-particles';
      c.style.cssText = 'position:fixed;inset:0;z-index:-1;pointer-events:none;opacity:.6';
      document.body.appendChild(c);
      this._particles();
    },
    _injectCursorGlow(){
      if (document.getElementById('g1-cursor-glow')) return;
      const g = document.createElement('div');
      g.id = 'g1-cursor-glow';
      g.className = 'g1-cursor-glow';
      document.body.appendChild(g);
      this._cursor();
    },
    _injectWatermark(){
      if (document.getElementById('g1-watermark')) return;
      // Background watermark — large repeating
      const w = document.createElement('div');
      w.id = 'g1-watermark';
      w.className = 'g1-watermark' + (this.opts.watermarkDeep ? ' deep' : '');
      for (let i = 0; i < this.opts.watermarkCount; i++){
        const s = document.createElement('span');
        s.textContent = this.opts.watermarkText;
        w.appendChild(s);
      }
      document.body.appendChild(w);
      // Corner stamp — FIXED, ALWAYS VISIBLE
      if (!document.getElementById('g1-sig-stamp')){
        const stamp = document.createElement('div');
        stamp.id = 'g1-sig-stamp';
        stamp.className = 'g1-sig-stamp';
        stamp.textContent = this.opts.watermarkText + ' · NOCTURNE';
        document.body.appendChild(stamp);
      }
    },

    // ─── Particles ───
    _particles(){
      const c = document.getElementById('g1-particles');
      if (!c) return;
      const ctx = c.getContext('2d');
      const resize = () => { c.width = innerWidth; c.height = innerHeight; };
      resize();
      addEventListener('resize', resize);
      const N = Math.min(60, Math.floor((innerWidth * innerHeight) / 24000));
      const ps = Array.from({length: N}, () => ({
        x: Math.random() * innerWidth, y: Math.random() * innerHeight,
        vx: (Math.random() - .5) * .3, vy: (Math.random() - .5) * .3,
        r: Math.random() * 1.8 + .4,
        c: ['#e3063e','#a855f7','#00f3ff','#ec4899','#00ff9d'][Math.floor(Math.random() * 5)]
      }));
      (function tick(){
        ctx.clearRect(0, 0, innerWidth, innerHeight);
        ps.forEach(p => {
          p.x += p.vx; p.y += p.vy;
          if (p.x < 0 || p.x > innerWidth) p.vx *= -1;
          if (p.y < 0 || p.y > innerHeight) p.vy *= -1;
          ctx.beginPath(); ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
          ctx.fillStyle = p.c; ctx.shadowColor = p.c; ctx.shadowBlur = 10;
          ctx.fill(); ctx.shadowBlur = 0;
        });
        ctx.strokeStyle = 'rgba(168,85,247,.12)'; ctx.lineWidth = .5;
        for (let i = 0; i < ps.length; i++)
          for (let j = i + 1; j < ps.length; j++){
            const dx = ps[i].x - ps[j].x, dy = ps[i].y - ps[j].y, d = Math.sqrt(dx*dx + dy*dy);
            if (d < 140){ ctx.beginPath(); ctx.moveTo(ps[i].x, ps[i].y); ctx.lineTo(ps[j].x, ps[j].y); ctx.stroke(); }
          }
        requestAnimationFrame(tick);
      })();
    },

    // ─── Cursor glow ───
    _cursor(){
      const glow = document.getElementById('g1-cursor-glow');
      if (!glow) return;
      let tx = 0, ty = 0, x = 0, y = 0;
      addEventListener('mousemove', e => { tx = e.clientX; ty = e.clientY; });
      (function tick(){
        x += (tx - x) * .1; y += (ty - y) * .1;
        glow.style.left = x + 'px'; glow.style.top = y + 'px';
        requestAnimationFrame(tick);
      })();
    },

    // ─── 3D Tilt ───
    tilt(selector = '[data-g1-tilt]'){
      document.querySelectorAll(selector).forEach(el => {
        if (el.dataset.g1TiltBound) return;
        el.dataset.g1TiltBound = '1';
        el.style.transformStyle = 'preserve-3d';
        el.addEventListener('mousemove', e => {
          const r = el.getBoundingClientRect();
          const x = (e.clientX - r.left) / r.width - .5;
          const y = (e.clientY - r.top) / r.height - .5;
          el.style.transform = `perspective(900px) rotateX(${-y * 3}deg) rotateY(${x * 3}deg) translateZ(0)`;
        });
        el.addEventListener('mouseleave', () => el.style.transform = '');
      });
    },

    // ─── Navigation ───
    goto(id){
      document.querySelectorAll('.g1-page').forEach(p => p.classList.remove('active'));
      document.querySelectorAll('[data-g1-page]').forEach(n => n.classList.remove('active'));
      const page = document.getElementById('g1-page-' + id);
      const nav = document.querySelector('[data-g1-page="' + id + '"]');
      if (page) page.classList.add('active');
      if (nav) nav.classList.add('active');
      const content = document.querySelector('.g1-content');
      if (content) content.scrollTop = 0;
      history.replaceState(null, '', '#' + id);
    },
    _hashNav(){
      addEventListener('hashchange', () => {
        const id = location.hash.slice(1);
        if (id) this.goto(id);
      });
      if (location.hash) this.goto(location.hash.slice(1));
    },

    // ─── Shortcuts ───
    _shortcuts(){
      let gKey = null;
      addEventListener('keydown', e => {
        if (e.target.matches('input,textarea,select')) return;
        if (e.key === '/'){ e.preventDefault(); const q = document.querySelector('[data-g1-search]'); if (q) q.focus(); }
        if (e.key === '?'){ e.preventDefault(); this._help(); }
        if (e.key === 'Escape'){ document.querySelectorAll('.g1-modal.show').forEach(m => m.classList.remove('show')); }
        if ((e.key === 'g' || e.key === 'G') && !e.ctrlKey){
          gKey = 'g'; setTimeout(() => gKey = null, 800);
        } else if (gKey === 'g'){
          gKey = null;
          const map = {h:'home', v:'vectors', c:'cve', r:'recon', s:'streams'};
          if (map[e.key.toLowerCase()]) this.goto(map[e.key.toLowerCase()]);
        }
      });
    },
    _help(){
      console.log('%c◆ GHOST1O1 · SHORTCUTS ◆', 'color:#a855f7;font-weight:800;font-size:14px');
      console.log('%c/  → search', 'color:#00f3ff');
      console.log('%c?  → this help', 'color:#00f3ff');
      console.log('%cg h → home', 'color:#00f3ff');
      console.log('%cesc → close modal', 'color:#00f3ff');
    },

    // ─── Sound ───
    _audioCtx: null,
    soundOn: false,
    sound(){
      this.soundOn = !this.soundOn;
      if (this.soundOn){
        this._audioCtx = this._audioCtx || new (window.AudioContext || window.webkitAudioContext)();
        this._glitch();
      }
      return this.soundOn;
    },
    _glitch(f = 440, d = .04){
      if (!this.soundOn || !this._audioCtx) return;
      const o = this._audioCtx.createOscillator();
      const g = this._audioCtx.createGain();
      o.frequency.value = f; o.type = 'square';
      g.gain.value = .04; g.gain.exponentialRampToValueAtTime(.001, this._audioCtx.currentTime + d);
      o.connect(g); g.connect(this._audioCtx.destination);
      o.start(); o.stop(this._audioCtx.currentTime + d);
    },

    // ─── Toast helper ───
    toast(msg, type = 'ok', duration = 3000){
      const t = document.createElement('div');
      t.textContent = msg;
      const border = type === 'ok' ? 'var(--g1-neon)' : type === 'warn' ? 'var(--g1-gold)' : 'var(--g1-blood)';
      t.style.cssText = `position:fixed;bottom:24px;left:50%;transform:translateX(-50%);
        padding:10px 20px;background:var(--g1-glass-strong);border:1px solid ${border};
        border-radius:8px;font-family:var(--g1-font-mono);font-size:12px;color:#fff;
        z-index:9999;box-shadow:0 0 20px var(--g1-blood-soft);opacity:0;transition:opacity .3s`;
      document.body.appendChild(t);
      requestAnimationFrame(() => t.style.opacity = '1');
      setTimeout(() => { t.style.opacity = '0'; setTimeout(() => t.remove(), 300); }, duration);
    }
  };

  if (typeof window !== 'undefined') window.G1 = G1;
})();
