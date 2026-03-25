import { useState, useEffect, useRef } from "react";
import * as THREE from "three";

// ============================================================
// JARVIS Enclosure — Single source of truth
// Tabs: 3D View | 2D Diagrams | STL Files | Electronics BOM | Connections
// Matches STL files in jarvis/05-the-body/designs/stl/
// ============================================================

// Exact STL dimensions (keep in sync with generate_enclosure.py)
const STL = {
  base:       { w: 162, d: 161, h: 82,  tri: 512, kb: 25, file: "jarvis-base.stl" },
  top:        { w: 174, d: 174, h: 3,   tri: 256, kb: 13, file: "jarvis-top.stl" },
  frontBlank: { w: 160, d: 44,  h: 2,   tri: 304, kb: 15, file: "jarvis-front-blank.stl" },
  front5:     { w: 155, d: 76,  h: 2,   tri: 120, kb: 6,  file: "jarvis-front-screen-5in.stl" },
  front7:     { w: 170, d: 105, h: 2,   tri: 120, kb: 6,  file: "jarvis-front-screen-7in.stl" },
  grille:     { w: 52,  d: 52,  h: 2,   tri: 152, kb: 8,  file: "jarvis-grille.stl" },
};

const LED_COLORS = {
  jarvis: "#4FC3F7", devesh: "#FF9800",
  chandler: "#E040FB", girlfriend: "#FF4081",
};

