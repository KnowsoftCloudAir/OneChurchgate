(function () {
  "use strict";
  var KEY = "cg_memories_v4";
  var MAX = 36;
  var EFFECTS = ["kenburns", "fade", "slide", "zoom", "flip", "glow", "pan"];
  var state = { on: true, landscape: false, intervalMs: 5500, items: [], idx: 0, timer: null, musicOn: false, effect: "kenburns", playing: true };

  function $(id) { return document.getElementById(id); }
  function load() {
    try {
      var raw = localStorage.getItem(KEY) || localStorage.getItem("cg_memories_v3");
      if (!raw) return;
      var p = JSON.parse(raw);
      state.on = p.on !== false;
      state.landscape = !!p.landscape;
      state.intervalMs = p.intervalMs || 5500;
      state.musicOn = !!p.musicOn;
      state.playing = p.playing !== false;
      state.effect = EFFECTS.indexOf(p.effect) >= 0 ? p.effect : "kenburns";
      state.items = Array.isArray(p.items) ? p.items.slice(0, MAX) : [];
    } catch (e) { state.items = []; }
  }
  function save() {
    try {
      localStorage.setItem(KEY, JSON.stringify({
        on: state.on, landscape: state.landscape, intervalMs: state.intervalMs,
        musicOn: state.musicOn, playing: state.playing, effect: state.effect, items: state.items
      }));
    } catch (e) {
      while (state.items.length > 8) state.items.shift();
      try {
        localStorage.setItem(KEY, JSON.stringify({
          on: state.on, landscape: state.landscape, intervalMs: state.intervalMs,
          musicOn: state.musicOn, playing: state.playing, effect: state.effect, items: state.items
        }));
      } catch (e2) {}
    }
  }
  function paintExtToggle() {
    var btn = $("cg-memories-ext-toggle");
    if (!btn) return;
    if (state.on) { btn.textContent = "Memories ON"; btn.classList.remove("is-off"); btn.setAttribute("aria-pressed", "true"); }
    else { btn.textContent = "Memories OFF"; btn.classList.add("is-off"); btn.setAttribute("aria-pressed", "false"); }
  }
  function paintPlayBtn() {
    var btn = $("cg-memories-play");
    if (!btn) return;
    if (state.playing) {
      btn.textContent = "\u23F8 Stop";
      btn.classList.add("is-playing"); btn.classList.remove("is-paused");
    } else {
      btn.textContent = "\u25B6 Play";
      btn.classList.add("is-paused"); btn.classList.remove("is-playing");
    }
  }
  function paintDots() {
    var dots = $("cg-memories-dots");
    if (!dots) return;
    if (!state.items.length || !state.on) { dots.innerHTML = ""; return; }
    var n = Math.min(state.items.length, 12);
    var html = "", cur = state.idx % state.items.length;
    for (var i = 0; i < n; i++) html += '<span class="' + ((cur % n) === i ? "on" : "") + '"></span>';
    dots.innerHTML = html;
  }
  function render() {
    var root = $("cg-memories");
    if (!root) return;
    root.classList.toggle("is-off", !state.on);
    root.classList.toggle("is-landscape", state.landscape);
    paintExtToggle(); paintPlayBtn(); paintDots();
    var stage = $("cg-memories-stage"), empty = $("cg-memories-empty");
    if (!state.items.length) {
      if (stage) stage.innerHTML = "";
      if (empty) empty.classList.remove("hidden");
      return;
    }
    if (empty) empty.classList.add("hidden");
    var it = state.items[state.idx % state.items.length];
    if (!stage || !it) return;
    stage.innerHTML = "";
    var img = document.createElement("img");
    img.src = it.dataUrl; img.alt = it.name || "Memory";
    img.className = "cg-mem-img cg-fx-" + (state.effect || "kenburns");
    img.draggable = false;
    stage.appendChild(img);
  }
  function next() { if (state.items.length < 1) return; state.idx = (state.idx + 1) % state.items.length; render(); }
  function prev() { if (state.items.length < 1) return; state.idx = (state.idx - 1 + state.items.length) % state.items.length; render(); }
  function stopTimer() { if (state.timer) { clearInterval(state.timer); state.timer = null; } }
  function startTimer() {
    stopTimer();
    if (!state.on || !state.playing || state.items.length < 2) return;
    state.timer = setInterval(next, state.intervalMs);
  }
  function compress(file, maxW, quality) {
    return new Promise(function (resolve) {
      var fr = new FileReader();
      fr.onload = function () {
        var img = new Image();
        img.onload = function () {
          var w = img.width, h = img.height;
          if (w > maxW) { h = Math.round(h * maxW / w); w = maxW; }
          var c = document.createElement("canvas");
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
    var files = Array.from(fileList || []).filter(function (f) { return /^image\//.test(f.type); }).slice(0, MAX);
    for (var i = 0; i < files.length; i++) {
      var packed = await compress(files[i], 1400, 0.78);
      if (!packed) continue;
      state.items.push({ id: Date.now() + Math.random(), dataUrl: packed.dataUrl, name: packed.name });
      if (state.items.length > MAX) state.items = state.items.slice(-MAX);
    }
    save(); render(); startTimer();
  }
  function music() {
    var audio = $("cg-memories-audio");
    if (!audio) return;
    if (!audio.getAttribute("src")) audio.src = "/static/uploads/kwealth_bgm/admin_global/nature_ambient.mp3";
    if (state.musicOn) { audio.volume = 0.38; audio.play().catch(function () {}); }
    else audio.pause();
  }
  function setOn(on) {
    state.on = !!on; save(); render();
    if (state.on && state.playing) startTimer(); else stopTimer();
  }
  function setPlaying(playing) {
    state.playing = !!playing; save(); paintPlayBtn();
    if (state.playing && state.on) startTimer(); else stopTimer();
  }
  function on(el, ev, fn) { if (el) el.addEventListener(ev, fn, false); }
  function init() {
    load();
    on($("cg-memories-ext-toggle"), "click", function (e) {
      e.preventDefault(); e.stopPropagation(); setOn(!state.on);
    });
    var root = $("cg-memories");
    if (!root) { paintExtToggle(); return; }
    on($("cg-memories-play"), "click", function (e) {
      e.preventDefault(); e.stopPropagation(); setPlaying(!state.playing);
    });
    on($("cg-memories-landscape"), "click", function (e) {
      e.preventDefault(); e.stopPropagation();
      state.landscape = !state.landscape; save();
      root.classList.toggle("is-landscape", state.landscape);
    });
    on($("cg-memories-add"), "change", function (e) { addFiles(e.target.files); e.target.value = ""; });
    on($("cg-memories-clear"), "click", function (e) {
      e.preventDefault();
      if (!confirm("Clear all Memories photos on this device?")) return;
      state.items = []; save(); render(); stopTimer();
    });
    on($("cg-memories-next"), "click", function (e) {
      e.preventDefault(); e.stopPropagation(); next(); if (state.playing) startTimer();
    });
    on($("cg-memories-prev"), "click", function (e) {
      e.preventDefault(); e.stopPropagation(); prev(); if (state.playing) startTimer();
    });
    on($("cg-memories-music"), "click", function (e) {
      e.preventDefault(); e.stopPropagation();
      state.musicOn = !state.musicOn; save(); music();
      this.textContent = state.musicOn ? "\u266A Music on" : "\u266A Music off";
    });
    var fx = $("cg-memories-effect");
    if (fx) {
      fx.value = state.effect;
      on(fx, "change", function () { state.effect = this.value; save(); render(); });
    }
    var ui = $("cg-memories-ui");
    if (ui) { ui.style.pointerEvents = "auto"; ui.style.zIndex = "30"; }
    render();
    if (state.on && state.playing) startTimer();
    music();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
  window.CGMemories = { init: init, addFiles: addFiles, setOn: setOn, setPlaying: setPlaying };
})();
