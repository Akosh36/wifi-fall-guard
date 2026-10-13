// Live 3D room view for WiFi Fall Guard.
// Runs in the Android app (WebView, native bridge `window.WFG`) and in a browser at /app/.
// Data comes from the server WebSocket /ws (same JSON as /api/status); demo mode generates it locally.

import * as THREE from "three";
import { OrbitControls } from "three/addons/OrbitControls.js";

const RED_STATES = new Set(["fall_suspected", "alert"]);
const OFF_STATES = new Set(["starting", "waiting_for_nodes", "offline"]);
const ACTIVITY_UZ = { empty: "Xona bo'sh", still: "Qimirlamayapti", walk: "Yuryapti", sit: "O'tiribdi",
                      lie: "Yotibdi", fall: "Yiqildi", unknown: "Noma'lum" };
const DEFAULT_ROOM = {
  name: "Xona", size: [4.0, 3.5, 2.7], tx: [0.3, 0.3, 1.2],
  rx: { 0: [3.7, 0.4, 1.0], 1: [3.7, 3.1, 1.0], 2: [0.3, 3.1, 1.0] },
  furniture: [
    { kind: "bed", pos: [3.0, 2.4], size: [1.0, 2.0], rot: 0 },
    { kind: "chair", pos: [0.9, 1.0], size: [0.5, 0.5], rot: 45 },
    { kind: "table", pos: [0.9, 1.7], size: [0.9, 0.6], rot: 0 },
  ],
};
const COLORS = { ok: 0x1fbf6a, bad: 0xe5322d, off: 0x8a94a0 };

// ---------------------------------------------------------------- settings / bridge
const bridge = window.WFG || null;
const store = {
  get(k, d) { try { return localStorage.getItem(k) ?? d; } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch { /* private mode */ } },
};
function defaultServer() {
  const servedByServer = location.protocol.startsWith("http") && location.pathname.startsWith("/app")
    && location.hostname !== "appassets.androidplatform.net";
  return servedByServer ? location.origin : "";
}
const cfg = {
  server: (bridge && bridge.getServer()) || store.get("wfg.server", "") || defaultServer(),
  demo: bridge ? bridge.getDemo() : store.get("wfg.demo", "0") === "1",
};
function saveCfg() {
  if (bridge) bridge.setConfig(cfg.server, cfg.demo);
  store.set("wfg.server", cfg.server);
  store.set("wfg.demo", cfg.demo ? "1" : "0");
}

// ---------------------------------------------------------------- scene
const host = document.getElementById("scene");
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
host.appendChild(renderer.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0d1a14);
const camera = new THREE.PerspectiveCamera(50, 1, 0.05, 100);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.maxPolarAngle = Math.PI * 0.47;
controls.minDistance = 2;
controls.maxDistance = 14;

scene.add(new THREE.HemisphereLight(0xdfe9ff, 0x2a2f2a, 1.1));
const sun = new THREE.DirectionalLight(0xffffff, 1.6);
sun.position.set(3, 6, 4);
sun.castShadow = true;
sun.shadow.mapSize.set(1024, 1024);
scene.add(sun);
const moodLight = new THREE.PointLight(COLORS.ok, 2.5, 8, 1.5);
scene.add(moodLight);

let room = null;           // world-space helpers built from the room config
const roomGroup = new THREE.Group();
scene.add(roomGroup);

// Place the camera so the whole room fits on screen, also in portrait.
function fitCamera() {
  if (!room) return;
  const radius = Math.hypot(room.W, room.D, room.H) / 2;
  const vfov = THREE.MathUtils.degToRad(camera.fov);
  const hfov = 2 * Math.atan(Math.tan(vfov / 2) * camera.aspect);
  const dist = radius / Math.sin(Math.min(vfov, hfov) / 2) * 0.92;
  const dir = new THREE.Vector3(0.55, 0.75, 0.95).normalize();
  controls.target.set(0, 0.5, 0);
  camera.position.copy(dir.multiplyScalar(dist)).add(controls.target);
  controls.maxDistance = dist * 1.8;
}