// ----- THREE.JS 3D VIEWER -----
function ThreeViewer({ phase, personality, screenSize }) {
  const mountRef = useRef(null);
  const sceneRef = useRef(null);
  const cameraRef = useRef(null);
  const rendererRef = useRef(null);
  const groupRef = useRef(null);
  const frameRef = useRef(null);
  const mouseRef = useRef({ down: false, x: 0, y: 0, rotX: 0.3, rotY: -0.4, dist: 1.0 });
  const [autoRotate, setAutoRotate] = useState(true);

  // Scale: 1 unit = 1mm, then scale down for viewing
  const S = 0.006; // mm to scene units

  useEffect(() => {
    const container = mountRef.current;
    if (!container) return;

    const w = container.clientWidth;
    const h = 450;

    // Scene
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xf5f2ed);
    sceneRef.current = scene;

    // Camera
    const camera = new THREE.PerspectiveCamera(35, w / h, 0.1, 100);
    camera.position.set(2.2, 1.5, 2.2);
    camera.lookAt(0, 0, 0);
    cameraRef.current = camera;

    // Renderer
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(w, h);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    container.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    // Lights
    const ambient = new THREE.AmbientLight(0xffffff, 0.6);
    scene.add(ambient);

    const key = new THREE.DirectionalLight(0xffffff, 0.8);
    key.position.set(3, 4, 2);
    key.castShadow = true;
    scene.add(key);

    const fill = new THREE.DirectionalLight(0xb0c4de, 0.3);
    fill.position.set(-2, 1, -1);
    scene.add(fill);

    const rim = new THREE.DirectionalLight(0xfff5e6, 0.2);
    rim.position.set(0, -1, -3);
    scene.add(rim);

    // Ground plane
    const groundGeo = new THREE.PlaneGeometry(8, 8);
    const groundMat = new THREE.ShadowMaterial({ opacity: 0.1 });
    const ground = new THREE.Mesh(groundGeo, groundMat);
    ground.rotation.x = -Math.PI / 2;
    ground.position.y = -0.5;
    ground.receiveShadow = true;
    scene.add(ground);

    // Grid helper (subtle)
    const grid = new THREE.GridHelper(4, 20, 0xe0dbd4, 0xede8e1);
    grid.position.y = -0.5;
    scene.add(grid);

    // Build enclosure group
    const group = new THREE.Group();
    groupRef.current = group;
    scene.add(group);

    // Animate
    function animate() {
      frameRef.current = requestAnimationFrame(animate);
      renderer.render(scene, camera);
    }
    animate();

    // Cleanup
    return () => {
      cancelAnimationFrame(frameRef.current);
      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
      renderer.dispose();
    };
  }, []);

  // Rebuild geometry when phase/personality/screenSize changes
  useEffect(() => {
    const group = groupRef.current;
    if (!group) return;

    // Clear old children
    while (group.children.length > 0) {
      const child = group.children[0];
      if (child.geometry) child.geometry.dispose();
      if (child.material) child.material.dispose();
      group.remove(child);
    }

    const led = new THREE.Color(LED_COLORS[personality] || LED_COLORS.jarvis);
    const hasScreen = phase === 2;

    // ========================================================
    // SCREEN-DRIVEN SIZING — EVERYTHING INTERNAL
    // All components inside. Only ports visible from back.
    // Layout verified with real component dimensions.
    // ========================================================
    const screenModuleW = screenSize === 7 ? 165 : 133;
    const screenModuleH = screenSize === 7 ? 100 : 85;
    const screenModuleD = screenSize === 7 ? 12 : 10;
    const screenActiveW = screenSize === 7 ? 154 : 121;
    const screenActiveH = screenSize === 7 ? 86 : 76;

    // Component dimensions (mm)
    const wall = 3;
    const topThick = 3;
    const jetsonW = 100; // carrier + module
    const jetsonD = 79;
    const jetsonH = 31;  // carrier 21 + module 10
    const spkDia = 50;
    const spkH = 20;
    const respeakerH = 12;
    const ledRingH = 3;
    const usbCodecD = 24;
    const cableGap = 18;

    // WIDTH: screen or Jetson+codec, whichever wider
    const intW = Math.max(screenModuleW, jetsonW + usbCodecD + 5);
    const encW = intW + wall * 2;
    // DEPTH: screen + cables + Jetson + port clearance
    const intD = (hasScreen ? screenModuleD : 5) + cableGap + jetsonD + 10;
    const encD = intD + wall * 2;
    // HEIGHT: top zone (LED+ReSpeaker) + Jetson + speaker
    const topZone = ledRingH + respeakerH + 3;
    const mainZone = jetsonH + 5;
    const bottomZone = spkH + 3;
    const intH = topZone + mainZone + bottomZone;
    const encH = intH + wall * 2 + topThick;

    // Convert to scene units
    const bw = encW * S;
    const bd = encD * S;
    const bh = encH * S;
    const th = topThick * S;
    const wl = wall * S;

    // Materials
    const shellMat = new THREE.MeshStandardMaterial({
      color: 0x2a2a2a, roughness: 0.4, metalness: 0.15,
    });
    const topMat = new THREE.MeshStandardMaterial({
      color: 0x333333, roughness: 0.35, metalness: 0.15,
    });
    const accentMat = new THREE.MeshStandardMaterial({
      color: 0x1a1a1a, roughness: 0.3, metalness: 0.2,
    });
    const screenBezelMat = new THREE.MeshStandardMaterial({
      color: 0x111111, roughness: 0.2, metalness: 0.1,
    });
    const screenGlowMat = new THREE.MeshStandardMaterial({
      color: 0x0d1525, roughness: 0.1, metalness: 0.05,
      emissive: 0x0a1530, emissiveIntensity: 0.6,
    });
    const ledMat = new THREE.MeshStandardMaterial({
      color: led, emissive: led, emissiveIntensity: 0.9, roughness: 0.3,
    });
    const grilleMat = new THREE.MeshStandardMaterial({
      color: 0x444444, roughness: 0.7, metalness: 0.3,
    });
    const jetsonMat = new THREE.MeshStandardMaterial({
      color: 0x76b900, roughness: 0.6, metalness: 0.1, transparent: true, opacity: 0.6,
    });
    const speakerMat = new THREE.MeshStandardMaterial({
      color: 0x2a2a2a, roughness: 0.8, metalness: 0.15,
    });
    const portMat = new THREE.MeshStandardMaterial({
      color: 0x555555, roughness: 0.5, metalness: 0.3,
    });
    const portInnerMat = new THREE.MeshStandardMaterial({
      color: 0x111111, roughness: 0.9, metalness: 0.05,
    });
    const oledMat = new THREE.MeshStandardMaterial({
      color: 0x111111, roughness: 0.3, metalness: 0.2,
    });
    const oledGlowMat = new THREE.MeshStandardMaterial({
      color: led, emissive: led, emissiveIntensity: 0.4, roughness: 0.3,
    });

    // --- BASE SHELL ---
    const baseGeo = new THREE.BoxGeometry(bw, bh, bd);
    const base = new THREE.Mesh(baseGeo, shellMat);
    base.castShadow = true;
    base.receiveShadow = true;
    group.add(base);

    // --- ACCENT STRIPE (thin line around the middle) ---
    const stripeMat = new THREE.MeshStandardMaterial({
      color: led, emissive: led, emissiveIntensity: 0.3,
      transparent: true, opacity: 0.6, roughness: 0.3,
    });
    const stripeGeo = new THREE.BoxGeometry(bw + 0.002, 2 * S, bd + 0.002);
    const stripe = new THREE.Mesh(stripeGeo, stripeMat);
    stripe.position.y = hasScreen ? (bh / 2 - screenModuleH * S - wl) : 0;
    group.add(stripe);

    // --- TOP PLATE ---
    const topGeo = new THREE.BoxGeometry(bw + 0.005, th, bd + 0.005);
    const top = new THREE.Mesh(topGeo, topMat);
    top.position.y = bh / 2 + th / 2;
    top.castShadow = true;
    group.add(top);

    // --- LED STRIP (around top edge) ---
    const ledCount = 24;
    const ledRadius = 0.006;
    for (let i = 0; i < ledCount; i++) {
      const t = i / ledCount;
      const perimeter = 2 * (bw + bd);
      const pos = t * perimeter;
      let lx, lz;
      if (pos < bw) {
        lx = -bw / 2 + pos; lz = -bd / 2;
      } else if (pos < bw + bd) {
        lx = bw / 2; lz = -bd / 2 + (pos - bw);
      } else if (pos < 2 * bw + bd) {
        lx = bw / 2 - (pos - bw - bd); lz = bd / 2;
      } else {
        lx = -bw / 2; lz = bd / 2 - (pos - 2 * bw - bd);
      }
      const ledGeo = new THREE.SphereGeometry(ledRadius, 8, 8);
      const ledDot = new THREE.Mesh(ledGeo, ledMat);
      ledDot.position.set(lx, bh / 2 + th + 0.002, lz);
      group.add(ledDot);
    }

    // --- LED GLOW RING (subtle halo) ---
    const glowGeo = new THREE.TorusGeometry(
      Math.min(bw, bd) / 2 * 0.85, 0.006, 8, 40
    );
    const glowMat2 = new THREE.MeshStandardMaterial({
      color: led, emissive: led, emissiveIntensity: 0.3,
      transparent: true, opacity: 0.2, roughness: 0.5,
    });
    const glowRing = new THREE.Mesh(glowGeo, glowMat2);
    glowRing.rotation.x = -Math.PI / 2;
    glowRing.position.y = bh / 2 + th + 0.004;
    group.add(glowRing);

    // --- MIC HOLES (4 corners of top) ---
    const micSpread = Math.min(bw, bd) * 0.35;
    const micPositions = [
      [-micSpread, 0, -micSpread], [micSpread, 0, -micSpread],
      [-micSpread, 0, micSpread], [micSpread, 0, micSpread],
    ];
    micPositions.forEach(function(mp) {
      var micGeo = new THREE.CylinderGeometry(2 * S, 2 * S, th + 0.01, 12);
      var mic = new THREE.Mesh(micGeo, accentMat);
      mic.position.set(mp[0], bh / 2 + th / 2, mp[2]);
      group.add(mic);
    });

    // --- STATUS OLED ON TOP ---
    const oledW = 35 * S;
    const oledH = 18 * S;
    const oledGeo = new THREE.BoxGeometry(oledW, 0.008, oledH);
    const oled = new THREE.Mesh(oledGeo, oledMat);
    oled.position.set(0, bh / 2 + th + 0.004, 0);
    group.add(oled);
    // OLED screen glow
    const oledScrGeo = new THREE.BoxGeometry(oledW - 4 * S, 0.004, oledH - 4 * S);
    const oledScr = new THREE.Mesh(oledScrGeo, oledGlowMat);
    oledScr.position.set(0, bh / 2 + th + 0.007, 0);
    group.add(oledScr);

    // --- FRONT FACE ---
    if (hasScreen) {
      // SCREEN MODE: Screen covers the ENTIRE front face edge-to-edge
      // The enclosure front IS the screen — no visible enclosure bezel
      const smW = screenModuleW * S;
      const smH = screenModuleH * S;
      const saW = screenActiveW * S;
      const saH = screenActiveH * S;

      // Screen module fills the top portion of the front face
      // Thin bezel frame (the screen module's own bezel, ~2mm)
      const bezelGeo = new THREE.BoxGeometry(smW, smH, wl);
      const bezel = new THREE.Mesh(bezelGeo, screenBezelMat);
      bezel.position.set(0, bh / 2 - smH / 2 - wl, -bd / 2 - wl / 2);
      bezel.castShadow = true;
      group.add(bezel);

      // Active screen area (glowing)
      const scrGeo = new THREE.BoxGeometry(saW, saH, 0.004);
      const scr = new THREE.Mesh(scrGeo, screenGlowMat);
      scr.position.set(0, bh / 2 - smH / 2 - wl, -bd / 2 - wl - 0.003);
      group.add(scr);

      // Below the screen: speaker grille strip (bottom-firing sound channel exit)
      const grillStripH = bh - smH - wl * 2;
      if (grillStripH > 0) {
        // Grille strip across bottom of front
        const gsGeo = new THREE.BoxGeometry(bw * 0.7, grillStripH, wl);
        const gs = new THREE.Mesh(gsGeo, grilleMat);
        gs.position.set(0, -bh / 2 + grillStripH / 2 + wl, -bd / 2 - wl / 2);
        group.add(gs);
        // Grille slot lines
        var slotCount = Math.floor(grillStripH / (3 * S));
        for (var si = 0; si < slotCount; si++) {
          var slotGeo = new THREE.BoxGeometry(bw * 0.6, 1 * S, wl + 0.002);
          var slot = new THREE.Mesh(slotGeo, accentMat);
          slot.position.set(0, -bh / 2 + wl + (si + 0.5) * 3 * S, -bd / 2 - wl / 2);
          group.add(slot);
        }
      }
    } else {
      // BLANK FRONT (Phase 1): speaker grille centered, clean panel
      const panelGeo = new THREE.BoxGeometry(bw, bh, wl);
      const panel = new THREE.Mesh(panelGeo, shellMat);
      panel.position.set(0, 0, -bd / 2 - wl / 2);
      panel.castShadow = true;
      group.add(panel);

      // Circular speaker grille
      const grilleR = 28 * S;
      const grilleBack = new THREE.Mesh(
        new THREE.CylinderGeometry(grilleR, grilleR, wl + 0.002, 32),
        grilleMat
      );
      grilleBack.rotation.x = Math.PI / 2;
      grilleBack.position.set(0, -8 * S, -bd / 2 - wl / 2);
      group.add(grilleBack);

      // Concentric ring grille pattern
      for (var ri = 1; ri <= 4; ri++) {
        var ringGeo = new THREE.TorusGeometry(grilleR * ri / 4, 1 * S, 8, 32);
        var ring = new THREE.Mesh(ringGeo, accentMat);
        ring.position.set(0, -8 * S, -bd / 2 - wl - 0.002);
        group.add(ring);
      }
    }

    // --- INTERNAL LAYOUT (top to bottom) ---
    // Y coords: top of internal space = bh/2 - wl - topThick*S
    var yTop = bh / 2 - wl;
    var yBot = -bh / 2 + wl;

    // Layer 1 (top): ReSpeaker 4-mic (plugs onto GPIO, under top plate)
    var respeakerMat = new THREE.MeshStandardMaterial({
      color: 0x2d8c3c, roughness: 0.5, metalness: 0.1, transparent: true, opacity: 0.7,
    });
    var rsW = 65 * S;
    var rsH = respeakerH * S;
    var rsGeo = new THREE.BoxGeometry(rsW, rsH, rsW);
    var rs = new THREE.Mesh(rsGeo, respeakerMat);
    rs.position.set(0, yTop - ledRingH * S - rsH / 2, 5 * S);
    group.add(rs);
    // Mic holes visible on ReSpeaker (4 dots)
    var micDotMat = new THREE.MeshStandardMaterial({ color: 0x111111, roughness: 0.9 });
    var micSpots = [[-20, -20], [20, -20], [-20, 20], [20, 20]];
    micSpots.forEach(function(mp) {
      var mdGeo = new THREE.CylinderGeometry(3 * S, 3 * S, rsH + 0.002, 8);
      var md = new THREE.Mesh(mdGeo, micDotMat);
      md.position.set(mp[0] * S, yTop - ledRingH * S - rsH / 2, mp[1] * S + 5 * S);
      group.add(md);
    });

    // Layer 2 (middle): Jetson Orin Nano
    var jetW = jetsonW * S;
    var jetD = jetsonD * S;
    var jetH = jetsonH * S;
    var yJetTop = yTop - (topZone) * S;
    var jetGeo = new THREE.BoxGeometry(jetW, jetH, jetD);
    var jet = new THREE.Mesh(jetGeo, jetsonMat);
    // Jetson sits in the back half (behind screen + cable gap)
    var jetZ = hasScreen ? bd / 2 - 10 * S - jetD / 2 : 5 * S;
    jet.position.set(-5 * S, yJetTop - jetH / 2, jetZ);
    group.add(jet);

    // USB Audio Codec beside Jetson
    var codecMat = new THREE.MeshStandardMaterial({
      color: 0x1a5276, roughness: 0.5, metalness: 0.15, transparent: true, opacity: 0.7,
    });
    var codecGeo = new THREE.BoxGeometry(50 * S, 14 * S, 24 * S);
    var codec = new THREE.Mesh(codecGeo, codecMat);
    codec.position.set(jetW / 2 + 15 * S, yJetTop - 14 * S / 2, jetZ);
    group.add(codec);

    // Layer 3 (bottom): Speaker
    var spkR = (spkDia / 2) * S;
    var spkDepth = spkH * S;
    var spkGeo = new THREE.CylinderGeometry(spkR, spkR, spkDepth, 20);
    var spk = new THREE.Mesh(spkGeo, speakerMat);
    if (hasScreen) {
      // Bottom-firing: cone points down
      spk.position.set(0, yBot + spkDepth / 2 + 2 * S, 0);
    } else {
      // Front-firing: cone faces front panel
      spk.rotation.x = Math.PI / 2;
      spk.position.set(0, -8 * S, -bd / 2 + spkDepth / 2 + wl);
    }
    group.add(spk);

    // --- BACK PANEL PORTS (recessed cutouts with depth) ---
    // Ports are on the BACK face (positive Z), spread horizontally
    var portDefs = [
      { w: 18, h: 9, x: -40, label: "HDMI", color: 0x3366cc },
      { w: 14, h: 7, x: -12, label: "USB 3.0", color: 0x3399ff },
      { w: 14, h: 7, x: 12, label: "USB 2.0", color: 0x888888 },
      { w: 8,  h: 8, x: 30, label: "Audio", color: 0x33cc33 },
      { w: 10, h: 6, x: 48, label: "USB-C", color: 0xcc6633 },
    ];
    portDefs.forEach(function(p) {
      // Port surround (raised bezel)
      var surroundGeo = new THREE.BoxGeometry((p.w + 4) * S, (p.h + 4) * S, 2 * S);
      var surroundMat = new THREE.MeshStandardMaterial({
        color: p.color, roughness: 0.4, metalness: 0.3,
      });
      var surround = new THREE.Mesh(surroundGeo, surroundMat);
      surround.position.set(p.x * S, -5 * S, bd / 2 + 1 * S);
      group.add(surround);
      // Port hole (dark recess)
      var holeGeo = new THREE.BoxGeometry(p.w * S, p.h * S, 3 * S);
      var hole = new THREE.Mesh(holeGeo, portInnerMat);
      hole.position.set(p.x * S, -5 * S, bd / 2 + 1.5 * S);
      group.add(hole);
    });

    // --- VENTILATION SLOTS (bottom) ---
    var ventCount = Math.floor(bw / (8 * S));
    for (var vi = 0; vi < ventCount; vi++) {
      var ventGeo = new THREE.BoxGeometry(5 * S, wl + 0.002, 40 * S);
      var vent = new THREE.Mesh(ventGeo, accentMat);
      vent.position.set(-bw / 2 + (vi + 0.5) * (bw / ventCount), -bh / 2, 0);
      group.add(vent);
    }

    // --- RUBBER FEET (4 corners, bottom) ---
    var footR = 5 * S;
    var footH = 3 * S;
    var footInset = 15 * S;
    var footPositions = [
      [-bw / 2 + footInset, -bh / 2 - footH / 2, -bd / 2 + footInset],
      [bw / 2 - footInset, -bh / 2 - footH / 2, -bd / 2 + footInset],
      [-bw / 2 + footInset, -bh / 2 - footH / 2, bd / 2 - footInset],
      [bw / 2 - footInset, -bh / 2 - footH / 2, bd / 2 - footInset],
    ];
    var footMat = new THREE.MeshStandardMaterial({ color: 0x444444, roughness: 0.9 });
    footPositions.forEach(function(fp) {
      var fGeo = new THREE.CylinderGeometry(footR, footR, footH, 12);
      var foot = new THREE.Mesh(fGeo, footMat);
      foot.position.set(fp[0], fp[1], fp[2]);
      group.add(foot);
    });

    // --- REFERENCE OBJECT: Coke can (120mm tall, 33mm radius) ---
    const canH = 120 * S;
    const canR = 33 * S;
    const canMat = new THREE.MeshStandardMaterial({
      color: 0xcc0000, roughness: 0.3, metalness: 0.6,
    });
    const canTopMat = new THREE.MeshStandardMaterial({
      color: 0xcccccc, roughness: 0.2, metalness: 0.8,
    });
    const canGeo = new THREE.CylinderGeometry(canR, canR, canH, 24);
    const can = new THREE.Mesh(canGeo, canMat);
    can.position.set(bw / 2 + canR + 15 * S, -bh / 2 + canH / 2, 0);
    can.castShadow = true;
    group.add(can);
    const canTopGeo = new THREE.CylinderGeometry(canR - 2 * S, canR, 3 * S, 24);
    const canTop = new THREE.Mesh(canTopGeo, canTopMat);
    canTop.position.set(bw / 2 + canR + 15 * S, -bh / 2 + canH + 1.5 * S, 0);
    group.add(canTop);
    const canLabelMat = new THREE.MeshStandardMaterial({
      color: 0xffffff, roughness: 0.5, metalness: 0.1,
    });
    const canLabelGeo = new THREE.CylinderGeometry(canR + 0.001, canR + 0.001, canH * 0.3, 24, 1, true);
    const canLabel = new THREE.Mesh(canLabelGeo, canLabelMat);
    canLabel.position.set(bw / 2 + canR + 15 * S, -bh / 2 + canH / 2, 0);
    group.add(canLabel);

  }, [phase, personality, screenSize]);

  // Auto-rotate + zoom
  useEffect(() => {
    let raf;
    function tick() {
      const group = groupRef.current;
      const m = mouseRef.current;
      if (group) {
        if (autoRotate && !m.down) {
          m.rotY -= 0.003;
        }
        group.rotation.y = m.rotY;
        group.rotation.x = m.rotX;
      }
      const camera = cameraRef.current;
      if (camera) {
        const d = m.dist;
        camera.position.set(2.2 * d, 1.5 * d, 2.2 * d);
        camera.lookAt(0, 0, 0);
      }
      const renderer = rendererRef.current;
      const scene = sceneRef.current;
      if (renderer && scene && camera) {
        renderer.render(scene, camera);
      }
      raf = requestAnimationFrame(tick);
    }
    tick();
    return () => cancelAnimationFrame(raf);
  }, [autoRotate]);

  // Mouse drag for orbit
  useEffect(() => {
    const el = mountRef.current;
    if (!el) return;

    function onDown(e) {
      mouseRef.current.down = true;
      mouseRef.current.x = e.clientX || (e.touches && e.touches[0].clientX);
      mouseRef.current.y = e.clientY || (e.touches && e.touches[0].clientY);
    }
    function onMove(e) {
      const m = mouseRef.current;
      if (!m.down) return;
      const cx = e.clientX || (e.touches && e.touches[0].clientX);
      const cy = e.clientY || (e.touches && e.touches[0].clientY);
      const dx = cx - m.x;
      const dy = cy - m.y;
      m.rotY += dx * 0.005;
      m.rotX += dy * 0.005;
      m.rotX = Math.max(-1, Math.min(1, m.rotX));
      m.x = cx;
      m.y = cy;
    }
    function onUp() { mouseRef.current.down = false; }
    function onWheel(e) {
      e.preventDefault();
      const m = mouseRef.current;
      m.dist = Math.max(0.3, Math.min(3.0, m.dist + e.deltaY * 0.001));
    }

    el.addEventListener("mousedown", onDown);
    el.addEventListener("mousemove", onMove);
    el.addEventListener("mouseup", onUp);
    el.addEventListener("mouseleave", onUp);
    el.addEventListener("touchstart", onDown);
    el.addEventListener("touchmove", onMove);
    el.addEventListener("touchend", onUp);
    el.addEventListener("wheel", onWheel, { passive: false });

    return () => {
      el.removeEventListener("mousedown", onDown);
      el.removeEventListener("mousemove", onMove);
      el.removeEventListener("mouseup", onUp);
      el.removeEventListener("mouseleave", onUp);
      el.removeEventListener("touchstart", onDown);
      el.removeEventListener("touchmove", onMove);
      el.removeEventListener("touchend", onUp);
      el.removeEventListener("wheel", onWheel);
    };
  }, []);

  return (
    <div>
      <div ref={mountRef} style={{ width: "100%", height: 450, cursor: "grab", borderRadius: 16, overflow: "hidden" }} />
      <div className="flex items-center gap-4 mt-3">
        <p className="text-xs text-gray-400">Drag to rotate, scroll to zoom. Red can = standard 330ml Coke can for scale.</p>
        <label className="flex items-center gap-1.5 text-xs text-gray-500 cursor-pointer ml-auto">
          <input type="checkbox" checked={autoRotate} onChange={() => setAutoRotate(!autoRotate)} className="rounded" />
          Auto-rotate
        </label>
      </div>
    </div>
  );
}

