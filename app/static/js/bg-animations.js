/* Churchgate ambient background animations (canvas). Free: none + first theme; rest premium if gated by UI. */
(function (global) {
  const MODES = [
    { id: 'none', name: 'None (default)', free: true },
    { id: 'sunset', name: 'Sunset glow', free: true },
    { id: 'ocean_fish', name: 'Ocean fish (3D depth)', free: false },
    { id: 'sky_run', name: 'Sky run (stars)', free: false },
    { id: 'jupiter', name: 'Jupiter flyby', free: false },
    { id: 'word_forms', name: 'Spoken word shapes', free: false },
    { id: 'great_men', name: 'Portraits from the sky', free: false },
    { id: 'sunrise_ant', name: 'Sunrise ant trail', free: false },
  ];

  let canvas, ctx, raf, mode = 'none', paused = false, t0 = 0;
  let fullscreen = false;
  let wordQueue = [];

  function ensureCanvas() {
    if (canvas) return;
    canvas = document.createElement('canvas');
    canvas.id = 'cgBgAnim';
    canvas.style.cssText = 'position:fixed;inset:0;z-index:0;pointer-events:none;opacity:0.85;';
    document.body.prepend(canvas);
    ctx = canvas.getContext('2d');
    resize();
    window.addEventListener('resize', resize);
  }

  function resize() {
    if (!canvas) return;
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
  }

  function setMode(id) {
    mode = id || 'none';
    localStorage.setItem('cg_bg_anim', mode);
    if (mode === 'none') {
      stop();
      if (canvas) canvas.style.display = 'none';
      return;
    }
    ensureCanvas();
    canvas.style.display = 'block';
    if (!raf) start();
  }

  function setPaused(p) {
    paused = !!p;
    localStorage.setItem('cg_bg_anim_paused', paused ? '1' : '0');
  }

  function toggleFullscreen() {
    const el = document.documentElement;
    if (!document.fullscreenElement) {
      el.requestFullscreen && el.requestFullscreen();
      fullscreen = true;
    } else {
      document.exitFullscreen && document.exitFullscreen();
      fullscreen = false;
    }
  }

  function pushSpokenWord(text) {
    if (!text) return;
    const w = String(text).split(/\s+/).slice(0, 8).join(' ');
    wordQueue.push({ t: performance.now(), text: w });
    if (wordQueue.length > 6) wordQueue.shift();
  }

  function start() {
    t0 = performance.now();
    const loop = (now) => {
      raf = requestAnimationFrame(loop);
      if (paused || !ctx || mode === 'none') return;
      const t = (now - t0) / 1000;
      const W = canvas.width, H = canvas.height;
      ctx.clearRect(0, 0, W, H);
      if (mode === 'sunset') drawSunset(t, W, H);
      else if (mode === 'ocean_fish') drawOcean(t, W, H);
      else if (mode === 'sky_run') drawSky(t, W, H);
      else if (mode === 'jupiter') drawJupiter(t, W, H);
      else if (mode === 'word_forms') drawWords(t, W, H);
      else if (mode === 'great_men') drawPortraits(t, W, H);
      else if (mode === 'sunrise_ant') drawAnt(t, W, H);
    };
    raf = requestAnimationFrame(loop);
  }

  function stop() {
    if (raf) cancelAnimationFrame(raf);
    raf = null;
  }

  function drawSunset(t, W, H) {
    const g = ctx.createLinearGradient(0, 0, 0, H);
    g.addColorStop(0, '#0f172a');
    g.addColorStop(0.45, '#7c2d12');
    g.addColorStop(0.7, '#f59e0b');
    g.addColorStop(1, '#1e1b4b');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, W, H);
    const y = H * 0.55 + Math.sin(t * 0.3) * 8;
    ctx.beginPath();
    ctx.arc(W * 0.5, y, Math.min(W, H) * 0.12, 0, Math.PI * 2);
    ctx.fillStyle = '#fbbf24';
    ctx.fill();
  }

  function drawOcean(t, W, H) {
    const g = ctx.createLinearGradient(0, 0, 0, H);
    g.addColorStop(0, '#020617');
    g.addColorStop(1, '#0ea5e9');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, W, H);
    for (let i = 0; i < 7; i++) {
      const phase = t * (0.4 + i * 0.07) + i;
      const depth = (Math.sin(phase) + 1) / 2;
      const y = H * (0.85 - depth * 0.7);
      const x = ((t * 40 * (1 + i * 0.1) + i * 90) % (W + 80)) - 40;
      const s = 12 + depth * 28;
      ctx.save();
      ctx.translate(x, y);
      ctx.scale(1 + depth, 0.6 + depth * 0.5);
      ctx.fillStyle = `rgba(56,189,248,${0.35 + depth * 0.5})`;
      ctx.beginPath();
      ctx.ellipse(0, 0, s, s * 0.4, 0, 0, Math.PI * 2);
      ctx.fill();
      ctx.beginPath();
      ctx.moveTo(s * 0.8, 0);
      ctx.lineTo(s * 1.4, -s * 0.3);
      ctx.lineTo(s * 1.4, s * 0.3);
      ctx.fill();
      ctx.restore();
    }
  }

  function drawSky(t, W, H) {
    ctx.fillStyle = '#020617';
    ctx.fillRect(0, 0, W, H);
    const depth = (t * 0.08) % 1;
    for (let i = 0; i < 120; i++) {
      const x = (i * 97 + depth * W * 0.3) % W;
      const y = (i * 53 + depth * H * 0.5) % H;
      const tw = 0.4 + 0.6 * Math.abs(Math.sin(t * 2 + i));
      ctx.fillStyle = `rgba(255,255,255,${tw})`;
      ctx.fillRect(x, y, 2, 2);
    }
    ctx.fillStyle = 'rgba(99,102,241,0.15)';
    ctx.beginPath();
    ctx.arc(W / 2, H / 2, H * (0.2 + depth * 0.4), 0, Math.PI * 2);
    ctx.fill();
  }

  function drawJupiter(t, W, H) {
    ctx.fillStyle = '#020617';
    ctx.fillRect(0, 0, W, H);
    // sun far
    ctx.beginPath();
    ctx.arc(W * 0.5, H * 0.5, 18, 0, Math.PI * 2);
    ctx.fillStyle = '#fbbf24';
    ctx.fill();
    const cycle = (t * 0.15) % 2;
    let x, r;
    if (cycle < 1) {
      x = W * (0.15 + cycle * 0.7);
      r = 20 + cycle * Math.min(W, H) * 0.45;
    } else {
      x = W * (0.85 + (cycle - 1) * 0.4);
      r = Math.min(W, H) * 0.55 - (cycle - 1) * 80;
    }
    const grd = ctx.createRadialGradient(x - r * 0.2, H * 0.45, r * 0.1, x, H * 0.5, r);
    grd.addColorStop(0, '#fcd34d');
    grd.addColorStop(0.4, '#d97706');
    grd.addColorStop(1, '#7c2d12');
    ctx.beginPath();
    ctx.arc(x, H * 0.5, Math.max(8, r), 0, Math.PI * 2);
    ctx.fillStyle = grd;
    ctx.fill();
    // next planet hint
    ctx.beginPath();
    ctx.arc(W * 0.92, H * 0.4, 14, 0, Math.PI * 2);
    ctx.fillStyle = '#93c5fd';
    ctx.fill();
  }

  function drawWords(t, W, H) {
    ctx.fillStyle = 'rgba(15,23,42,0.35)';
    ctx.fillRect(0, 0, W, H);
    const now = performance.now();
    wordQueue.forEach((item, i) => {
      const age = (now - item.t) / 1000;
      if (age > 6) return;
      const alpha = Math.max(0, 1 - age / 6);
      ctx.save();
      ctx.globalAlpha = alpha;
      ctx.fillStyle = '#e0e7ff';
      ctx.font = `bold ${18 + i * 4}px system-ui,sans-serif`;
      ctx.fillText(item.text, W * 0.1, H * 0.3 + i * 40 + Math.sin(t + i) * 10);
      // simple 3d-ish block
      ctx.fillStyle = `rgba(129,140,248,${0.25 * alpha})`;
      ctx.fillRect(W * 0.55, H * 0.25 + i * 50, 80, 50);
      ctx.restore();
    });
  }

  function drawPortraits(t, W, H) {
    ctx.fillStyle = '#0f172a';
    ctx.fillRect(0, 0, W, H);
    for (let i = 0; i < 5; i++) {
      const phase = (t * 0.12 + i * 0.2) % 1;
      const y = -80 + phase * (H + 160);
      const scale = 0.4 + phase * 1.2;
      const x = W * (0.15 + (i % 3) * 0.3);
      const s = 40 * scale;
      ctx.save();
      ctx.translate(x, y);
      ctx.fillStyle = `rgba(226,232,240,${0.35 + phase * 0.4})`;
      ctx.beginPath();
      ctx.arc(0, -s * 0.35, s * 0.35, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillRect(-s * 0.45, -s * 0.05, s * 0.9, s * 0.9);
      ctx.restore();
    }
  }

  function drawAnt(t, W, H) {
    const g = ctx.createLinearGradient(0, 0, 0, H);
    g.addColorStop(0, '#7c2d12');
    g.addColorStop(0.5, '#fbbf24');
    g.addColorStop(1, '#14532d');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, W, H);
    // leaves buzz
    for (let i = 0; i < 30; i++) {
      const x = (i * 40 + Math.sin(t + i) * 8) % W;
      const y = H * 0.55 + Math.sin(t * 3 + i) * 6;
      ctx.fillStyle = 'rgba(22,163,74,0.7)';
      ctx.beginPath();
      ctx.ellipse(x, y, 10, 4, Math.sin(t + i), 0, Math.PI * 2);
      ctx.fill();
    }
    const ax = (t * 50) % (W + 40) - 20;
    const ay = H * 0.72 + Math.sin(t * 2) * 12;
    ctx.fillStyle = '#1c1917';
    ctx.beginPath();
    ctx.ellipse(ax, ay, 10, 5, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.beginPath();
    ctx.arc(ax + 10, ay - 2, 4, 0, Math.PI * 2);
    ctx.fill();
  }

  // restore
  const saved = localStorage.getItem('cg_bg_anim') || 'none';
  const wasPaused = localStorage.getItem('cg_bg_anim_paused') === '1';

  global.CGBgAnim = {
    MODES,
    setMode,
    setPaused,
    toggleFullscreen,
    pushSpokenWord,
    getMode: () => mode,
    isPaused: () => paused,
    init() {
      if (saved && saved !== 'none') setMode(saved);
      if (wasPaused) setPaused(true);
    },
  };
})(window);