// config coordinates (x = width, y = depth, z = height) -> three.js (x, y = up, z)
function toWorld(p, size) { return new THREE.Vector3(p[0] - size[0] / 2, p[2] ?? 0, p[1] - size[1] / 2); }

function mat(color, extra = {}) { return new THREE.MeshStandardMaterial({ color, roughness: 0.8, metalness: 0.05, ...extra }); }
function box(w, h, d, material, x = 0, y = 0, z = 0) {
  const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), material);
  m.position.set(x, y, z);
  m.castShadow = m.receiveShadow = true;
  return m;
}
function textSprite(text, color = "#ffffff", bg = "rgba(0,0,0,.65)") {
  const c = document.createElement("canvas");
  c.width = 256; c.height = 96;
  const g = c.getContext("2d");
  g.fillStyle = bg;
  g.beginPath(); g.roundRect(8, 16, 240, 64, 32); g.fill();
  g.fillStyle = color; g.font = "bold 40px system-ui, sans-serif";
  g.textAlign = "center"; g.textBaseline = "middle"; g.fillText(text, 128, 50);
  const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(c), depthTest: false }));
  s.scale.set(0.75, 0.28, 1);
  s.renderOrder = 5;
  return s;
}

function furniture(f) {
  const g = new THREE.Group();
  const [w, d] = f.size || [1, 1];
  const wood = mat(0x8a6a4a), fabric = mat(0x5d7a9a), white = mat(0xe8e8e0);
  if (f.kind === "bed") {
    g.add(box(w, 0.3, d, wood, 0, 0.15, 0));
    g.add(box(w * 0.96, 0.18, d * 0.96, white, 0, 0.39, 0));
    g.add(box(w * 0.6, 0.1, 0.3, white, 0, 0.53, -d / 2 + 0.25));
    g.add(box(w, 0.7, 0.06, wood, 0, 0.35, -d / 2));
    g.userData.surface = 0.48;
  } else if (f.kind === "chair") {
    g.add(box(w, 0.06, d, wood, 0, 0.45, 0));
    g.add(box(w, 0.5, 0.05, wood, 0, 0.73, -d / 2 + 0.025));
    for (const [sx, sz] of [[1, 1], [1, -1], [-1, 1], [-1, -1]]) g.add(box(0.04, 0.45, 0.04, wood, sx * (w / 2 - 0.03), 0.225, sz * (d / 2 - 0.03)));
    g.userData.surface = 0.48;
  } else if (f.kind === "table") {
    g.add(box(w, 0.05, d, wood, 0, 0.74, 0));
    for (const [sx, sz] of [[1, 1], [1, -1], [-1, 1], [-1, -1]]) g.add(box(0.05, 0.72, 0.05, wood, sx * (w / 2 - 0.05), 0.36, sz * (d / 2 - 0.05)));
  } else if (f.kind === "sofa") {
    g.add(box(w, 0.42, d, fabric, 0, 0.21, 0));
    g.add(box(w, 0.45, 0.2, fabric, 0, 0.62, -d / 2 + 0.1));
    g.userData.surface = 0.44;
  } else {
    g.add(box(w, 0.5, d, wood, 0, 0.25, 0));
  }
  return g;
}

function node(label, color) {
  const g = new THREE.Group();
  const body = box(0.12, 0.05, 0.08, mat(0x20252a), 0, 0, 0);
  const ant = new THREE.Mesh(new THREE.CylinderGeometry(0.008, 0.008, 0.16), mat(0x111111));
  ant.position.set(0.04, 0.1, 0);
  const led = new THREE.Mesh(new THREE.SphereGeometry(0.022, 12, 8), new THREE.MeshBasicMaterial({ color }));
  led.position.set(-0.03, 0.04, 0.03);
  const tag = textSprite(label);
  tag.position.set(0, 0.28, 0);
  g.add(body, ant, led, tag);
  g.userData.led = led;
  return g;
}