// ----- 3/4 Hero View -----
function HeroView({ phase, personality, screenSize }) {
  const led = LED_COLORS[personality] || LED_COLORS.jarvis;
  const hasScreen = phase === 2;

  return (
    <svg viewBox="0 0 520 440" style={{ width: "100%", maxWidth: 520 }}>
      <defs>
        <filter id="glow">
          <feGaussianBlur stdDeviation="5" result="b" />
          <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
        <linearGradient id="bodyG" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#F0EBE3" /><stop offset="100%" stopColor="#D9D0C4" />
        </linearGradient>
        <linearGradient id="sideG" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="#D9D0C4" /><stop offset="100%" stopColor="#C4B8A8" />
        </linearGradient>
        <linearGradient id="topG" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#F5F0E8" /><stop offset="100%" stopColor="#EDE7DC" />
        </linearGradient>
        <linearGradient id="scrG" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#1a1a2e" /><stop offset="100%" stopColor="#0f0f1a" />
        </linearGradient>
      </defs>

      {/* Shadow */}
      <ellipse cx="260" cy="400" rx="190" ry="22" fill="rgba(0,0,0,0.07)" />

      {/* Right side */}
      <path d="M395,155 L435,190 L435,340 L395,370Z" fill="url(#sideG)" stroke="#C4B8A8" strokeWidth="0.5" />

      {/* Front face */}
      <path d="M85,155 L395,155 L395,370 L85,370Z" fill="url(#bodyG)" stroke="#D9D0C4" strokeWidth="0.5" />

      {/* Front panel content */}
      {hasScreen ? (
        <g>
          <rect x="95" y="165" width="290" height="195" rx="8" fill="#1a1a1a" />
          {screenSize === 7 ? (
            <g>
              <rect x="100" y="170" width="280" height="175" rx="4" fill="url(#scrG)" />
              <text x="240" y="230" textAnchor="middle" fill="#4FC3F7" fontSize="16" fontFamily="monospace" fontWeight="bold">JARVIS</text>
              <text x="240" y="255" textAnchor="middle" fill="#666" fontSize="10" fontFamily="monospace">How can I help you?</text>
              <text x="140" y="310" textAnchor="middle" fill="#888" fontSize="22" fontFamily="monospace">10:42</text>
              <text x="320" y="300" textAnchor="middle" fill="#FF9800" fontSize="12" fontFamily="monospace">28 C</text>
              <text x="320" y="315" textAnchor="middle" fill="#666" fontSize="8" fontFamily="monospace">Mumbai</text>
              <rect x="110" y="330" width="260" height="8" rx="4" fill="#222" />
              <rect x="110" y="330" width="140" height="8" rx="4" fill={led} opacity="0.5" />
              <text x="240" y="326" textAnchor="middle" fill="#aaa" fontSize="7" fontFamily="monospace">Sajni - Jal The Band</text>
              <text x="385" y="260" fill="#555" fontSize="7" fontFamily="monospace" transform="rotate(90,385,260)">7 inch IPS 1024x600</text>
            </g>
          ) : (
            <g>
              <rect x="115" y="180" width="250" height="155" rx="4" fill="url(#scrG)" />
              <text x="240" y="235" textAnchor="middle" fill="#4FC3F7" fontSize="14" fontFamily="monospace" fontWeight="bold">JARVIS</text>
              <text x="240" y="255" textAnchor="middle" fill="#666" fontSize="9" fontFamily="monospace">How can I help you?</text>
              <text x="175" y="310" textAnchor="middle" fill="#888" fontSize="18" fontFamily="monospace">10:42</text>
              <text x="300" y="310" textAnchor="middle" fill="#FF9800" fontSize="10" fontFamily="monospace">28 C</text>
              <text x="385" y="265" fill="#555" fontSize="7" fontFamily="monospace" transform="rotate(90,385,265)">5 inch HDMI 800x480</text>
            </g>
          )}
          <text x="240" y="362" textAnchor="middle" fill="#888" fontSize="7" fontFamily="monospace">HDMI + USB Touch (plug-and-play)</text>
        </g>
      ) : (
        <g>
          {/* Speaker grille */}
          <circle cx="340" cy="270" r="28" fill="#3D3D3D" />
          <circle cx="340" cy="270" r="26" fill="#555" />
          {[0,1,2,3,4].map(r =>
            [0,1,2,3,4].map(c => {
              const ox = c * 9 - 18;
              const oy = r * 9 - 18;
              if (Math.sqrt(ox * ox + oy * oy) > 22) return null;
              return <circle key={r + "-" + c} cx={340 + ox} cy={270 + oy} r="2.5" fill="#444" opacity="0.8" />;
            })
          )}
          <circle cx="340" cy="270" r="26" fill="none" stroke="#666" strokeWidth="1.5" />

          {/* Vent slots */}
          {[0,1,2].map(i => (
            <rect key={i} x={120 + i * 50} y="310" width="35" height="3" rx="1.5" fill="#3D3D3D" opacity="0.3" />
          ))}

          {/* Sticker zone */}
          <rect x="100" y="175" width="200" height="80" rx="8"
            fill="rgba(168,130,255,0.06)" stroke="rgba(168,130,255,0.2)" strokeWidth="1" strokeDasharray="4 3" />
          <text x="200" y="220" textAnchor="middle" fill="rgba(168,130,255,0.35)" fontSize="9" fontFamily="system-ui">
            sticker / vinyl zone
          </text>
          <text x="200" y="340" fill="#3D3D3D" fontSize="11" fontFamily="monospace" letterSpacing="5" opacity="0.1">JARVIS</text>
          <text x="240" y="385" textAnchor="middle" fill="#999" fontSize="7" fontFamily="system-ui" fontStyle="italic">
            snap-off front panel - swap to screen later
          </text>
        </g>
      )}

      {/* Top plate */}
      <path d="M85,155 L125,120 L435,120 L395,155Z" fill="url(#topG)" stroke="#D9D0C4" strokeWidth="0.8" />

      {/* LED strip */}
      <path d="M85,155 L125,120 L435,120 L395,155Z" fill="none" stroke={led} strokeWidth="3" opacity="0.6" filter="url(#glow)" />
      {Array.from({ length: 14 }).map((_, i) => {
        const t = i / 13;
        const px = 90 + t * 340;
        const py = 154 - (t < 0.45 ? t * 75 : t > 0.55 ? (1 - t) * 75 : 34);
        return <circle key={i} cx={px} cy={py} r="2" fill={led} opacity="0.9" />;
      })}

      {/* Status OLED on top */}
      <rect x="160" y="128" width="55" height="20" rx="3" fill="#111" stroke="#333" strokeWidth="0.7" />
      <rect x="163" y="131" width="49" height="14" rx="2" fill="#0a0a14" />
      <text x="187" y="140" textAnchor="middle" fill={led} fontSize="6" fontFamily="monospace">10:42 PM</text>
      <text x="187" y="147" textAnchor="middle" fill="#555" fontSize="4" fontFamily="monospace">Listening...</text>

      {/* Mic holes */}
      {[{x:220,y:132},{x:280,y:132},{x:250,y:124},{x:250,y:142}].map((p, i) => (
        <circle key={i} cx={p.x} cy={p.y} r="1.8" fill="#777" opacity="0.4" />
      ))}

      {/* Dimensions */}
      <g opacity="0.4" fontSize="9" fontFamily="monospace" fill="#888">
        <line x1="85" y1="395" x2="395" y2="395" stroke="#888" strokeWidth="0.8" />
        <text x="240" y="408" textAnchor="middle">162 mm</text>
        <line x1="65" y1="155" x2="65" y2="370" stroke="#888" strokeWidth="0.8" />
        <text x="50" y="268" textAnchor="middle" transform="rotate(-90,50,268)">82 mm</text>
      </g>
    </svg>
  );
}

