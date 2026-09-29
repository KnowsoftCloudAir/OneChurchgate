/* Churchgate Books — Three.js WebGL scenes (optimized) */
(function (global) {
  'use strict';

  var MODES = [
    { id: 'none', name: 'None (use CSS ambience)' },
    { id: 'jupiter_close', name: 'Jupiter flyby close' },
    { id: 'milkyway', name: 'Milky Way stars (close pass)' },
    { id: 'wavelength', name: '3D wavelength' },
    { id: 'fishes3d', name: '3D ocean fishes' },
    { id: 'abstract', name: 'Abstract (water · sand · antimatter)' }
  ];

  var renderer, scene, camera, animId, mode = 'none', paused = false;
  var clock, host, canvas, extra = {};
  var dprCap = 1.5;
  var threeReady = null;

  function loadThree() {
    if (global.THREE) return Promise.resolve(global.THREE);
    if (threeReady) return threeReady;
    threeReady = new Promise(function (resolve, reject) {
      var s = document.createElement('script');
      s.src = 'https://cdnjs.cloudflare.com/ajax/libs/three.js/r134/three.min.js';
      s.onload = function () { resolve(global.THREE); };
      s.onerror = function () { reject(new Error('Three.js failed to load')); };
      document.head.appendChild(s);
      setTimeout(function () { if (!global.THREE) reject(new Error('Three.js timeout')); }, 15000);
    });
    return threeReady;
  }

  function ensureHost(parent) {
    host = document.getElementById('cgWebglHost');
    if (!host) {
      host = document.createElement('div');
      host.id = 'cgWebglHost';
      host.style.cssText = 'position:absolute;inset:0;z-index:2;pointer-events:none;display:none;';
      (parent || document.getElementById('sceneStage') || document.getElementById('stage') || document.body).appendChild(host);
    }
    return host;
  }

  function onResize() {
    if (!renderer || !camera) return;
    var w = host.clientWidth || window.innerWidth;
    var h = host.clientHeight || window.innerHeight;
    if (w < 2 || h < 2) { w = window.innerWidth; h = window.innerHeight; }
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    renderer.setSize(w, h, true);
  }

  function disposeObject(obj) {
    if (!obj) return;
    if (obj.geometry) obj.geometry.dispose();
    if (obj.material) {
      if (Array.isArray(obj.material)) obj.material.forEach(function (m) { m.dispose(); });
      else obj.material.dispose();
    }
  }

  function clearScene() {
    if (!scene) return;
    while (scene.children.length) {
      var o = scene.children[0];
      scene.remove(o);
      o.traverse(function (c) { disposeObject(c); });
    }
    extra = {};
  }

  /* —— 1. Jupiter close flyby (slow, large, realistic) —— */
  function buildJupiter(THREE) {
    renderer.setClearColor(0x02040a, 1);
    // stars
    var starGeo = new THREE.BufferGeometry();
    var n = 1800, pos = new Float32Array(n * 3);
    for (var i = 0; i < n; i++) {
      pos[i * 3] = (Math.random() - 0.5) * 120;
      pos[i * 3 + 1] = (Math.random() - 0.5) * 80;
      pos[i * 3 + 2] = (Math.random() - 0.5) * 120 - 20;
    }
    starGeo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    scene.add(new THREE.Points(starGeo, new THREE.PointsMaterial({ color: 0xffffff, size: 0.05, sizeAttenuation: true, transparent: true, opacity: 0.85 })));

    // Jupiter body — large, banded look via vertex colors
    var geo = new THREE.SphereGeometry(3.2, 64, 64);
    var cols = new Float32Array(geo.attributes.position.count * 3);
    for (var i = 0; i < geo.attributes.position.count; i++) {
      var y = geo.attributes.position.getY(i);
      var band = Math.sin(y * 3.2) * 0.5 + 0.5;
      cols[i * 3] = 0.72 + band * 0.2;
      cols[i * 3 + 1] = 0.45 + band * 0.15;
      cols[i * 3 + 2] = 0.22 + band * 0.08;
    }
    geo.setAttribute('color', new THREE.BufferAttribute(cols, 3));
    var mat = new THREE.MeshStandardMaterial({
      vertexColors: true,
      roughness: 0.55,
      metalness: 0.08,
      flatShading: false
    });
    var jup = new THREE.Mesh(geo, mat);
    jup.position.set(-14, 0.2, -18);
    scene.add(jup);
    // soft limb darkening via second shell
    var shell = new THREE.Mesh(
      new THREE.SphereGeometry(3.28, 32, 32),
      new THREE.MeshBasicMaterial({ color: 0x1a0f08, transparent: true, opacity: 0.18, side: THREE.BackSide })
    );
    jup.add(shell);

    scene.add(new THREE.AmbientLight(0x334455, 0.55));
    var sun = new THREE.DirectionalLight(0xffe6c0, 1.35);
    sun.position.set(8, 4, 10);
    scene.add(sun);
    var fill = new THREE.DirectionalLight(0x6688aa, 0.35);
    fill.position.set(-6, -2, 4);
    scene.add(fill);

    extra.jup = jup;
    extra.phase = 0; // 0..1 slow approach & pass
    camera.position.set(0, 0.6, 10);
    camera.lookAt(0, 0, -8);
  }

  /* —— 2. Milky Way — stars rush toward camera —— */
  function buildMilkyway(THREE) {
    renderer.setClearColor(0x000008, 1);
    var n = 4000;
    var geo = new THREE.BufferGeometry();
    var pos = new Float32Array(n * 3);
    var spd = new Float32Array(n);
    for (var i = 0; i < n; i++) {
      pos[i * 3] = (Math.random() - 0.5) * 40;
      pos[i * 3 + 1] = (Math.random() - 0.5) * 28;
      pos[i * 3 + 2] = -Math.random() * 80 - 2;
      spd[i] = 0.08 + Math.random() * 0.35;
    }
    geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    var pts = new THREE.Points(geo, new THREE.PointsMaterial({
      color: 0xe8eeff, size: 0.06, sizeAttenuation: true, transparent: true, opacity: 0.95
    }));
    scene.add(pts);
    // milky band haze
    var band = new THREE.Mesh(
      new THREE.PlaneGeometry(60, 16),
      new THREE.MeshBasicMaterial({ color: 0x8899cc, transparent: true, opacity: 0.08, depth: THREE.DoubleSide })
    );
    band.position.z = -30;
    scene.add(band);
    extra.stars = pts;
    extra.starSpeed = spd;
    camera.position.set(0, 0, 2);
    camera.lookAt(0, 0, -20);
  }

  /* —— 3. Dramatic 3D wavelength —— */
  function buildWavelength(THREE) {
    renderer.setClearColor(0x020617, 1);
    var segX = 80, segY = 50;
    var geo = new THREE.PlaneGeometry(36, 22, segX, segY);
    var mat = new THREE.MeshStandardMaterial({
      color: 0x22d3ee,
      emissive: 0x0e7490,
      emissiveIntensity: 0.25,
      roughness: 0.25,
      metalness: 0.55,
      side: THREE.DoubleSide,
      wireframe: false
    });
    var mesh = new THREE.Mesh(geo, mat);
    mesh.rotation.x = -Math.PI / 2.6;
    mesh.position.y = -1.5;
    scene.add(mesh);
    // second interference layer
    var geo2 = new THREE.PlaneGeometry(36, 22, 60, 40);
    var mat2 = new THREE.MeshStandardMaterial({
      color: 0xa78bfa,
      emissive: 0x4c1d95,
      emissiveIntensity: 0.2,
      transparent: true,
      opacity: 0.45,
      side: THREE.DoubleSide,
      wireframe: true
    });
    var mesh2 = new THREE.Mesh(geo2, mat2);
    mesh2.rotation.x = -Math.PI / 2.6;
    mesh2.position.y = -1.2;
    scene.add(mesh2);
    scene.add(new THREE.AmbientLight(0x445566, 0.6));
    var L = new THREE.PointLight(0x67e8f9, 1.4, 50);
    L.position.set(0, 6, 6);
    scene.add(L);
    extra.wave = mesh;
    extra.wave2 = mesh2;
    camera.position.set(0, 8, 14);
    camera.lookAt(0, 0, 0);
  }

  /* —— 4. Slow 3D fishes —— */
  function buildFishes(THREE) {
    renderer.setClearColor(0x021820, 1);
    // water gradient plane
    var water = new THREE.Mesh(
      new THREE.PlaneGeometry(50, 50, 40, 40),
      new THREE.MeshStandardMaterial({ color: 0x0e7490, transparent: true, opacity: 0.35, roughness: 0.3 })
    );
    water.rotation.x = -Math.PI / 2;
    water.position.y = -3;
    scene.add(water);
    extra.water = water;

    scene.add(new THREE.AmbientLight(0x226688, 0.7));
    var sun = new THREE.DirectionalLight(0xa5f3fc, 0.9);
    sun.position.set(5, 12, 5);
    scene.add(sun);
    // god rays approx
    var ray = new THREE.Mesh(
      new THREE.ConeGeometry(6, 18, 16, 1, true),
      new THREE.MeshBasicMaterial({ color: 0x7dd3fc, transparent: true, opacity: 0.06, side: THREE.DoubleSide })
    );
    ray.position.set(0, 6, -4);
    ray.rotation.x = Math.PI;
    scene.add(ray);

    extra.fishes = [];
    for (var i = 0; i < 14; i++) {
      var g = new THREE.Group();
      var body = new THREE.Mesh(
        new THREE.SphereGeometry(0.28, 12, 10),
        new THREE.MeshStandardMaterial({
          color: new THREE.Color().setHSL(0.52 + Math.random() * 0.12, 0.75, 0.55),
          roughness: 0.35,
          metalness: 0.2
        })
      );
      body.scale.set(2.1, 0.75, 1);
      g.add(body);
      var tail = new THREE.Mesh(
        new THREE.ConeGeometry(0.22, 0.4, 8),
        new THREE.MeshStandardMaterial({ color: 0x38bdf8, roughness: 0.4 })
      );
      tail.rotation.z = Math.PI / 2;
      tail.position.x = -0.55;
      g.add(tail);
      g.position.set(
        (Math.random() - 0.5) * 16,
        (Math.random() - 0.5) * 5,
        (Math.random() - 0.5) * 10 - 2
      );
      g.userData = {
        speed: 0.004 + Math.random() * 0.01,
        amp: 0.3 + Math.random() * 0.6,
        phase: Math.random() * Math.PI * 2,
        dir: Math.random() > 0.5 ? 1 : -1,
        yaw: Math.random() * Math.PI * 2
      };
      scene.add(g);
      extra.fishes.push(g);
    }
    camera.position.set(0, 1.5, 12);
    camera.lookAt(0, 0, 0);
  }

  /* —— 5. Abstract alien (water / sand / antimatter) —— */
  function buildAbstract(THREE) {
    renderer.setClearColor(0x050510, 1);
    // antimatter core
    var core = new THREE.Mesh(
      new THREE.IcosahedronGeometry(1.4, 2),
      new THREE.MeshStandardMaterial({
        color: 0xc4b5fd,
        emissive: 0x5b21b6,
        emissiveIntensity: 0.6,
        roughness: 0.2,
        metalness: 0.7,
        wireframe: false
      })
    );
    scene.add(core);
    var coreWire = new THREE.Mesh(
      new THREE.IcosahedronGeometry(1.55, 1),
      new THREE.MeshBasicMaterial({ color: 0xa78bfa, wireframe: true, transparent: true, opacity: 0.35 })
    );
    scene.add(coreWire);

    // sand ring
    var sandGeo = new THREE.TorusGeometry(3.2, 0.35, 12, 80);
    var sand = new THREE.Mesh(sandGeo, new THREE.MeshStandardMaterial({
      color: 0xd4a574, roughness: 0.9, metalness: 0.05
    }));
    sand.rotation.x = Math.PI / 2.5;
    scene.add(sand);

    // water ribbon
    var ribbon = new THREE.Mesh(
      new THREE.TorusKnotGeometry(2.1, 0.22, 120, 16),
      new THREE.MeshStandardMaterial({
        color: 0x22d3ee, emissive: 0x0891b2, emissiveIntensity: 0.35,
        transparent: true, opacity: 0.75, roughness: 0.25, metalness: 0.5
      })
    );
    scene.add(ribbon);

    // orbiting antimatter shards
    extra.shards = [];
    for (var i = 0; i < 18; i++) {
      var sh = new THREE.Mesh(
        new THREE.TetrahedronGeometry(0.18 + Math.random() * 0.15, 0),
        new THREE.MeshStandardMaterial({
          color: 0xf0abfc, emissive: 0xd946ef, emissiveIntensity: 0.5, roughness: 0.3
        })
      );
      sh.userData = { a: Math.random() * Math.PI * 2, r: 2.5 + Math.random() * 2.5, s: 0.2 + Math.random() * 0.4 };
      scene.add(sh);
      extra.shards.push(sh);
    }

    scene.add(new THREE.AmbientLight(0x444466, 0.55));
    var L = new THREE.PointLight(0xe9d5ff, 1.5, 30);
    L.position.set(3, 4, 5);
    scene.add(L);
    var L2 = new THREE.PointLight(0x22d3ee, 0.9, 20);
    L2.position.set(-4, -2, 3);
    scene.add(L2);

    extra.core = core;
    extra.coreWire = coreWire;
    extra.sand = sand;
    extra.ribbon = ribbon;
    camera.position.set(0, 2.5, 9);
    camera.lookAt(0, 0, 0);
  }

  function buildMode(id, THREE) {
    clearScene();
    if (id === 'jupiter_close') buildJupiter(THREE);
    else if (id === 'milkyway') buildMilkyway(THREE);
    else if (id === 'wavelength') buildWavelength(THREE);
    else if (id === 'fishes3d') buildFishes(THREE);
    else if (id === 'abstract') buildAbstract(THREE);
  }

  function tick() {
    animId = requestAnimationFrame(tick);
    if (paused || mode === 'none' || !renderer || !scene) return;
    var t = clock.getElapsedTime();
    var THREE = global.THREE;

    if (mode === 'jupiter_close' && extra.jup) {
      // Slow approach from left, grow, pass right — ~45s cycle
      extra.phase = (extra.phase || 0) + 0.0018;
      var p = extra.phase % 1;
      var x = -16 + p * 36;
      var z = -22 + Math.sin(p * Math.PI) * 6;
      var s = 0.55 + Math.sin(p * Math.PI) * 1.65;
      extra.jup.position.set(x, 0.15 + Math.sin(p * Math.PI) * 0.3, z);
      extra.jup.scale.setScalar(s);
      extra.jup.rotation.y += 0.0012;
      camera.position.x = Math.sin(t * 0.05) * 0.25;
      camera.lookAt(extra.jup.position.x * 0.3, 0, -6);
    }

    if (mode === 'milkyway' && extra.stars) {
      var pos = extra.stars.geometry.attributes.position;
      var spd = extra.starSpeed;
      for (var i = 0; i < pos.count; i++) {
        var z = pos.getZ(i) + spd[i] * 0.55;
        if (z > 3) {
          z = -80 - Math.random() * 20;
          pos.setX(i, (Math.random() - 0.5) * 40);
          pos.setY(i, (Math.random() - 0.5) * 28);
        }
        pos.setZ(i, z);
      }
      pos.needsUpdate = true;
      camera.rotation.z = Math.sin(t * 0.08) * 0.02;
    }

    if (mode === 'wavelength' && extra.wave) {
      var pos = extra.wave.geometry.attributes.position;
      for (var i = 0; i < pos.count; i++) {
        var x = pos.getX(i), y = pos.getY(i);
        var z = Math.sin(x * 0.45 + t * 1.4) * 1.1
              + Math.cos(y * 0.55 + t * 1.1) * 0.7
              + Math.sin((x + y) * 0.25 + t * 0.8) * 0.45;
        pos.setZ(i, z);
      }
      pos.needsUpdate = true;
      extra.wave.geometry.computeVertexNormals();
      if (extra.wave2) {
        var p2 = extra.wave2.geometry.attributes.position;
        for (var j = 0; j < p2.count; j++) {
          var xx = p2.getX(j), yy = p2.getY(j);
          p2.setZ(j, Math.sin(xx * 0.6 - t * 1.6) * 0.8 + Math.cos(yy * 0.4 + t) * 0.5);
        }
        p2.needsUpdate = true;
      }
      camera.position.x = Math.sin(t * 0.12) * 2;
      camera.lookAt(0, 0, 0);
    }

    if (mode === 'fishes3d' && extra.fishes) {
      extra.fishes.forEach(function (g) {
        var u = g.userData;
        u.yaw += u.speed * u.dir * 0.35;
        g.position.x += Math.cos(u.yaw) * u.speed * 2.2;
        g.position.z += Math.sin(u.yaw) * u.speed * 2.2;
        g.position.y += Math.sin(t * 0.6 + u.phase) * 0.004 * u.amp;
        g.rotation.y = -u.yaw + (u.dir > 0 ? 0 : Math.PI);
        if (g.position.x > 12) g.position.x = -12;
        if (g.position.x < -12) g.position.x = 12;
        if (g.position.z > 8) g.position.z = -10;
        if (g.position.z < -12) g.position.z = 6;
      });
      if (extra.water) {
        var wp = extra.water.geometry.attributes.position;
        for (var i = 0; i < wp.count; i++) {
          wp.setZ(i, Math.sin(wp.getX(i) * 0.3 + t) * 0.15 + Math.cos(wp.getY(i) * 0.25 + t * 0.7) * 0.12);
        }
        wp.needsUpdate = true;
      }
    }

    if (mode === 'abstract') {
      if (extra.core) { extra.core.rotation.y += 0.004; extra.core.rotation.x += 0.002; }
      if (extra.coreWire) { extra.coreWire.rotation.y -= 0.003; }
      if (extra.sand) { extra.sand.rotation.z += 0.002; extra.sand.rotation.x = Math.PI / 2.5 + Math.sin(t * 0.3) * 0.08; }
      if (extra.ribbon) { extra.ribbon.rotation.y += 0.006; extra.ribbon.rotation.z = Math.sin(t * 0.4) * 0.2; }
      if (extra.shards) {
        extra.shards.forEach(function (sh) {
          sh.userData.a += sh.userData.s * 0.012;
          sh.position.x = Math.cos(sh.userData.a) * sh.userData.r;
          sh.position.z = Math.sin(sh.userData.a) * sh.userData.r;
          sh.position.y = Math.sin(sh.userData.a * 1.3 + t) * 1.2;
          sh.rotation.x += 0.02;
          sh.rotation.y += 0.03;
        });
      }
      camera.position.x = Math.sin(t * 0.1) * 1.2;
      camera.position.y = 2.5 + Math.sin(t * 0.15) * 0.4;
      camera.lookAt(0, 0, 0);
    }

    renderer.render(scene, camera);
  }

  async function setMode(id, parentEl) {
    mode = id || 'none';
    try { localStorage.setItem('cg_webgl_mode', mode); } catch (e) {}
    if (mode === 'none') {
      stop();
      if (host) host.style.display = 'none';
      return;
    }
    ensureHost(parentEl);
    host.style.display = 'block';
    try {
      await loadThree();
      var THREE = global.THREE;
      if (!renderer) {
        renderer = new THREE.WebGLRenderer({
          antialias: true,
          alpha: false,
          powerPreference: 'high-performance',
          stencil: false,
          depth: true
        });
        renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, dprCap));
        renderer.outputEncoding = THREE.sRGBEncoding || 3001;
        host.innerHTML = '';
        host.appendChild(renderer.domElement);
        renderer.domElement.style.width = '100%';
        renderer.domElement.style.height = '100%';
        scene = new THREE.Scene();
        camera = new THREE.PerspectiveCamera(50, 1, 0.1, 500);
        clock = new THREE.Clock();
        window.addEventListener('resize', onResize, { passive: true });
      }
      onResize();
      buildMode(mode, THREE);
      if (!animId) tick();
    } catch (e) {
      console.warn('WebGL scene failed', e);
    }
  }

  function stop() {
    if (animId) cancelAnimationFrame(animId);
    animId = null;
  }

  function setPaused(p) { paused = !!p; }

  function attachTo(el) {
    if (!el) return;
    ensureHost(el);
    host.style.position = 'absolute';
    if (!el.contains(host)) el.appendChild(host);
    onResize();
  }

  global.CGWebGL = {
    MODES: MODES,
    setMode: setMode,
    setPaused: setPaused,
    stop: stop,
    attachTo: attachTo,
    getMode: function () { return mode; },
    isPaused: function () { return paused; }
  };
})(window);