function buildRoom(conf) {
  roomGroup.clear();
  const [W, D, H] = conf.size;
  const floorMat = mat(0x2b3a33, { roughness: 0.95 });
  const floor = new THREE.Mesh(new THREE.PlaneGeometry(W, D), floorMat);
  floor.rotation.x = -Math.PI / 2;
  floor.receiveShadow = true;
  roomGroup.add(floor);
  const grid = new THREE.GridHelper(Math.max(W, D), Math.round(Math.max(W, D) * 2), 0x6b7d74, 0x3d4a44);
  grid.scale.set(W / Math.max(W, D), 1, D / Math.max(W, D));
  grid.position.y = 0.002;
  roomGroup.add(grid);

  // two back walls are solid-ish, the two front walls are only outlined so the camera can see in
  const wallMat = mat(0xcfd6d2, { transparent: true, opacity: 0.35, side: THREE.DoubleSide });
  const back = new THREE.Mesh(new THREE.PlaneGeometry(W, H), wallMat);
  back.position.set(0, H / 2, -D / 2);
  const left = new THREE.Mesh(new THREE.PlaneGeometry(D, H), wallMat);
  left.rotation.y = Math.PI / 2;
  left.position.set(-W / 2, H / 2, 0);
  roomGroup.add(back, left);
  const edges = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(W, H, D)),
    new THREE.LineBasicMaterial({ color: COLORS.ok, transparent: true, opacity: 0.9 }));
  edges.position.y = H / 2;
  roomGroup.add(edges);

  const blockers = [];
  for (const f of conf.furniture || []) {
    const g = furniture(f);
    const p = toWorld([f.pos[0], f.pos[1], 0], conf.size);
    g.position.copy(p);
    g.rotation.y = -THREE.MathUtils.degToRad(f.rot || 0);
    roomGroup.add(g);
    const [w, d] = f.size || [1, 1];
    blockers.push({ kind: f.kind, center: p, yaw: g.rotation.y, half: [w / 2 + 0.3, d / 2 + 0.3], surface: g.userData.surface, size: [w, d] });
  }

  const tx = node("TX", 0xffffff);
  tx.position.copy(toWorld(conf.tx, conf.size));
  roomGroup.add(tx);
  const rxNodes = {};
  const links = [];
  for (const [id, p] of Object.entries(conf.rx || {})) {
    const n = node(`RX ${id}`, COLORS.ok);
    n.position.copy(toWorld(p, conf.size));
    roomGroup.add(n);
    rxNodes[id] = n;
    const geo = new THREE.BufferGeometry().setFromPoints([tx.position.clone(), n.position.clone()]);
    const line = new THREE.Line(geo, new THREE.LineDashedMaterial({ color: COLORS.ok, dashSize: 0.12, gapSize: 0.08, transparent: true, opacity: 0.8 }));
    line.computeLineDistances();
    roomGroup.add(line);
    links.push({ id, line });
  }

  // pulse ring shown on the floor where the person fell
  const ring = new THREE.Mesh(new THREE.RingGeometry(0.55, 0.7, 48), new THREE.MeshBasicMaterial({ color: COLORS.bad, transparent: true, opacity: 0.8, side: THREE.DoubleSide }));
  ring.rotation.x = -Math.PI / 2;
  ring.position.y = 0.01;
  ring.visible = false;
  roomGroup.add(ring);

  room = { conf, W, D, H, floorMat, edges, rxNodes, links, ring, blockers, path: walkPath(W, D, blockers) };
  fitCamera();
  moodLight.position.set(0, H - 0.3, 0);
  person.root.position.set(0, 0, 0);
}

function insideBlocker(x, z, blockers) {
  return blockers.some(b => {
    const dx = x - b.center.x, dz = z - b.center.z;
    const c = Math.cos(-b.yaw), s = Math.sin(-b.yaw);
    const lx = dx * c - dz * s, lz = dx * s + dz * c;
    return Math.abs(lx) < b.half[0] && Math.abs(lz) < b.half[1];
  });
}
function walkPath(W, D, blockers) {
  const pts = [];
  for (let i = 0; i < 16; i++) {
    const a = (i / 16) * Math.PI * 2;
    for (const k of [0.3, 0.22, 0.14]) {
      const x = Math.cos(a) * W * k, z = Math.sin(a) * D * k;
      if (!insideBlocker(x, z, blockers)) { pts.push(new THREE.Vector3(x, 0, z)); break; }
    }
  }
  return pts.length >= 3 ? pts : [new THREE.Vector3(-0.4, 0, 0), new THREE.Vector3(0.4, 0, 0), new THREE.Vector3(0, 0, 0.4)];
}