// ----- Cross Section -----
function CrossSection({ phase }) {
  return (
    <svg viewBox="0 0 520 340" style={{ width: "100%", maxWidth: 520 }}>
      <rect x="60" y="30" width="400" height="240" rx="16" fill="none" stroke="#D9D0C4" strokeWidth="3" />
      <rect x="60" y="30" width="8" height="240" rx="2" fill="#EDE7DC" />
      <rect x="452" y="30" width="8" height="240" rx="2" fill="#EDE7DC" />
      <rect x="60" y="262" width="400" height="8" rx="2" fill="#EDE7DC" />
      <rect x="60" y="30" width="400" height="12" rx="4" fill="#F5F0E8" stroke="#D9D0C4" strokeWidth="0.8" />

      {/* LED */}
      <rect x="64" y="33" width="6" height="6" rx="2" fill="#4FC3F7" opacity="0.7" />
      <rect x="450" y="33" width="6" height="6" rx="2" fill="#4FC3F7" opacity="0.7" />

      {/* Status OLED */}
      <rect x="200" y="32" width="40" height="8" rx="2" fill="#111" stroke="#333" strokeWidth="0.5" />
      <text x="220" y="39" textAnchor="middle" fill="#4FC3F7" fontSize="5" fontFamily="monospace">OLED</text>

      {/* Mic */}
      <rect x="160" y="46" width="80" height="10" rx="3" fill="#9C27B0" opacity="0.2" stroke="#9C27B0" strokeWidth="0.6" />
      <text x="200" y="54" textAnchor="middle" fill="#9C27B0" fontSize="6" fontFamily="monospace">ReSpeaker 4-Mic</text>
      <text x="470" y="54" fill="#999" fontSize="6" fontFamily="monospace">I2C</text>

      {/* Expansion */}
      <rect x="80" y="62" width="360" height="16" rx="3" fill="#87CEEB" opacity="0.1" stroke="#87CEEB" strokeWidth="0.6" strokeDasharray="3 2" />
      <text x="260" y="73" textAnchor="middle" fill="#87CEEB" fontSize="6" fontFamily="monospace">expansion tray</text>

      {/* Jetson */}
      <rect x="100" y="85" width="200" height="40" rx="4" fill="#76B900" opacity="0.15" stroke="#76B900" strokeWidth="1" />
      <text x="200" y="107" textAnchor="middle" fill="#76B900" fontSize="9" fontFamily="monospace" fontWeight="bold">Jetson Orin Nano</text>
      <text x="200" y="118" textAnchor="middle" fill="#76B900" fontSize="6" fontFamily="monospace">100 x 79 x 21 mm</text>

      {/* Standoffs */}
      {[110, 290].map((x, i) => <rect key={i} x={x} y="125" width="4" height="25" fill="#888" opacity="0.4" />)}
      <text x="200" y="145" textAnchor="middle" fill="#888" fontSize="5" fontFamily="monospace">M2.5 nylon standoffs</text>

      {/* USB Audio */}
      <rect x="110" y="155" width="60" height="15" rx="3" fill="#2196F3" opacity="0.2" stroke="#2196F3" strokeWidth="0.6" />
      <text x="140" y="166" textAnchor="middle" fill="#2196F3" fontSize="6" fontFamily="monospace">USB Audio</text>
      <text x="470" y="166" fill="#999" fontSize="6" fontFamily="monospace">USB</text>

      {/* Speaker */}
      <rect x="340" y="100" width="80" height="80" rx="4" fill="#FF6B6B" opacity="0.1" stroke="#FF6B6B" strokeWidth="0.6" />
      <circle cx="380" cy="140" r="24" fill="none" stroke="#333" strokeWidth="1.2" />
      <circle cx="380" cy="140" r="10" fill="#333" opacity="0.2" />
      <text x="380" y="175" textAnchor="middle" fill="#FF6B6B" fontSize="6" fontFamily="monospace">50mm 10W</text>

      {/* Grille */}
      {[125, 135, 145, 155].map((y, i) => (
        <rect key={i} x="454" y={y} width="5" height="3" rx="1" fill="#444" opacity="0.4" />
      ))}

      {/* Front panel */}
      {phase === 2 ? (
        <g>
          <rect x="62" y="50" width="3" height="200" fill="#111" />
          <text x="57" y="150" fill="#4FC3F7" fontSize="6" fontFamily="monospace" textAnchor="end" transform="rotate(-90,57,150)">HDMI Screen</text>
        </g>
      ) : (
        <g>
          <rect x="62" y="50" width="3" height="200" fill="#EDE7DC" />
          <text x="57" y="150" fill="#999" fontSize="6" fontFamily="monospace" textAnchor="end" transform="rotate(-90,57,150)">Blank Panel</text>
        </g>
      )}

      {/* Ventilation */}
      {[100, 150, 200].map((x, i) => (
        <rect key={i} x={x} y="264" width="30" height="3" rx="1.5" fill="#3D3D3D" opacity="0.3" />
      ))}
      <text x="175" y="285" textAnchor="middle" fill="#999" fontSize="6" fontFamily="monospace">ventilation slots</text>

      {/* Port bay on back wall */}
      <rect x="435" y="80" width="18" height="180" rx="4" fill="#3D3D3D" opacity="0.12" />
      <rect x="438" y="88" width="12" height="10" rx="2" fill="#333" opacity="0.4" />
      <text x="470" y="96" fill="#999" fontSize="5" fontFamily="monospace">HDMI</text>
      <rect x="438" y="105" width="12" height="8" rx="2" fill="#333" opacity="0.4" />
      <text x="470" y="112" fill="#999" fontSize="5" fontFamily="monospace">USB 3.0</text>
      <rect x="438" y="120" width="12" height="8" rx="2" fill="#333" opacity="0.4" />
      <text x="470" y="127" fill="#999" fontSize="5" fontFamily="monospace">USB 2.0</text>
      <circle cx="444" cy="140" r="4" fill="#333" opacity="0.4" />
      <text x="470" y="143" fill="#999" fontSize="5" fontFamily="monospace">3.5mm</text>
      <rect x="439" y="152" width="10" height="7" rx="2" fill="#333" opacity="0.4" />
      <text x="470" y="159" fill="#999" fontSize="5" fontFamily="monospace">USB-C</text>
      <rect x="438" y="170" width="12" height="10" rx="2" fill="#333" opacity="0.3" strokeDasharray="2 1" stroke="#666" strokeWidth="0.5" />
      <text x="470" y="178" fill="#777" fontSize="5" fontFamily="monospace">future</text>
      <text x="444" y="245" textAnchor="middle" fill="#888" fontSize="5" fontFamily="monospace" transform="rotate(-90,444,235)">port bay (pass-through)</text>

      <text x="260" y="310" textAnchor="middle" fill="#666" fontSize="8" fontFamily="monospace">
        All Jetson ports exposed via back panel cutouts - zero soldering
      </text>
    </svg>
  );
}

