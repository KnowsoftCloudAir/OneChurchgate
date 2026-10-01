
(function () {
  const KEY = "cg_memories_v4";
  const MAX = 36;
  const EFFECTS = ["kenburns", "fade", "slide", "zoom", "flip", "glow", "pan"];
  let state = { on: true, landscape: false, intervalMs: 5500, items: [], idx: 0, timer: null, musicOn: false, effect: "kenburns" };

  function load() {
    try {
      const raw = localStorage.getItem(KEY) || localStorage.getItem("cg_memories_v3");
      if (raw) {
        const p = JSON.parse(raw);
        state.on = p.on !== false;
        state.landscape = !!p.landscape;
        state.intervalMs = p.intervalMs || 5500;
        state.musicOn = !!p.musicOn;
        state.effect = EFFECTS.indexOf(p.effect) >= 0 ? p.effect : "kenburns";
        state.items = Array.isArray(p.items) ? p.items.slice(0, MAX) : [];
      }
    } catch (e) { state.items = []; }
  }
  function save() {
    try {
      localStorage.setItem(KEY, JSON.stringify({
        on: state.on, landscape: state.landscape, intervalMs: state.intervalMs,
        musicOn: state.musicOn, effect: state.effect, items: state.items
      }));
    } catch (e) {
      while (state.items.length > 8) state.items.shift();
      try {
        localStorage.setItem(KEY, JSON.stringify({
          on: state.on, landscape: state.landscape, intervalMs: state.intervalMs,
          musicOn: state.musicOn, effect: state.effect, items: state.items
        }));
      } catch (e2) {}
    }
  }
  function $(id) { return document.getElementById(id); }

  function paintExtToggle() {
    const btn = $("cg-memories-ext-toggle");
    if (!btn) return;
    if (state.on) {
      btn.textContent = "Memories ON";
      btn.classList.remove("is-off");
      btn.setAttribute("aria-pressed", "true");
    } else {
      btn.textContent = "Memories OFF";
      btn.classList.add("is-off");
      btn.setAttribute("aria-pressed", "false");
    }
  }

  function paintDots() {
    const dots = $("cg-memories-dots");
    if (!dots) return;
    if (!state.items.length || !state.on) {
      dots.innerHTML = "";
      return;
    }
    const n = Math.min(state.items.length, 12);
    let html = "";
    for (let i = 0; i < n; i++) {
      const active = (state.idx % state.items.length) === i || (state.items.length > 12 && i === n - 1 && state.idx >= 12);
      const on = (state.idx % state.items.length) % n === i;
      html += '<span class="' + (on ? "on" : "") + '"></span>';
    }
    dots.innerHTML = html;
  }

  function render() {
    const root = $("cg-memories");
    if (!root) return;
    root.classList.toggle("is-off", !state.on);
    root.classList.toggle("is-landscape", state.landscape);
    paintExtToggle();
    paintDots();
    const stage = $("cg-memories-stage");
    const empty = $("cg-memories-empty");
    if (!state.items.length) {
      if (stage) stage.innerHTML = "";
      if (empty) empty.classList.remove("hidden");
      return;
    }
    if (empty) empty.classList.add("hidden");
    const it = state.items[state.idx % state.items.length];
    if (!stage || !it) return;
    stage.innerHTML = "";
    const img = document.createElement("img");
    img.src = it.dataUrl;
    img.alt = it.name || "Memory";
    img.className = "cg-mem-img cg-fx-" + (state.effect || "kenburns");
    stage.appendChild(img);
  }

  function next() {
    if (state.items.length < 1) return;
    state.idx = (state.idx + 1) % state.items.length;
    render();
  }
  function prev() {
    if (state.items.length < 1) return;
    state.idx = (state.idx - 1 + state.items.length) % state.items.length;
    render();
  }
  function stopTimer() { if (state.timer) { clearInterval(state.timer); state.timer = null; } }
  function startTimer() {
    stopTimer();
    if (!state.on || state.items.length < 2) return;
    state.timer = setInterval(next, state.intervalMs);
  }

  function compress(file, maxW, quality) {
    return new Promise(function (resolve) {
      const fr = new FileReader();
      fr.onload = function () {
        const img = new Image();
        img.onload = function () {
          let w = img.width, h = img.height;
          if (w > maxW) { h = Math.round(h * maxW / w); w = maxW; }
          const c = document.createElement("canvas");
          c.width = w; c.height = h;
          c.getContext("2d").drawImage(img, 0, 0, w, h);
          resolve({ dataUrl: c.toDataURL("image/jpeg", quality), name: file.name });
        };
        img.onerror = function () { resolve(null); };
        img.src = fr.result;
      };
      fr.onerror = function () { resolve(null); };
      fr.readAsDataURL(file);
    });
  }

  async function addFiles(fileList) {
    const files = Array.from(fileList || []).filter(function (f) { return /^image\//.test(f.type); }).slice(0, MAX);
    for (let i = 0; i < files.length; i++) {
      const packed = await compress(files[i], 1400, 0.78);
      if (!packed) continue;
      state.items.push({ id: Date.now() + Math.random(), dataUrl: packed.dataUrl, name: packed.name });
      if (state.items.length > MAX) state.items = state.items.slice(-MAX);
    }
    save(); render(); startTimer();
  }

  function music() {
    const audio = $("cg-memories-audio");
    if (!audio) return;
    if (!audio.getAttribute("src")) {
      audio.src = "/static/uploads/kwealth_bgm/admin_global/nature_ambient.mp3";
    }
    if (state.musicOn) { audio.volume = 0.38; audio.play().catch(function () {}); }
    else audio.pause();
  }

  function setOn(on) {
    state.on = !!on;
    save();
    render();
    if (state.on) startTimer(); else stopTimer();
  }

  function init() {
    load();
    const root = $("cg-memories");
    if (!root) return;

    const ext = $("cg-memories-ext-toggle");
    if (ext) ext.addEventListener("click", function () { setOn(!state.on); });

    $("cg-memories-landscape") && $("cg-memories-landscape").addEventListener("click", function () {
      state.landscape = !state.landscape; save();
      root.classList.toggle("is-landscape", state.landscape);
    });
    $("cg-memories-add") && $("cg-memories-add").addEventListener("change", function (e) {
      addFiles(e.target.files); e.target.value = "";
    });
    $("cg-memories-clear") && $("cg-memories-clear").addEventListener("click", function () {
      if (!confirm("Clear all Memories photos on this device?")) return;
      state.items = []; save(); render(); stopTimer();
    });
    $("cg-memories-next") && $("cg-memories-next").addEventListener("click", function () { next(); startTimer(); });
    $("cg-memories-prev") && $("cg-memories-prev").addEventListener("click", function () { prev(); startTimer(); });
    $("cg-memories-music") && $("cg-memories-music").addEventListener("click", function () {
      state.musicOn = !state.musicOn; save(); music();
      this.textContent = state.musicOn ? "♪ Music on" : "♪ Music off";
    });
    const fx = $("cg-memories-effect");
    if (fx) {
      fx.value = state.effect;
      fx.addEventListener("change", function () {
        state.effect = this.value;
        save();
        render();
      });
    }

    render();
    if (state.on) startTimer();
    music();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
  window.CGMemories = { init: init, addFiles: addFiles, setOn: setOn };
})();