// ---------------------------------------------------------------- person
function limb(len, r, material) {
  const pivot = new THREE.Group();
  const m = new THREE.Mesh(new THREE.CapsuleGeometry(r, len - 2 * r, 4, 10), material);
  m.position.y = -len / 2;
  m.castShadow = true;
  pivot.add(m);
  return pivot;
}
const person = (() => {
  const skin = mat(0xe0b18f), shirt = mat(0x3f7fd0), pants = mat(0x2f3b4c);
  const root = new THREE.Group();
  const body = new THREE.Group();            // tilts as a whole for lying / falling
  root.add(body);
  const torso = new THREE.Mesh(new THREE.CapsuleGeometry(0.15, 0.32, 4, 12), shirt);
  torso.position.y = 0.3; torso.castShadow = true;
  const head = new THREE.Mesh(new THREE.SphereGeometry(0.11, 16, 12), skin);
  head.position.y = 0.72; head.castShadow = true;
  body.add(torso, head);
  const j = {};
  for (const side of [-1, 1]) {
    const hip = limb(0.45, 0.07, pants); hip.position.set(side * 0.09, 0, 0);
    const knee = limb(0.45, 0.06, pants); knee.position.y = -0.45; hip.add(knee);
    const sh = limb(0.3, 0.05, shirt); sh.position.set(side * 0.2, 0.55, 0);
    const el = limb(0.28, 0.045, skin); el.position.y = -0.3; sh.add(el);
    body.add(hip, sh);
    const k = side < 0 ? "L" : "R";
    Object.assign(j, { ["hip" + k]: hip, ["knee" + k]: knee, ["sh" + k]: sh, ["el" + k]: el });
  }
  return { root, body, j, materials: [skin, shirt, pants], shirt };
})();
scene.add(person.root);

// joint angles (radians, about the local x axis) + body height / tilt
const POSES = {
  stand: { y: 0.92, tilt: 0, roll: 0, hipL: 0, hipR: 0, kneeL: 0, kneeR: 0, shL: 0.05, shR: 0.05, elL: 0, elR: 0 },
  sit:   { y: 0.5, tilt: 0, roll: 0, hipL: -1.5, hipR: -1.5, kneeL: 1.5, kneeR: 1.5, shL: -0.3, shR: -0.3, elL: -0.6, elR: -0.6 },
  lie:   { y: 0.62, tilt: -Math.PI / 2, roll: 0, hipL: 0, hipR: 0, kneeL: 0.1, kneeR: 0.1, shL: 0.2, shR: 0.2, elL: 0, elR: 0 },
  fall:  { y: 0.16, tilt: Math.PI / 2, roll: 0.25, hipL: 0.35, hipR: -0.2, kneeL: 0.9, kneeR: 0.3, shL: -2.4, shR: -1.2, elL: -0.5, elR: -0.9 },
};
const JOINTS = ["hipL", "hipR", "kneeL", "kneeR", "shL", "shR", "elL", "elR"];
const cur = { ...POSES.stand };
const sim = { pos: new THREE.Vector3(), yaw: 0, waypoint: 0, phase: 0, opacity: 1, fallPos: null };

function blendPose(target, rate) {
  for (const k of Object.keys(target)) cur[k] += (target[k] - cur[k]) * rate;
}
function applyPose(walkSwing) {
  const { j, body, root } = person;
  root.position.set(sim.pos.x, cur.y, sim.pos.z);
  root.rotation.set(0, sim.yaw, 0);
  body.rotation.set(cur.tilt, 0, cur.roll);
  for (const k of JOINTS) j[k].rotation.x = cur[k];
  if (walkSwing) {
    const s = Math.sin(sim.phase) * 0.55;
    j.hipL.rotation.x += s; j.hipR.rotation.x -= s;
    j.kneeL.rotation.x += Math.max(0, -s) * 0.9; j.kneeR.rotation.x += Math.max(0, s) * 0.9;
    j.shL.rotation.x -= s * 0.8; j.shR.rotation.x += s * 0.8;
  }
}
function setPersonOpacity(a) {
  person.root.visible = a > 0.02;
  for (const m of person.materials) { m.transparent = a < 0.99; m.opacity = a; }
}
function seatFor(kind) { return room?.blockers.find(b => b.kind === kind) || null; }