// ----- Connection Diagram -----
function ConnectionDiagram() {
  const nodes = [
    { x: 80,  y: 30,  w: 120, h: 45, label: "USB Audio Card", sub: "Waveshare", color: "#2196F3", conn: "USB" },
    { x: 80,  y: 95,  w: 120, h: 35, label: "50mm Speaker", sub: "screw terminal", color: "#FF6B6B", conn: "" },
    { x: 380, y: 30,  w: 120, h: 45, label: "ReSpeaker 4-Mic", sub: "GPIO header", color: "#9C27B0", conn: "GPIO" },
    { x: 380, y: 95,  w: 120, h: 45, label: "HDMI Screen", sub: "5 or 7 inch touch", color: "#4FC3F7", conn: "HDMI" },
    { x: 180, y: 205, w: 160, h: 35, label: "1.3 inch Status OLED", sub: "4 Dupont wires", color: "#FF9800", conn: "I2C" },
    { x: 20,  y: 205, w: 120, h: 35, label: "WS2812B LED Ring", sub: "3 Dupont wires", color: "#DAA520", conn: "GPIO" },
    { x: 380, y: 205, w: 120, h: 35, label: "USB-C Power", sub: "magnetic cable", color: "#F44336", conn: "USB-C" },
  ];

  return (
    <svg viewBox="0 0 520 300" style={{ width: "100%", maxWidth: 520 }}>
      {/* Jetson center */}
      <rect x="180" y="110" width="160" height="60" rx="8" fill="#76B900" opacity="0.2" stroke="#76B900" strokeWidth="1.5" />
      <text x="260" y="140" textAnchor="middle" fill="#76B900" fontSize="11" fontFamily="monospace" fontWeight="bold">Jetson Orin Nano</text>
      <text x="260" y="158" textAnchor="middle" fill="#76B900" fontSize="7" fontFamily="monospace">40-pin GPIO + USB + HDMI</text>

      {nodes.map((n, i) => (
        <g key={i}>
          <rect x={n.x} y={n.y} width={n.w} height={n.h} rx="6" fill={n.color} opacity="0.15" stroke={n.color} strokeWidth="1" />
          <text x={n.x + n.w / 2} y={n.y + 18} textAnchor="middle" fill={n.color} fontSize="8" fontFamily="monospace" fontWeight="bold">{n.label}</text>
          <text x={n.x + n.w / 2} y={n.y + 30} textAnchor="middle" fill={n.color} fontSize="6" fontFamily="monospace">{n.sub}</text>
          {n.conn && (
            <line
              x1={n.x + n.w / 2} y1={n.y + n.h}
              x2="260" y2={n.y < 150 ? 110 : 170}
              stroke={n.color} strokeWidth="1.5" strokeDasharray="4 2"
            />
          )}
        </g>
      ))}

      {/* Speaker to audio card */}
      <line x1="140" y1="95" x2="140" y2="68" stroke="#FF6B6B" strokeWidth="1" strokeDasharray="3 2" />

      {/* GPIO breakout */}
      <rect x="155" y="260" width="210" height="25" rx="6" fill="#607D8B" opacity="0.15" stroke="#607D8B" strokeWidth="1" />
      <text x="260" y="276" textAnchor="middle" fill="#607D8B" fontSize="7" fontFamily="monospace">
        GPIO Screw Terminal Breakout - no crimping, just screw in wires
      </text>

      <text x="260" y="298" textAnchor="middle" fill="#aaa" fontSize="7" fontFamily="system-ui">
        Every connection is plug-in or screw-terminal. Zero soldering.
      </text>
    </svg>
  );
}

