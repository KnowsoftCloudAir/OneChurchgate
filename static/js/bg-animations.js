/* Churchgate full-3D ambient scenes (Three.js) — emotionally rich, runs portal + books */
(function (global) {
  const MODES = [
    { id: 'none', name: 'None' },
    { id: 'sunset', name: 'Golden sunset' },
    { id: 'planets', name: 'Planets around the sun' },
    { id: 'starfield', name: 'Deep starfield' },
    { id: 'aurora', name: 'Northern lights' },
    { id: 'ocean_waves', name: 'Ocean waves' },
    { id: 'ocean_fish', name: 'Ocean depths' },
    { id: 'sky_run', name: 'Journey into the heavens' },
    { id: 'jupiter', name: 'Jupiter flyby' },
    { id: 'galaxy', name: 'Spiral galaxy' },
    { id: 'floating_orbs', name: 'Floating orbs of light' },
    { id: 'word_forms', name: 'Living words' },
    { id: 'great_men', name: 'Portraits from the sky' },
    { id: 'sunrise_ant', name: 'Sunrise meadow' },
  ];

  let renderer, scene, camera, animId, mode = 'none', paused = false;
  let clock, root, starPoints, extra = {};
  let threeReady = null;
  let wordQueue = [];
  let canvasHost = null;

  function loadThree() {
    if (global.THREE) return Promise.resolve(global.THREE);
    if (threeReady) return threeReady;
    threeReady = new Promise((resolve, reject) => {
      const s = document.createElement('script');
      s.src = 'https://cdnjs.cloudflare.com/ajax/libs/three.js/r134/three.min.js';
      s.onload = () => resolve(global.THREE);
      s.onerror = reject;
      document.head.appendChild(s);
    });
    return threeReady;
  }

  function ensureRenderer() {
    if (renderer) return;
    canvasHost = document.createElement('div');
    canvasHost.id = 'cgBgAnim3d';
    canvasHost.style.cssText = 'position:fixed;inset:0;z-index:0;pointer-events:none;opacity:0.92;';
    document.body.prepend(canvasHost);
    const THREE = global.THREE;
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setClearColor(0x020617, 1);
    canvasHost.appendChild(renderer.domElement);
    scene = new THREE.Scene();
    camera = new THREE.PerspectiveCamera(55, window.innerWidth / window.innerHeight, 0.1, 2000);
    camera.position.set(0, 2, 12);
    clock = new THREE.Clock();
    window.addEventListener('resize', onResize);
  }

  function onResize() {
    if (!renderer || !camera) return;
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
  }

  function clearScene() {
    if (!scene) return;
    while (scene.children.length) {
      const o = scene.children[0];
      scene.remove(o);
      if (o.geometry) o.geometry.dispose();
      if (o.material) {
        if (Array.isArray(o.material)) o.material.forEach((m) => m.dispose());
        else o.material.dispose();
      }
    }
    root = null;
    starPoints = null;
    extra = {};
  }

  function addStars(count, spread) {
    const THREE = global.THREE;
    const geo = new THREE.BufferGeometry();
    const pos = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      pos[i * 3] = (Math.random() - 0.5) * spread;
      pos[i * 3 + 1] = (Math.random() - 0.5) * spread;
      pos[i * 3 + 2] = (Math.random() - 0.5) * spread;
    }
    geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    const mat = new THREE.PointsMaterial({ color: 0xffffff, size: 0.06, transparent: true, opacity: 0.9 });
    starPoints = new THREE.Points(geo, mat);
    scene.add(starPoints);
  }

  function softLight() {
    const THREE = global.THREE;
    scene.add(new THREE.AmbientLight(0x404060, 0.6));
    const key = new THREE.DirectionalLight(0xffe4c4, 1.1);
    key.position.set(5, 8, 5);
    scene.add(key);
    const rim = new THREE.PointLight(0x88aaff, 0.8, 80);
    rim.position.set(-8, 4, -6);
    scene.add(rim);
  }

  function buildMode(id) {
    const THREE = global.THREE;
    clearScene();
    softLight();
    camera.position.set(0, 2, 12);
    camera.lookAt(0, 0, 0);

    if (id === 'sunset') {
      renderer.setClearColor(0x1a0a2e, 1);
      const sun = new THREE.Mesh(
        new THREE.SphereGeometry(1.6, 32, 32),
        new THREE.MeshBasicMaterial({ color: 0xffb347 })
      );
      sun.position.set(0, -0.5, -8);
      scene.add(sun);
      const glow = new THREE.PointLight(0xff8c42, 2.5, 60);
      glow.position.copy(sun.position);
      scene.add(glow);
      // horizon plane
      const ground = new THREE.Mesh(
        new THREE.PlaneGeometry(80, 40),
        new THREE.MeshStandardMaterial({ color: 0x2a1840, roughness: 0.9 })
      );
      ground.rotation.x = -Math.PI / 2;
      ground.position.y = -3;
      scene.add(ground);
      // floating clouds
      extra.clouds = [];
      for (let i = 0; i < 8; i++) {
        const c = new THREE.Mesh(
          new THREE.SphereGeometry(1.2 + Math.random(), 12, 12),
          new THREE.MeshStandardMaterial({ color: 0xffc9a3, transparent: true, opacity: 0.35 })
        );
        c.position.set((Math.random() - 0.5) * 20, 1 + Math.random() * 3, -6 - Math.random() * 8);
        c.scale.set(2.5, 0.6, 1.2);
        scene.add(c);
        extra.clouds.push(c);
      }
      extra.sun = sun;
    } else if (id === 'planets') {
      renderer.setClearColor(0x020617, 1);
      addStars(1200, 80);
      const sun = new THREE.Mesh(
        new THREE.SphereGeometry(1.4, 32, 32),
        new THREE.MeshBasicMaterial({ color: 0xffd166 })
      );
      scene.add(sun);
      scene.add(new THREE.PointLight(0xffcc66, 2, 50));
      extra.planets = [];
      const cols = [0x94a3b8, 0xf59e0b, 0x3b82f6, 0xef4444, 0xa78bfa, 0x34d399];
      cols.forEach((col, i) => {
        const p = new THREE.Mesh(
          new THREE.SphereGeometry(0.25 + i * 0.08, 24, 24),
          new THREE.MeshStandardMaterial({ color: col, roughness: 0.4, metalness: 0.2 })
        );
        const pivot = new THREE.Object3D();
        pivot.userData = { radius: 2.5 + i * 1.1, speed: 0.35 - i * 0.04, phase: p };
        p.position.x = pivot.userData.radius;
        pivot.add(p);
        scene.add(pivot);
        extra.planets.push(pivot);
      });
    } else if (id === 'starfield' || id === 'sky_run') {
      renderer.setClearColor(0x000010, 1);
      addStars(id === 'sky_run' ? 2500 : 1800, 100);
      camera.position.set(0, 0, 8);
      extra.drift = id === 'sky_run' ? 0.15 : 0.04;
      if (id === 'sky_run') {
        const neb = new THREE.Mesh(
          new THREE.SphereGeometry(30, 32, 32),
          new THREE.MeshBasicMaterial({ color: 0x1e1b4b, side: THREE.BackSide, transparent: true, opacity: 0.5 })
        );
        scene.add(neb);
      }
    } else if (id === 'aurora') {
      renderer.setClearColor(0x020617, 1);
      addStars(600, 60);
      extra.bands = [];
      for (let i = 0; i < 5; i++) {
        const geo = new THREE.PlaneGeometry(40, 6, 40, 8);
        const mat = new THREE.MeshBasicMaterial({
          color: new THREE.Color().setHSL(0.35 + i * 0.06, 0.7, 0.45),
          transparent: true,
          opacity: 0.22,
          side: THREE.DoubleSide,
        });
        const band = new THREE.Mesh(geo, mat);
        band.position.set(0, 2 + i * 1.2, -10);
        band.rotation.x = -0.3;
        scene.add(band);
        extra.bands.push(band);
      }
    } else if (id === 'ocean_waves' || id === 'ocean_fish') {
      renderer.setClearColor(0x0c4a6e, 1);
      const water = new THREE.Mesh(
        new THREE.PlaneGeometry(60, 60, 64, 64),
        new THREE.MeshStandardMaterial({ color: 0x0ea5e9, roughness: 0.2, metalness: 0.3, flatShading: true })
      );
      water.rotation.x = -Math.PI / 2;
      water.position.y = -1;
      scene.add(water);
      extra.water = water;
      scene.add(new THREE.DirectionalLight(0x87ceeb, 1.2));
      if (id === 'ocean_fish') {
        extra.fish = [];
        for (let i = 0; i < 12; i++) {
          const body = new THREE.Mesh(
            new THREE.SphereGeometry(0.25, 12, 12),
            new THREE.MeshStandardMaterial({ color: 0x38bdf8, roughness: 0.3 })
          );
          body.scale.set(2, 0.7, 1);
          body.position.set((Math.random() - 0.5) * 16, -0.5 + Math.random() * 3, (Math.random() - 0.5) * 10);
          scene.add(body);
          extra.fish.push(body);
        }
      }
      camera.position.set(0, 4, 14);
    } else if (id === 'jupiter') {
      renderer.setClearColor(0x020617, 1);
      addStars(900, 70);
      const jup = new THREE.Mesh(
        new THREE.SphereGeometry(2.2, 48, 48),
        new THREE.MeshStandardMaterial({ color: 0xd97706, roughness: 0.55 })
      );
      scene.add(jup);
      const sun = new THREE.Mesh(
        new THREE.SphereGeometry(0.5, 16, 16),
        new THREE.MeshBasicMaterial({ color: 0xffe566 })
      );
      sun.position.set(-8, 2, -12);
      scene.add(sun);
      scene.add(new THREE.PointLight(0xffcc66, 1.5, 40));
      extra.jup = jup;
      extra.phase = 0;
    } else if (id === 'galaxy') {
      renderer.setClearColor(0x000008, 1);
      const geo = new THREE.BufferGeometry();
      const n = 4000;
      const pos = new Float32Array(n * 3);
      const col = new Float32Array(n * 3);
      for (let i = 0; i < n; i++) {
        const arm = i % 3;
        const a = i * 0.05 + arm * 2.1;
        const r = (i * 0.004) % 12;
        pos[i * 3] = Math.cos(a) * r;
        pos[i * 3 + 1] = (Math.random() - 0.5) * 0.8;
        pos[i * 3 + 2] = Math.sin(a) * r;
        const c = new THREE.Color().setHSL(0.55 + arm * 0.1, 0.8, 0.6);
        col[i * 3] = c.r; col[i * 3 + 1] = c.g; col[i * 3 + 2] = c.b;
      }
      geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
      geo.setAttribute('color', new THREE.BufferAttribute(col, 3));
      const pts = new THREE.Points(geo, new THREE.PointsMaterial({ size: 0.05, vertexColors: true }));
      scene.add(pts);
      extra.galaxy = pts;
      camera.position.set(0, 8, 14);
      camera.lookAt(0, 0, 0);
    } else if (id === 'floating_orbs') {
      renderer.setClearColor(0x0f172a, 1);
      extra.orbs = [];
      for (let i = 0; i < 16; i++) {
        const mesh = new THREE.Mesh(
          new THREE.SphereGeometry(0.35 + Math.random() * 0.4, 20, 20),
          new THREE.MeshStandardMaterial({
            color: new THREE.Color().setHSL(Math.random(), 0.7, 0.55),
            emissive: new THREE.Color().setHSL(Math.random(), 0.5, 0.2),
            transparent: true,
            opacity: 0.85,
          })
        );
        mesh.position.set((Math.random() - 0.5) * 14, (Math.random() - 0.5) * 8, (Math.random() - 0.5) * 10);
        mesh.userData = { sp: 0.3 + Math.random() * 0.5, ph: Math.random() * 6 };
        scene.add(mesh);
        extra.orbs.push(mesh);
        const pl = new THREE.PointLight(mesh.material.color, 0.4, 8);
        mesh.add(pl);
      }
    } else if (id === 'word_forms') {
      renderer.setClearColor(0x111827, 1);
      extra.blocks = [];
      for (let i = 0; i < 10; i++) {
        const b = new THREE.Mesh(
          new THREE.BoxGeometry(1.2, 0.4, 0.2),
          new THREE.MeshStandardMaterial({ color: 0x818cf8, transparent: true, opacity: 0.7 })
        );
        b.position.set((Math.random() - 0.5) * 10, (Math.random() - 0.5) * 6, (Math.random() - 0.5) * 4);
        scene.add(b);
        extra.blocks.push(b);
      }
    } else if (id === 'great_men') {
      renderer.setClearColor(0x0f172a, 1);
      addStars(400, 50);
      extra.figures = [];
      for (let i = 0; i < 6; i++) {
        const g = new THREE.Group();
        const head = new THREE.Mesh(
          new THREE.SphereGeometry(0.35, 16, 16),
          new THREE.MeshStandardMaterial({ color: 0xe2e8f0 })
        );
        head.position.y = 0.9;
        const body = new THREE.Mesh(
          new THREE.CylinderGeometry(0.25, 0.4, 1.2, 12),
          new THREE.MeshStandardMaterial({ color: 0xcbd5e1 })
        );
        body.position.y = 0.1;
        g.add(head); g.add(body);
        g.position.set((i - 2.5) * 2.2, 8 + i * 2, -4);
        g.userData = { speed: 0.4 + Math.random() * 0.3 };
        scene.add(g);
        extra.figures.push(g);
      }
    } else if (id === 'sunrise_ant') {
      renderer.setClearColor(0x7c2d12, 1);
      const ground = new THREE.Mesh(
        new THREE.PlaneGeometry(40, 40),
        new THREE.MeshStandardMaterial({ color: 0x14532d, roughness: 0.95 })
      );
      ground.rotation.x = -Math.PI / 2;
      ground.position.y = -1;
      scene.add(ground);
      const sun = new THREE.Mesh(
        new THREE.SphereGeometry(1.2, 24, 24),
        new THREE.MeshBasicMaterial({ color: 0xfbbf24 })
      );
      sun.position.set(0, 3, -12);
      scene.add(sun);
      scene.add(new THREE.PointLight(0xfbbf24, 1.5, 40));
      // trees
      for (let i = 0; i < 10; i++) {
        const trunk = new THREE.Mesh(
          new THREE.CylinderGeometry(0.1, 0.15, 1.5, 8),
          new THREE.MeshStandardMaterial({ color: 0x5c4033 })
        );
        const leaf = new THREE.Mesh(
          new THREE.SphereGeometry(0.6, 10, 10),
          new THREE.MeshStandardMaterial({ color: 0x22c55e })
        );
        leaf.position.y = 1.1;
        const tree = new THREE.Group();
        tree.add(trunk); tree.add(leaf);
        tree.position.set((Math.random() - 0.5) * 18, -0.25, (Math.random() - 0.5) * 14 - 2);
        scene.add(tree);
      }
      const ant = new THREE.Mesh(
        new THREE.SphereGeometry(0.15, 10, 10),
        new THREE.MeshStandardMaterial({ color: 0x1c1917 })
      );
      ant.scale.set(1.8, 0.8, 1);
      ant.position.set(-6, -0.7, 2);
      scene.add(ant);
      extra.ant = ant;
      camera.position.set(0, 5, 12);
    }
  }

  function tick() {
    animId = requestAnimationFrame(tick);
    if (paused || mode === 'none' || !renderer) return;
    const t = clock.getElapsedTime();
    const dt = clock.getDelta();

    if (starPoints && (mode === 'starfield' || mode === 'sky_run')) {
      starPoints.rotation.y += (extra.drift || 0.02) * 0.15;
      starPoints.position.z += (extra.drift || 0) * 0.5;
      if (starPoints.position.z > 20) starPoints.position.z = 0;
    }
    if (extra.planets) {
      extra.planets.forEach((piv) => {
        piv.rotation.y += piv.userData.speed * 0.01;
        piv.rotation.x = Math.sin(t * 0.2) * 0.15;
      });
    }
    if (extra.sun && mode === 'sunset') {
      extra.sun.position.y = -0.5 + Math.sin(t * 0.2) * 0.15;
      (extra.clouds || []).forEach((c, i) => {
        c.position.x += 0.008 * (1 + i * 0.05);
        if (c.position.x > 14) c.position.x = -14;
      });
    }
    if (extra.water) {
      const pos = extra.water.geometry.attributes.position;
      for (let i = 0; i < pos.count; i++) {
        const x = pos.getX(i);
        const y = pos.getY(i);
        pos.setZ(i, Math.sin(x * 0.3 + t) * 0.25 + Math.cos(y * 0.25 + t * 0.8) * 0.2);
      }
      pos.needsUpdate = true;
      extra.water.geometry.computeVertexNormals();
    }
    if (extra.fish) {
      extra.fish.forEach((f, i) => {
        f.position.x += Math.sin(t + i) * 0.02;
        f.position.y = -0.2 + Math.sin(t * 0.8 + i) * 1.5;
        f.rotation.y = Math.sin(t + i) * 0.5;
      });
    }
    if (extra.jup) {
      extra.phase = (extra.phase || 0) + 0.004;
      const p = extra.phase % 2;
      if (p < 1) {
        extra.jup.position.x = -6 + p * 12;
        extra.jup.scale.setScalar(0.6 + p * 1.8);
      } else {
        extra.jup.position.x = 6 + (p - 1) * 8;
        extra.jup.scale.setScalar(2.4 - (p - 1) * 1.2);
      }
      extra.jup.rotation.y += 0.01;
    }
    if (extra.galaxy) extra.galaxy.rotation.y += 0.002;
    if (extra.orbs) {
      extra.orbs.forEach((o) => {
        o.position.y += Math.sin(t * o.userData.sp + o.userData.ph) * 0.01;
        o.rotation.y += 0.01;
      });
    }
    if (extra.bands) {
      extra.bands.forEach((b, i) => {
        b.position.y = 2 + i * 1.2 + Math.sin(t + i) * 0.3;
        b.material.opacity = 0.15 + 0.1 * Math.sin(t * 0.5 + i);
      });
    }
    if (extra.figures) {
      extra.figures.forEach((g) => {
        g.position.y -= g.userData.speed * 0.03;
        const s = Math.max(0.4, 1.5 - g.position.y * 0.05);
        g.scale.setScalar(s);
        if (g.position.y < -6) g.position.y = 10;
      });
    }
    if (extra.ant) {
      extra.ant.position.x = Math.sin(t * 0.4) * 6;
      extra.ant.position.z = 2 + Math.cos(t * 0.3) * 3;
    }
    if (extra.blocks) {
      extra.blocks.forEach((b, i) => {
        b.rotation.y += 0.01;
        b.position.y += Math.sin(t + i) * 0.005;
      });
    }

    // gentle camera breathe
    if (mode !== 'none') {
      camera.position.x = Math.sin(t * 0.15) * 0.4;
      camera.position.y += (2 + Math.sin(t * 0.2) * 0.15 - camera.position.y) * 0.02;
    }
    renderer.render(scene, camera);
  }

  async function setMode(id) {
    mode = id || 'none';
    localStorage.setItem('cg_bg_anim', mode);
    if (mode === 'none') {
      stop();
      if (canvasHost) canvasHost.style.display = 'none';
      return;
    }
    try {
      await loadThree();
      ensureRenderer();
      canvasHost.style.display = 'block';
      buildMode(mode);
      if (!animId) tick();
    } catch (e) {
      console.warn('3D anim failed, silent', e);
    }
  }

  function setPaused(p) {
    paused = !!p;
    localStorage.setItem('cg_bg_anim_paused', paused ? '1' : '0');
  }
  function stop() {
    if (animId) cancelAnimationFrame(animId);
    animId = null;
  }
  function toggleFullscreen() {
    const el = document.documentElement;
    if (!document.fullscreenElement) {
      (el.requestFullscreen || el.webkitRequestFullscreen || function () {}).call(el);
    } else {
      (document.exitFullscreen || document.webkitExitFullscreen || function () {}).call(document);
    }
  }
  function pushSpokenWord(text) {
    if (!text) return;
    wordQueue.push({ t: performance.now(), text: String(text).split(/\s+/).slice(0, 6).join(' ') });
    if (wordQueue.length > 5) wordQueue.shift();
  }

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