// Move the avatar toward what the classifier reports. Positions are illustrative: CSI gives the activity, not coordinates.
function stepPerson(dt, status) {
  if (!room) return;
  const red = RED_STATES.has(status.state);
  const activity = red ? "fall" : status.activity;
  const off = OFF_STATES.has(status.state);
  const visible = !off && activity !== "empty" && activity !== "unknown";
  sim.opacity += ((visible ? 1 : 0) - sim.opacity) * Math.min(1, dt * 3);
  setPersonOpacity(sim.opacity);

  let goal = null, pose = POSES.stand, yawGoal = sim.yaw, walking = false;
  if (activity === "fall") {
    if (!sim.fallPos) sim.fallPos = sim.pos.clone();
    pose = POSES.fall;
  } else {
    sim.fallPos = null;
    if (activity === "walk") {
      const wp = room.path[sim.waypoint % room.path.length];
      if (sim.pos.distanceTo(wp) < 0.15) sim.waypoint++;
      goal = room.path[sim.waypoint % room.path.length];
    } else if (activity === "sit" || activity === "lie") {
      const b = seatFor(activity === "sit" ? "chair" : "bed") || seatFor("sofa");
      if (b) {
        goal = b.center.clone();
        if (activity === "lie") goal.add(new THREE.Vector3(0, 0, 0.2).applyAxisAngle(new THREE.Vector3(0, 1, 0), b.yaw));
        yawGoal = activity === "lie" ? b.yaw + Math.PI : b.yaw;
      }
      pose = activity === "sit" ? POSES.sit : { ...POSES.lie, y: (b?.surface ?? 0) + 0.14 };
    }
  }

  if (goal) {
    const to = goal.clone().sub(sim.pos); to.y = 0;
    const dist = to.length();
    const arrive = activity === "walk" ? 0.05 : 0.08;
    if (dist > arrive) {
      walking = true;
      const step = Math.min(dist, 0.9 * dt);
      sim.pos.add(to.normalize().multiplyScalar(step));
      yawGoal = Math.atan2(to.x, to.z);
      if (activity !== "walk") pose = POSES.stand; // walk over first, then sit / lie down
    }
  }
  let dy = yawGoal - sim.yaw;
  dy = Math.atan2(Math.sin(dy), Math.cos(dy));
  sim.yaw += dy * Math.min(1, dt * 6);
  sim.phase += walking ? dt * 7 : 0;
  blendPose(pose, Math.min(1, dt * (activity === "fall" ? 9 : 4)));
  applyPose(walking);

  const ring = room.ring;
  ring.visible = activity === "fall" && sim.opacity > 0.5;
  if (ring.visible) {
    ring.position.set(sim.pos.x, 0.01, sim.pos.z);
    const k = 1 + 0.25 * Math.sin(performance.now() / 200);
    ring.scale.set(k, k, k);
  }
  const shirtColor = red ? COLORS.bad : 0x3f7fd0;
  person.shirt.color.setHex(shirtColor);
}

// ---------------------------------------------------------------- UI
const $ = id => document.getElementById(id);
let status = { state: "offline", activity: "unknown", probs: {}, nodes: [] };
let wasRed = false, muted = false, connected = false;

function mode(state) { return RED_STATES.has(state) ? "bad" : OFF_STATES.has(state) ? "off" : "ok"; }