// ----- STL File Card -----
function STLCard({ stl, label, desc, phaseTag }) {
  return (
    <div className="p-4 rounded-xl border border-gray-200 bg-white">
      <div className="flex items-start justify-between mb-2">
        <code className="text-sm font-bold text-gray-900">{stl.file}</code>
        <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">{stl.kb} KB</span>
      </div>
      <p className="text-sm text-gray-600 mb-2">{desc}</p>
      <div className="flex gap-4 text-xs text-gray-400 font-mono">
        <span>{stl.w} x {stl.d} x {stl.h} mm</span>
        <span>{stl.tri} triangles</span>
      </div>
      {phaseTag && (
        <span className={"inline-block mt-2 text-xs px-2 py-0.5 rounded-full " +
          (phaseTag === "Phase 1" ? "bg-green-100 text-green-700" : "bg-blue-100 text-blue-700")
        }>{phaseTag}</span>
      )}
    </div>
  );
}

// ----- Electronics BOM -----
function ElectronicsBOM() {
  const items = [
    { name: "Waveshare USB Audio Codec", price: "2,000-2,500", link: "amazon.in/dp/B08YXV48HL", plug: true, note: "USB plug-and-play, no I2S wiring needed" },
    { name: "50mm 10W Speaker (pre-wired)", price: "300-500", link: "amazon.in/dp/B0BN44QCFQ", plug: true, note: "Comes with wires, screw terminal to amp" },
    { name: "ReSpeaker 4-Mic Array", price: "1,500-2,500", link: "amazon.in/dp/B076SSR1W1", plug: true, note: "Plugs onto GPIO header directly" },
    { name: "WS2812B 24-LED Ring 72mm", price: "200-400", link: "amazon.in/dp/B0D5CQ4PHS", plug: false, note: "3 Dupont wires to GPIO, no solder" },
    { name: "1.3 inch I2C OLED (top status)", price: "400-800", link: "amazon.in/s?k=1.3+inch+OLED+I2C+display", plug: true, note: "4-pin I2C header, Dupont wires" },
    { name: "USB-C Hub (ports access)", price: "800-1,500", link: "amazon.in/s?k=usb+c+hub+hdmi+usb+3.5mm", plug: true, note: "Exposes HDMI, USB-A, 3.5mm, USB-C from back panel" },
    { name: "GPIO Screw Terminal Breakout", price: "400-700", link: "amazon.in/s?k=40+pin+GPIO+screw+terminal+breakout", plug: true, note: "Screw in wires to labeled GPIO pins" },
    { name: "Dupont Jumper Wires 120pcs", price: "150-250", link: "amazon.in/s?k=dupont+jumper+wire+120", plug: true, note: "For LED ring and OLED" },
    { name: "M2.5 Nylon Standoff Kit", price: "200-400", link: "amazon.in/s?k=M2.5+nylon+standoff+assortment", plug: true, note: "Hand-tighten, no tools" },
    { name: "Magnetic USB-C Cable", price: "400-800", link: "amazon.in/s?k=magnetic+usb+c+cable", plug: true, note: "Snap-on power, easy disconnect" },
    { name: "Short HDMI Cable 30cm", price: "200-400", link: "amazon.in/s?k=short+hdmi+cable+30cm", plug: true, note: "Internal routing to front screen" },
    { name: "Velcro Cable Ties 20pcs", price: "150-250", link: "amazon.in/s?k=velcro+cable+ties+reusable", plug: true, note: "Reusable, no adhesive" },
  ];

  return (
    <div>
      <div className="overflow-x-auto bg-white rounded-xl shadow-lg">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b-2 border-gray-300 bg-gray-50">
              <th className="text-left py-3 px-3 font-semibold text-gray-900">Component</th>
              <th className="text-left py-3 px-3 font-semibold text-gray-900">INR</th>
              <th className="text-center py-3 px-3 font-semibold text-gray-900">Plug and Play</th>
              <th className="text-left py-3 px-3 font-semibold text-gray-900">Link (copy to browser)</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item, i) => (
              <tr key={i} className={"border-b border-gray-100 " + (i % 2 === 0 ? "bg-white" : "bg-gray-50")}>
                <td className="py-3 px-3">
                  <div className="font-medium text-gray-900">{item.name}</div>
                  {item.note && <div className="text-xs text-gray-500 mt-0.5">{item.note}</div>}
                </td>
                <td className="py-3 px-3 font-mono text-gray-700 whitespace-nowrap">Rs {item.price}</td>
                <td className="py-3 px-3 text-center">
                  {item.plug ? (
                    <span className="inline-block bg-green-100 text-green-700 text-xs px-2 py-0.5 rounded-full">YES</span>
                  ) : (
                    <span className="inline-block bg-yellow-100 text-yellow-700 text-xs px-2 py-0.5 rounded-full">jumpers</span>
                  )}
                </td>
                <td className="py-3 px-3">
                  <div className="font-mono text-xs text-blue-700 select-all cursor-text break-all bg-blue-50 px-2 py-1 rounded">
                    {item.link}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-4 p-4 bg-gradient-to-r from-green-50 to-blue-50 rounded-xl">
        <div className="grid grid-cols-3 gap-4 text-center">
          <div>
            <div className="text-xs text-gray-500">Phase 1 (Voice Only)</div>
            <div className="text-xl font-bold text-green-700">Rs 5,000-7,500</div>
          </div>
          <div>
            <div className="text-xs text-gray-500">Phase 2 (+5 inch Screen)</div>
            <div className="text-xl font-bold text-blue-700">Rs 7,500-12,500</div>
          </div>
          <div>
            <div className="text-xs text-gray-500">Phase 2 (+7 inch Screen)</div>
            <div className="text-xl font-bold text-purple-700">Rs 9,000-14,500</div>
          </div>
        </div>
        <p className="text-xs text-gray-500 mt-3 text-center">
          Excludes Jetson Orin Nano. All items ship to India. Zero soldering required.
        </p>
      </div>
    </div>
  );
}