function render(s) {
  const m = mode(s.state);
  document.body.className = m;
  const color = COLORS[m];
  scene.background.setHex(m === "bad" ? 0x2a0d0d : m === "off" ? 0x15181b : 0x0d1a14);
  moodLight.color.setHex(color);
  if (room) {
    room.edges.material.color.setHex(color);
    room.floorMat.color.setHex(m === "bad" ? 0x4a2523 : m === "off" ? 0x2f3336 : 0x2b3a33);
    const online = new Map((s.nodes || []).map(n => [String(n.node ?? n.node_id), n.online]));
    for (const { id, line } of room.links) {
      const on = online.size ? online.get(String(id)) : connected;
      line.material.color.setHex(on ? color : COLORS.off);
      line.material.opacity = on ? 0.85 : 0.25;
      room.rxNodes[id].userData.led.material.color.setHex(on ? COLORS.ok : COLORS.off);
    }
  }

  const titles = { ok: "NORMAL", bad: s.state === "alert" ? "XAVF: turmayapti" : "XAVF: yiqilish", off: "Aloqa yo'q" };
  $("stateText").textContent = titles[m];
  const nodes = s.nodes || [];
  const onlineCount = nodes.filter(n => n.online).length;
  $("subText").textContent = m === "off"
    ? (s.state === "waiting_for_nodes" ? "Platalardan signal kutilmoqda" : cfg.demo ? "Demo" : (cfg.server ? `Server: ${cfg.server}` : "Sozlamalarda server manzilini kiriting"))
    : `${room?.conf.name || "Xona"} · ${cfg.demo ? "demo rejim" : "jonli"}`;
  $("activity").textContent = ACTIVITY_UZ[RED_STATES.has(s.state) ? "fall" : s.activity] || s.activity || "—";
  const pf = s.probs?.fall;
  $("fallProb").textContent = pf == null ? "—" : `${Math.round(pf * 100)}%`;
  $("nodes").textContent = nodes.length ? `${onlineCount}/${nodes.length} onlayn` : "—";

  const red = m === "bad";
  if (red && !wasRed) { muted = false; $("alert").hidden = false; }
  if (!red) $("alert").hidden = true;
  if (red) {
    $("alertText").textContent = s.state === "alert" ? "Odam yiqildi va turmayapti!" : "Yiqilish aniqlandi";
    const since = s.fall_since ? Math.max(0, Math.round((s.server_time || Date.now() / 1000) - s.fall_since)) : null;
    $("alertSince").textContent = since == null ? "" : `${since} soniya oldin`;
  }
  alarm(red && !muted);
  wasRed = red;
}

let audioCtx = null, beepTimer = null, alarmOn = false;
function alarm(on) {
  if (on === alarmOn) return;
  alarmOn = on;
  if (bridge) { bridge.alarm(on); return; }
  // browser fallback: vibrate + short beeps
  clearInterval(beepTimer);
  if (!on) { navigator.vibrate?.(0); return; }
  const beep = () => {
    navigator.vibrate?.([400, 200, 400]);
    try {
      audioCtx ??= new AudioContext();
      const o = audioCtx.createOscillator(), g = audioCtx.createGain();
      o.frequency.value = 880; g.gain.value = 0.15;
      o.connect(g).connect(audioCtx.destination);
      o.start(); o.stop(audioCtx.currentTime + 0.35);
    } catch { /* autoplay blocked */ }
  };
  beep();
  beepTimer = setInterval(beep, 1200);
}

$("muteBtn").onclick = () => { muted = true; alarm(false); $("alert").hidden = true; };
$("ackBtn").onclick = async () => {
  muted = true; alarm(false); $("alert").hidden = true;
  if (cfg.demo) { demo.ack(); return; }
  try { await fetch(`${cfg.server}/api/ack`, { method: "POST" }); } catch { /* shown by the next status */ }
};
$("settingsBtn").onclick = () => { $("serverInput").value = cfg.server; $("demoInput").checked = cfg.demo; $("settings").hidden = false; };
$("closeBtn").onclick = () => { $("settings").hidden = true; };
$("saveBtn").onclick = () => {
  cfg.server = $("serverInput").value.trim().replace(/\/+$/, "");
  if (cfg.server && !/^https?:\/\//.test(cfg.server)) cfg.server = "http://" + cfg.server;
  cfg.demo = $("demoInput").checked;
  saveCfg();
  $("settings").hidden = true;
  start();
};

// ---------------------------------------------------------------- data sources
let ws = null, retry = null;
function stopLive() { clearTimeout(retry); if (ws) { ws.onclose = null; ws.close(); ws = null; } connected = false; }

async function loadRoom() {
  try {
    const r = await fetch(`${cfg.server}/api/room`, { cache: "no-store" });
    if (r.ok) { buildRoom(await r.json()); return; }
  } catch { /* keep the default room */ }
  if (!room) buildRoom(DEFAULT_ROOM);
}

function connectLive() {
  stopLive();
  if (!cfg.server) { status = { ...status, state: "offline" }; render(status); return; }
  loadRoom();
  const url = cfg.server.replace(/^http/, "ws") + "/ws";
  ws = new WebSocket(url);
  ws.onopen = () => { connected = true; };
  ws.onmessage = e => { status = JSON.parse(e.data); render(status); };
  ws.onclose = () => {
    connected = false;
    status = { ...status, state: "offline", nodes: [] };
    render(status);
    retry = setTimeout(connectLive, 3000);
  };
}

// Scripted day in the room so the app can be shown without boards or a server.
const demo = (() => {
  const script = [["walk", 9], ["sit", 7], ["walk", 6], ["lie", 7], ["walk", 6], ["fall", 0]];
  let i = 0, t0 = 0, timer = null, fallAt = null;
  function tick() {
    const now = Date.now() / 1000;
    const [act, dur] = script[i];
    let state = "monitoring", activity = act;
    if (act === "fall") {
      fallAt ??= now;
      state = now - fallAt > 8 ? "alert" : "fall_suspected";
      activity = now - fallAt > 2 ? "still" : "fall";
      if (now - fallAt > 40) next(now); // nobody pressed the button: the person "gets up" by themselves
    } else if (now - t0 > dur) next(now);
    const pf = act === "fall" ? 0.86 : 0.02 + Math.random() * 0.05;
    status = {
      state, activity, fall_since: fallAt, server_time: now,
      probs: { fall: pf }, nodes: [0, 1, 2].map(id => ({ node: id, online: true })),
    };
    render(status);
  }
  function next(now) { i = (i + 1) % script.length; t0 = now; fallAt = null; }
  return {
    start() { this.stop(); i = 0; t0 = Date.now() / 1000; fallAt = null; if (!room) buildRoom(DEFAULT_ROOM); timer = setInterval(tick, 500); tick(); },
    stop() { clearInterval(timer); },
    ack() { next(Date.now() / 1000); },
  };
})();

function start() {
  demo.stop();
  stopLive();
  if (cfg.demo) demo.start(); else connectLive();
  if (!cfg.demo && !cfg.server) $("settingsBtn").click();
}

// ---------------------------------------------------------------- loop
function resize() {
  const w = host.clientWidth || innerWidth, h = host.clientHeight || innerHeight;
  renderer.setSize(w, h, false);
  renderer.domElement.style.width = w + "px";
  renderer.domElement.style.height = h + "px";
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  fitCamera();
}
addEventListener("resize", resize);
resize();

const label = $("personLabel");
const clock = new THREE.Clock();
let dash = 0;
renderer.setAnimationLoop(() => {
  const dt = Math.min(clock.getDelta(), 0.1);
  stepPerson(dt, status);
  if (room) {
    dash -= dt * (0.3 + Math.min(1, (status.motion || 0) * 20));
    for (const { line } of room.links) line.material.dashOffset = dash;
  }
  controls.update();
  renderer.render(scene, camera);
  if (person.root.visible && sim.opacity > 0.5) {
    const p = person.root.position.clone(); p.y = cur.y + (cur.tilt ? 0.35 : 0.95);
    p.project(camera);
    label.hidden = false;
    label.style.left = `${(p.x * 0.5 + 0.5) * innerWidth}px`;
    label.style.top = `${(-p.y * 0.5 + 0.5) * innerHeight}px`;
    label.textContent = ACTIVITY_UZ[RED_STATES.has(status.state) ? "fall" : status.activity] || "";
  } else label.hidden = true;
});

buildRoom(DEFAULT_ROOM);
render(status);
start();
window.wfgResume = () => { alarmOn = false; render(status); };
window.wfgDebug = { get status() { return status; }, cfg };