// ----- Screen Proposals (Phase 2) -----
function ScreenProposals() {
  const screens = [
    {
      name: "Waveshare 5.5 inch AMOLED",
      badge: "THINNEST BEZEL",
      badgeColor: "bg-purple-100 text-purple-700",
      res: "1080 x 1920",
      panel: "AMOLED",
      touch: "Capacitive 5-point",
      bezel: "2-3mm (near zero)",
      thickness: "4.8mm panel, 11mm with bracket",
      brightness: "High (AMOLED)",
      price: "Rs 10,000-10,500",
      link: "waveshare.com/5.5inch-hdmi-amoled.htm",
      indiaLink: "indiamart.com (search: waveshare 5.5 amoled hdmi)",
      driver: "Plug-and-play, driver-free on Linux",
      pros: ["Thinnest bezel available", "AMOLED = true blacks, incredible contrast", "USB-C for touch + power", "Portrait 1080x1920 great for assistant UI"],
      cons: ["Most expensive option", "Portrait orientation needs UI adaptation", "IndiaMART sourcing (not Amazon)"],
    },
    {
      name: "Waveshare 5DP-CAPLCD-H (Narrow Bezel)",
      badge: "BEST VALUE",
      badgeColor: "bg-green-100 text-green-700",
      res: "1024 x 600",
      panel: "IPS",
      touch: "Capacitive 5-point, air-bonded",
      bezel: "3-4mm (narrow)",
      thickness: "~10mm",
      brightness: "800 cd/m2 (very bright)",
      price: "Rs 4,500-5,500",
      link: "waveshare.com/5dp-caplcd.htm",
      indiaLink: "hubtronics.in/5dp-caplcd-h",
      driver: "Plug-and-play, driver-free on Linux",
      pros: ["Narrow bezel design", "800 nits - readable in any light", "Air-bonded glass (premium feel)", "Half the price of AMOLED"],
      cons: ["Lower resolution than AMOLED", "Slightly thicker bezel than AMOLED"],
    },
    {
      name: "Waveshare 5 inch LCD (H) V4",
      badge: "BUDGET",
      badgeColor: "bg-amber-100 text-amber-700",
      res: "800 x 480",
      panel: "IPS",
      touch: "Capacitive 5-point",
      bezel: "4-5mm (standard)",
      thickness: "~12mm",
      brightness: "Standard",
      price: "Rs 4,000-4,500",
      link: "amazon.in/dp/B0BR8HRGSZ",
      indiaLink: "robu.in (search: waveshare 5 inch hdmi lcd h v4)",
      driver: "Plug-and-play, driver-free on Linux",
      pros: ["Cheapest option", "Widely available in India", "Well-documented for Pi/Jetson"],
      cons: ["Widest bezel of the three", "Lower resolution 800x480", "Standard brightness"],
    },
    {
      name: "Waveshare 7 inch HDMI LCD (H)",
      badge: "BIGGEST",
      badgeColor: "bg-blue-100 text-blue-700",
      res: "1024 x 600",
      panel: "IPS",
      touch: "Capacitive 5-point",
      bezel: "5-6mm",
      thickness: "~14mm",
      brightness: "Standard",
      price: "Rs 5,000-6,500",
      link: "amazon.in/dp/B077PLVZCX",
      indiaLink: "robu.in (search: waveshare 7 inch hdmi capacitive)",
      driver: "Plug-and-play, driver-free on Linux",
      pros: ["Biggest screen for games/gallery", "Good for touch UI controls", "IPS 178 degree viewing angle"],
      cons: ["Widest bezel", "Needs the 7 inch front panel STL", "Enclosure front is almost all screen"],
    },
  ];

  return (
    <div>
      <h3 className="font-bold text-gray-900 mb-2">Front Screen Options (Phase 2)</h3>
      <p className="text-sm text-gray-500 mb-4">All are HDMI + USB touch, plug-and-play on Jetson. No drivers. Pick based on bezel preference and budget.</p>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {screens.map((s, i) => (
          <div key={i} className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
            <div className="flex items-start justify-between mb-3">
              <h4 className="font-bold text-gray-900 text-sm">{s.name}</h4>
              <span className={"text-xs px-2 py-0.5 rounded-full font-medium " + s.badgeColor}>{s.badge}</span>
            </div>
            <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs mb-3">
              <div><span className="text-gray-400">Resolution:</span> <span className="text-gray-700 font-mono">{s.res}</span></div>
              <div><span className="text-gray-400">Panel:</span> <span className="text-gray-700">{s.panel}</span></div>
              <div><span className="text-gray-400">Touch:</span> <span className="text-gray-700">{s.touch}</span></div>
              <div><span className="text-gray-400">Bezel:</span> <span className="text-gray-900 font-bold">{s.bezel}</span></div>
              <div><span className="text-gray-400">Thickness:</span> <span className="text-gray-700">{s.thickness}</span></div>
              <div><span className="text-gray-400">Brightness:</span> <span className="text-gray-700">{s.brightness}</span></div>
            </div>
            <div className="flex items-baseline gap-2 mb-3">
              <span className="text-lg font-bold text-gray-900">{s.price}</span>
              <span className="text-xs text-green-600">plug-and-play</span>
            </div>
            <div className="mb-3">
              <div className="text-xs text-gray-500 mb-1">Pros:</div>
              <div className="flex flex-wrap gap-1">
                {s.pros.map((p, j) => (
                  <span key={j} className="text-xs bg-green-50 text-green-700 px-2 py-0.5 rounded-full">{p}</span>
                ))}
              </div>
            </div>
            <div className="mb-3">
              <div className="text-xs text-gray-500 mb-1">Cons:</div>
              <div className="flex flex-wrap gap-1">
                {s.cons.map((c, j) => (
                  <span key={j} className="text-xs bg-red-50 text-red-600 px-2 py-0.5 rounded-full">{c}</span>
                ))}
              </div>
            </div>
            <div className="space-y-1">
              <div className="font-mono text-xs text-blue-700 select-all cursor-text break-all bg-blue-50 px-2 py-1 rounded">{s.link}</div>
              <div className="font-mono text-xs text-purple-600 select-all cursor-text break-all bg-purple-50 px-2 py-1 rounded">{s.indiaLink}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ----- Assembly Steps -----
function AssemblySteps() {
  const steps = [
    { n: 1, title: "Mount Jetson on nylon standoffs", desc: "4x M2.5 nylon standoffs into base, hand-tighten Jetson onto them" },
    { n: 2, title: "Plug USB Audio Card into Jetson", desc: "Single USB cable. Speaker wires screw into audio card terminal" },
    { n: 3, title: "Connect speaker to USB Audio Card", desc: "Speaker has pre-soldered wires, screw into terminal block" },
    { n: 4, title: "Mount speaker in base", desc: "Press-fit into side wall, secure with printed grille from outside" },
    { n: 5, title: "Attach GPIO Screw Terminal Breakout", desc: "Plugs onto Jetson 40-pin header. All GPIO pins become screw terminals" },
    { n: 6, title: "Wire LED ring via Dupont jumpers", desc: "3 wires: 5V, GND, Data into GPIO breakout screw terminals" },
    { n: 7, title: "Connect 1.3 inch OLED status screen", desc: "4 Dupont wires: VCC, GND, SDA, SCL into I2C pins on breakout" },
    { n: 8, title: "Route cables with velcro ties", desc: "Wrap bundles, tuck into cable channel. Reusable, no adhesive" },
    { n: 9, title: "Snap on top plate and front panel", desc: "Push-fit into rails. LED ring sits in the top plate channel" },
    { n: 10, title: "(Phase 2) Swap front panel, plug HDMI screen", desc: "Snap off blank panel, snap on screen panel, HDMI + USB to Jetson" },
  ];

  return (
    <div className="space-y-4">
      {steps.map(s => (
        <div key={s.n} className="flex gap-4">
          <div className="flex-shrink-0 w-8 h-8 bg-gray-900 text-white rounded-full flex items-center justify-center text-sm font-bold">{s.n}</div>
          <div>
            <p className="font-semibold text-gray-900">{s.title}</p>
            <p className="text-sm text-gray-500">{s.desc}</p>
          </div>
        </div>
      ))}
    </div>
  );
}

// ============================================================
// MAIN COMPONENT
// ============================================================
export default function JARVISEnclosure() {
  const [phase, setPhase] = useState(1);
  const [personality, setPersonality] = useState("jarvis");
  const [screenSize, setScreenSize] = useState(5);
  const [tab, setTab] = useState("3d");

  const tabs = [
    { id: "3d", label: "3D View" },
    { id: "diagrams", label: "2D Diagrams" },
    { id: "stl", label: "STL Files" },
    { id: "bom", label: "Electronics (India)" },
    { id: "wiring", label: "Connections" },
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-stone-50 via-white to-amber-50 p-6">
      <div className="max-w-5xl mx-auto">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-3xl font-bold text-gray-900">JARVIS Enclosure</h1>
          <p className="text-gray-500 mt-1">3D printed, modular, swappable front panels, zero soldering</p>
        </div>

        {/* Phase selector */}
        <div className="flex gap-3 mb-6">
          <button onClick={() => setPhase(1)}
            className={"flex-1 p-4 rounded-xl border-2 text-left transition-all " +
              (phase === 1 ? "border-green-500 bg-green-50 shadow-md" : "border-gray-200 bg-white")}>
            <div className="font-bold text-gray-900">Phase 1: Voice Only</div>
            <div className="text-sm text-gray-500 mt-1">Blank front, top status OLED</div>
          </button>
          <button onClick={() => setPhase(2)}
            className={"flex-1 p-4 rounded-xl border-2 text-left transition-all " +
              (phase === 2 ? "border-blue-500 bg-blue-50 shadow-md" : "border-gray-200 bg-white")}>
            <div className="font-bold text-gray-900">Phase 2: Smart Display</div>
            <div className="text-sm text-gray-500 mt-1">5 or 7 inch front screen</div>
          </button>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 mb-6 border-b border-gray-200">
          {tabs.map(t => (
            <button key={t.id} onClick={() => setTab(t.id)}
              className={"px-4 py-2 text-sm font-medium border-b-2 transition-colors " +
                (tab === t.id
                  ? "border-gray-900 text-gray-900"
                  : "border-transparent text-gray-400 hover:text-gray-600")}>
              {t.label}
            </button>
          ))}
        </div>

        {/* === 3D VIEW TAB === */}
        {tab === "3d" && (
          <div>
            {/* Controls */}
            <div className="bg-white rounded-xl shadow-sm p-4 mb-6 flex flex-wrap gap-4 items-center">
              <div className="flex gap-2">
                <span className="text-sm text-gray-500 self-center">LED:</span>
                {Object.entries(LED_COLORS).map(([id, c]) => (
                  <button key={id} onClick={() => setPersonality(id)}
                    className={"w-7 h-7 rounded-full border-2 " + (personality === id ? "border-gray-900 scale-110" : "border-gray-300")}
                    style={{ backgroundColor: c }} title={id} />
                ))}
              </div>
              {phase === 2 && (
                <div className="flex gap-2 ml-4">
                  <span className="text-sm text-gray-500 self-center">Screen:</span>
                  {[5, 7].map(s => (
                    <button key={s} onClick={() => setScreenSize(s)}
                      className={"px-3 py-1 rounded-lg text-sm font-medium " +
                        (screenSize === s ? "bg-gray-900 text-white" : "bg-gray-100 text-gray-600")}>
                      {s} inch
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Three.js 3D Viewer */}
            <div className="bg-white rounded-2xl shadow-lg p-6 mb-6" style={{ background: "linear-gradient(180deg, #faf9f7, #f0ede8)" }}>
              <ThreeViewer phase={phase} personality={personality} screenSize={screenSize} />
            </div>

            {/* Feature cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="bg-white rounded-xl shadow-sm p-5 border-l-4 border-green-500">
                <h3 className="font-bold text-gray-900 mb-1">Snap-Fit Front Panel</h3>
                <p className="text-sm text-gray-600">Start with blank front. Later, snap off and swap to 5 or 7 inch screen panel. No tools, no reprinting.</p>
              </div>
              <div className="bg-white rounded-xl shadow-sm p-5 border-l-4 border-blue-500">
                <h3 className="font-bold text-gray-900 mb-1">Dual Screen Support</h3>
                <p className="text-sm text-gray-600">Small 1.3 inch OLED on top for status. Large HDMI touch on front for UI, games, gallery.</p>
              </div>
              <div className="bg-white rounded-xl shadow-sm p-5 border-l-4 border-purple-500">
                <h3 className="font-bold text-gray-900 mb-1">Zero Soldering</h3>
                <p className="text-sm text-gray-600">USB audio, GPIO screw terminals, Dupont jumpers, HDMI for screen. All plug-and-play.</p>
              </div>
              <div className="bg-white rounded-xl shadow-sm p-5 border-l-4 border-amber-500">
                <h3 className="font-bold text-gray-900 mb-1">Full Port Bay (Back Panel)</h3>
                <p className="text-sm text-gray-600">HDMI, 2x USB, 3.5mm audio, USB-C all accessible from back. Connect external displays, keyboards, mice, USB-C earphones, battery packs -- without opening the enclosure.</p>
              </div>
            </div>
          </div>
        )}

        {/* === 2D DIAGRAMS TAB === */}
        {tab === "diagrams" && (
          <div>
            {/* Controls */}
            <div className="bg-white rounded-xl shadow-sm p-4 mb-6 flex flex-wrap gap-4 items-center">
              <div className="flex gap-2">
                <span className="text-sm text-gray-500 self-center">LED:</span>
                {Object.entries(LED_COLORS).map(([id, c]) => (
                  <button key={id} onClick={() => setPersonality(id)}
                    className={"w-7 h-7 rounded-full border-2 " + (personality === id ? "border-gray-900 scale-110" : "border-gray-300")}
                    style={{ backgroundColor: c }} title={id} />
                ))}
              </div>
              {phase === 2 && (
                <div className="flex gap-2 ml-4">
                  <span className="text-sm text-gray-500 self-center">Screen:</span>
                  {[5, 7].map(s => (
                    <button key={s} onClick={() => setScreenSize(s)}
                      className={"px-3 py-1 rounded-lg text-sm font-medium " +
                        (screenSize === s ? "bg-gray-900 text-white" : "bg-gray-100 text-gray-600")}>
                      {s} inch
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* SVG Visualizations */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
              <div className="bg-white rounded-2xl shadow-lg p-6" style={{ background: "linear-gradient(180deg, #faf9f7, #f0ede8)" }}>
                <h3 className="text-sm font-semibold text-gray-400 mb-3 uppercase tracking-wide">3/4 View</h3>
                <HeroView phase={phase} personality={personality} screenSize={screenSize} />
              </div>
              <div className="bg-white rounded-2xl shadow-lg p-6" style={{ background: "linear-gradient(180deg, #faf9f7, #f0ede8)" }}>
                <h3 className="text-sm font-semibold text-gray-400 mb-3 uppercase tracking-wide">Cross Section</h3>
                <CrossSection phase={phase} />
              </div>
            </div>

          </div>
        )}

        {/* === STL FILES TAB === */}
        {tab === "stl" && (
          <div>
            <p className="text-gray-600 mb-4">Six modular STL files. Print what you need, add screen panels later.</p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
              <STLCard stl={STL.base} label="Base Shell"
                desc="Main body with Jetson mounts, cable channel, snap-fit front rails, ventilation" />
              <STLCard stl={STL.top} label="Top Plate"
                desc="Mic holes, LED channel, 1.3 inch OLED cutout, snap-fit tabs" />
              <STLCard stl={STL.frontBlank} label="Blank Front"
                desc="Speaker grille area, vent slots, sticker zone" phaseTag="Phase 1" />
              <STLCard stl={STL.front5} label="5 inch Screen Front"
                desc="121x76mm screen cutout, M3 mounting tabs" phaseTag="Phase 2" />
              <STLCard stl={STL.front7} label="7 inch Screen Front"
                desc="170x105mm screen cutout, M3 mounting tabs" phaseTag="Phase 2" />
              <STLCard stl={STL.grille} label="Speaker Grille"
                desc="Press-fit insert for blank front panel" phaseTag="Phase 1" />
            </div>

            <div className="bg-amber-50 rounded-xl p-5 border border-amber-200 mb-4">
              <h3 className="font-bold text-gray-900 mb-2">Print Settings (for 3Ding or any FDM service)</h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                <div><span className="text-gray-500">Technology:</span> <strong>FDM/FFF</strong></div>
                <div><span className="text-gray-500">Material:</span> <strong>PLA</strong> (PETG for base)</div>
                <div><span className="text-gray-500">Quality:</span> <strong>Standard</strong></div>
                <div><span className="text-gray-500">Infill:</span> <strong>20%</strong></div>
                <div><span className="text-gray-500">Color:</span> <strong>White</strong></div>
                <div><span className="text-gray-500">Layer:</span> <strong>0.2mm</strong></div>
                <div><span className="text-gray-500">Walls:</span> <strong>2.5mm (3 perimeters)</strong></div>
                <div><span className="text-gray-500">Supports:</span> <strong>Yes (base only)</strong></div>
              </div>
            </div>

            <div className="bg-gray-50 rounded-xl p-4 border border-gray-200">
              <p className="text-sm text-gray-600">
                <strong>Files:</strong>{" "}
                <code className="bg-gray-100 px-2 py-0.5 rounded text-xs">jarvis/05-the-body/designs/stl/</code>
              </p>
              <p className="text-sm text-gray-600 mt-1">
                <strong>Regenerate:</strong>{" "}
                <code className="bg-gray-100 px-2 py-0.5 rounded text-xs">python generate_enclosure_v2.py</code>
              </p>
            </div>
          </div>
        )}

        {/* === BOM TAB === */}
        {tab === "bom" && (
          <div>
            <div className="bg-green-50 rounded-xl p-4 border border-green-200 mb-6">
              <p className="text-green-800 font-medium">All items ship to India (Amazon.in / Robocraze). Every component is plug-and-play. No soldering iron needed.</p>
            </div>
            <ElectronicsBOM />
            <div className="mt-8">
              <ScreenProposals />
            </div>
          </div>
        )}

        {/* === WIRING TAB === */}
        {tab === "wiring" && (
          <div>
            <div className="bg-white rounded-2xl shadow-lg p-6 mb-6">
              <h3 className="font-bold text-gray-900 mb-4">Connection Diagram</h3>
              <ConnectionDiagram />
            </div>
            <div className="bg-white rounded-xl shadow-lg p-6">
              <h3 className="font-bold text-gray-900 mb-4">Assembly (30 min, screwdriver only)</h3>
              <AssemblySteps />
            </div>
          </div>
        )}

        <div className="mt-8 pt-6 border-t border-gray-200 text-center text-sm text-gray-400">
          JARVIS Enclosure - Birthday Deadline: May 14, 2026
        </div>
      </div>
    </div>
  );
}
