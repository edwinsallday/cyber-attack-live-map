// The Live Cyber Attack Map: interactive globe (Datafloq).
// Static files only. The data file data/incidents.json is rewritten by pipeline/update.py on a schedule,
// and this page re-reads it every few minutes.
import * as THREE from 'three';
import { OrbitControls } from './vendor/OrbitControls.js';

const $ = (s) => document.querySelector(s);
const REDUCED = matchMedia('(prefers-reduced-motion: reduce)').matches;
const NARROW = () => innerWidth < 900;
const REFRESH_MS = 5 * 60 * 1000;
const FRESH_HOURS = 48;            // newer than this pulses

const TYPES = {
  ransomware:      { label: 'Ransomware',         color: '#ff4b14' },
  data_breach:     { label: 'Data breach',        color: '#ffb23e' },
  supply_chain:    { label: 'Supply chain',       color: '#4cc9f0' },
  espionage:       { label: 'Espionage',          color: '#b79cff' },
  financial_theft: { label: 'Financial theft',    color: '#2fd47a' },
  ddos:            { label: 'DDoS',               color: '#ff5fa2' },
  phishing:        { label: 'Phishing',           color: '#ffe66b' },
  other:           { label: 'Sabotage and other', color: '#e9e4dc' },
};
const CONF_LABEL = {
  high: 'Victim and attack type are stated outright in the report',
  medium: 'Victim and country were both found in the report by keyword matching',
  low: 'Only part of the picture could be read from the report; treat the details with caution',
};
const PIN_LABEL = {
  city: 'Placed at the victim’s city',
  country: 'Placed at the centre of the victim’s country (city not known)',
  none: 'Not on the globe: the report does not say where the victim is based',
};

// ---------- helpers ----------
const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const ease = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
function sph(lat, lon, r = 1) {
  const la = THREE.MathUtils.degToRad(lat), ph = THREE.MathUtils.degToRad(lon + 180);
  return new THREE.Vector3(-Math.cos(ph) * Math.cos(la) * r, Math.sin(la) * r, Math.sin(ph) * Math.cos(la) * r);
}
function el(tag, props = {}, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === 'class') e.className = v; else if (k === 'text') e.textContent = v; else if (v != null) e.setAttribute(k, v);
  }
  for (const k of kids) if (k != null) e.append(k);
  return e;
}
const safeUrl = (u) => (/^https?:\/\//i.test(u || '') ? u : null);
const typeOf = (c) => TYPES[c.type] || TYPES.other;
// The headline is the most reliable label; the extracted victim name is shown as a field on the card.
const nameOf = (c) => (c.sources[0] && c.sources[0].title) || c.victim || 'Unnamed incident';
const ageHours = (iso) => (Date.now() - Date.parse(iso)) / 36e5;
function ago(iso) {
  const h = ageHours(iso);
  if (h < 1) return Math.max(1, Math.round(h * 60)) + ' min ago';
  if (h < 48) return Math.round(h) + ' h ago';
  return Math.round(h / 24) + ' d ago';
}
const fmtDate = (iso) => new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' });

// ---------- three.js setup ----------
const canvas = $('#globe');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: 'high-performance' });
renderer.setPixelRatio(Math.min(devicePixelRatio, 1.75));
renderer.outputColorSpace = THREE.SRGBColorSpace;
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0e0e10);
const camera = new THREE.PerspectiveCamera(35, 1, 0.01, 200);
function homeDistance() {
  const vh = THREE.MathUtils.degToRad(camera.fov / 2), hh = Math.atan(Math.tan(vh) * camera.aspect);
  return Math.max(3.2, 1.18 / Math.sin(Math.min(vh, hh)));
}
const HOME_DIR = sph(30, -30).normalize();
const home = () => HOME_DIR.clone().multiplyScalar(homeDistance());
camera.position.copy(HOME_DIR).multiplyScalar(4.5);

const controls = new OrbitControls(camera, canvas);
controls.enableDamping = true; controls.dampingFactor = 0.08;
controls.enablePan = false; controls.minDistance = 1.25; controls.maxDistance = 6;
controls.rotateSpeed = 0.5; controls.zoomSpeed = 0.8;
controls.enableZoom = false;                          // wheel zoom needs Ctrl/Cmd so the page can still scroll
controls.autoRotate = !REDUCED; controls.autoRotateSpeed = 0.35;
controls.addEventListener('start', () => { controls.autoRotate = false; hideTip(); });
controls.addEventListener('change', () => {
  controls.rotateSpeed = 0.12 + 0.4 * clamp((camera.position.length() - 1.25) / 3);
});

let hintTimer;
canvas.addEventListener('wheel', (e) => {
  controls.enableZoom = e.ctrlKey || e.metaKey;
  if (!controls.enableZoom) { $('#hint').hidden = false; clearTimeout(hintTimer); hintTimer = setTimeout(() => ($('#hint').hidden = true), 1200); }
}, { capture: true, passive: true });
canvas.addEventListener('touchstart', () => { controls.enableZoom = true; }, { passive: true });

function glowTexture() {
  const c = document.createElement('canvas'); c.width = c.height = 128;
  const g = c.getContext('2d'), grad = g.createRadialGradient(64, 64, 0, 64, 64, 64);
  grad.addColorStop(0, 'rgba(255,255,255,1)'); grad.addColorStop(0.25, 'rgba(255,255,255,0.45)'); grad.addColorStop(1, 'rgba(255,255,255,0)');
  g.fillStyle = grad; g.fillRect(0, 0, 128, 128);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
}

// Two looks for the globe; the visitor's choice is remembered in their browser.
const earth = { photo: null, holo: null, uniforms: null, style: 'holo' };
try { if (localStorage.getItem('globeStyle') === 'photo') earth.style = 'photo'; } catch (e) { /* storage unavailable */ }
function setStyle(style) {
  earth.style = style;
  if (earth.photo) { earth.photo.visible = style === 'photo'; earth.holo.visible = style !== 'photo'; }
  const big = Math.min(screen.width, screen.height) >= 700 && renderer.capabilities.maxTextureSize >= 4096;
  if (earth.photo && style === 'photo' && big && !earth.sharp) {
    earth.sharp = true;
    new THREE.TextureLoader().loadAsync('assets/earth-night-4k.jpg').then((hi) => {
      hi.colorSpace = THREE.SRGBColorSpace; hi.anisotropy = renderer.capabilities.getMaxAnisotropy();
      earth.photo.material.map = hi; earth.photo.material.needsUpdate = true;
    }).catch(() => { earth.sharp = false; });
  }
  $('#style').setAttribute('aria-label', style === 'photo' ? 'Switch to hologram globe' : 'Switch to night-photo globe');
  try { localStorage.setItem('globeStyle', style); } catch (e) { /* storage unavailable */ }
}
$('#style').addEventListener('click', () => setStyle(earth.style === 'photo' ? 'holo' : 'photo'));

async function buildEarth() {
  // The small image is enough for the hologram style; the large one is fetched only if the photo style is chosen.
  const tex = await new THREE.TextureLoader().loadAsync('assets/earth-night-2k.jpg');
  tex.colorSpace = THREE.SRGBColorSpace; tex.anisotropy = renderer.capabilities.getMaxAnisotropy();
  const sphere = new THREE.SphereGeometry(1, 96, 64);
  earth.photo = new THREE.Mesh(sphere, new THREE.MeshBasicMaterial({ map: tex, color: new THREE.Color(1.3, 1.3, 1.35) }));

  // "Hologram" style: land drawn as a grid of dots, city lights on top, a scan line drifting north to south.
  // The land mask is painted from the same border file the map already loads.
  const W = 2048, H = 1024, cv = document.createElement('canvas'); cv.width = W; cv.height = H;
  const g = cv.getContext('2d'); g.fillStyle = '#000'; g.fillRect(0, 0, W, H); g.fillStyle = '#fff';
  for (const f of topojson.feature(world, world.objects.countries).features) {
    const polys = f.geometry.type === 'MultiPolygon' ? f.geometry.coordinates : [f.geometry.coordinates];
    for (const shift of [0, -W, W]) {                       // repeat so shapes crossing the date line wrap round
      g.beginPath();
      for (const poly of polys) for (const ring of poly) {
        ring.forEach(([lon, lat], i) => { const x = (lon + 180) / 360 * W + shift, y = (90 - lat) / 180 * H; i ? g.lineTo(x, y) : g.moveTo(x, y); });
        g.closePath();
      }
      g.fill('evenodd');
    }
  }
  const mask = new THREE.CanvasTexture(cv); mask.generateMipmaps = false; mask.minFilter = mask.magFilter = THREE.LinearFilter;
  earth.uniforms = { mask: { value: mask }, lights: { value: tex }, time: { value: 0 } };
  earth.holo = new THREE.Mesh(sphere, new THREE.ShaderMaterial({
    uniforms: earth.uniforms,
    vertexShader: `varying vec2 vUv; varying vec3 vN; varying vec3 vV; void main(){ vUv = uv; vec4 mv = modelViewMatrix*vec4(position,1.0); vN = normalize(normalMatrix*normal); vV = normalize(-mv.xyz); gl_Position = projectionMatrix*mv; }`,
    fragmentShader: `uniform sampler2D mask; uniform sampler2D lights; uniform float time; varying vec2 vUv; varying vec3 vN; varying vec3 vV;
      void main(){
        float rows = 170.0, row = floor(vUv.y*rows);
        float lat = ((row + 0.5)/rows - 0.5)*3.14159265;
        float cols = max(1.0, floor(rows*2.0*cos(lat)));               // fewer dots per row towards the poles keeps them evenly spaced
        vec2 cell = vec2(fract(vUv.x*cols), fract(vUv.y*rows)) - 0.5;
        vec2 centre = vec2((floor(vUv.x*cols) + 0.5)/cols, (row + 0.5)/rows);
        float land = step(0.5, texture2D(mask, centre).r);
        float d = smoothstep(0.31, 0.20, length(cell))*land;
        float facing = max(dot(vN, vV), 0.0);
        float sweep = smoothstep(0.05, 0.0, abs(fract(vUv.y + time*0.04) - 0.5));
        vec3 night = texture2D(lights, vUv).rgb;
        vec3 col = vec3(0.020, 0.020, 0.024)
          + vec3(0.20, 0.185, 0.175)*d*(0.45 + 0.55*facing)
          + night*vec3(1.0, 0.50, 0.22)*1.25
          + vec3(1.0, 0.36, 0.10)*sweep*(0.03 + 0.6*d);
        gl_FragColor = vec4(col, 1.0);
        #include <colorspace_fragment>
      }`,
  }));
  scene.add(earth.photo, earth.holo);
  setStyle(earth.style);
  scene.add(new THREE.Mesh(new THREE.SphereGeometry(1.0015, 96, 64), new THREE.ShaderMaterial({
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
    vertexShader: `varying vec3 vN; varying vec3 vV; void main(){ vec4 mv = modelViewMatrix*vec4(position,1.0); vN = normalize(normalMatrix*normal); vV = normalize(-mv.xyz); gl_Position = projectionMatrix*mv; }`,
    fragmentShader: `varying vec3 vN; varying vec3 vV; void main(){ float f = pow(1.0 - max(dot(vN, vV), 0.0), 3.0); gl_FragColor = vec4(vec3(1.0,0.34,0.10)*f*0.8, 1.0); }`,
  })));
  scene.add(new THREE.Mesh(new THREE.SphereGeometry(1.09, 96, 64), new THREE.ShaderMaterial({
    side: THREE.BackSide, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
    vertexShader: `varying vec3 vN; varying vec3 vW; void main(){ vN = normalize(normalMatrix*normal); vW = (modelMatrix*vec4(position,1.0)).xyz; gl_Position = projectionMatrix*viewMatrix*vec4(vW,1.0); }`,
    fragmentShader: `varying vec3 vN; varying vec3 vW; void main(){ vec3 v = normalize((viewMatrix*vec4(vW - cameraPosition, 0.0)).xyz); float i = pow(clamp(0.12 + dot(v, vN), 0.0, 1.0), 3.2); gl_FragColor = vec4(vec3(1.0,0.32,0.08)*i*1.25, 1.0); }`,
  })));
}

async function buildBorders() {
  world = await (await fetch('assets/countries-110m.json')).json();
  const mesh = topojson.mesh(world, world.objects.countries);
  // faint latitude/longitude grid
  const grid = [];
  for (let lat = -60; lat <= 60; lat += 20) for (let lon = -180; lon < 180; lon += 4) grid.push(sph(lat, lon, 1.001), sph(lat, lon + 4, 1.001));
  for (let lon = -180; lon < 180; lon += 20) for (let lat = -80; lat < 80; lat += 4) grid.push(sph(lat, lon, 1.001), sph(lat + 4, lon, 1.001));
  scene.add(new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(grid), new THREE.LineBasicMaterial({ color: 0xff4b14, transparent: true, opacity: 0.09, depthWrite: false })));
  const pts = [];
  for (const line of mesh.coordinates) for (let i = 0; i < line.length - 1; i++) pts.push(sph(line[i][1], line[i][0], 1.0012), sph(line[i + 1][1], line[i + 1][0], 1.0012));
  scene.add(new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(pts), new THREE.LineBasicMaterial({ color: 0xffc3a6, transparent: true, opacity: 0.20, depthWrite: false })));
}

function buildStars() {
  const n = 2200, pos = new Float32Array(n * 3), col = new Float32Array(n * 3);
  let s = 12345; const rnd = () => (s = (s * 16807) % 2147483647) / 2147483647;
  for (let i = 0; i < n; i++) {
    const u = rnd() * 2 - 1, th = rnd() * Math.PI * 2, r = Math.sqrt(1 - u * u);
    pos.set([r * Math.cos(th) * 80, u * 80, r * Math.sin(th) * 80], i * 3);
    const b = 0.25 + Math.pow(rnd(), 3) * 0.75; col.set([b, b, b], i * 3);
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3)); geo.setAttribute('color', new THREE.BufferAttribute(col, 3));
  scene.add(new THREE.Points(geo, new THREE.PointsMaterial({ size: 1.8, sizeAttenuation: false, vertexColors: true, transparent: true, opacity: 0.8 })));
}

// ---------- incident pins and arcs ----------
const dotGeo = new THREE.CircleGeometry(0.007, 24).rotateX(-Math.PI / 2).translate(0, 0.0012, 0);
const ringGeo = new THREE.RingGeometry(0.009, 0.0105, 40).rotateX(-Math.PI / 2).translate(0, 0.001, 0);
const beamGeo = new THREE.CylinderGeometry(0.0009, 0.0042, 1, 14, 1, true).translate(0, 0.5, 0);
const SHARED_GEO = new Set([dotGeo, ringGeo, beamGeo]);
// a column of light that fades towards its tip
const beamMaterial = (color) => new THREE.ShaderMaterial({
  transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide,
  uniforms: { c: { value: color }, o: { value: 1 } },
  vertexShader: `varying float h; void main(){ h = position.y; gl_Position = projectionMatrix*modelViewMatrix*vec4(position,1.0); }`,
  fragmentShader: `uniform vec3 c; uniform float o; varying float h; void main(){ gl_FragColor = vec4(c, o*pow(1.0 - h, 1.5)); }`,
});
const glowTex = glowTexture();
const pins = new THREE.Group();
const outlines = new THREE.Group();      // borders of countries with incidents in view
scene.add(pins, outlines);
let world = null;
let incidents = [];              // [{c, mapped, lat, lon, up, g, glow, ring, arc, phase}]

const selRing = new THREE.Mesh(new THREE.TorusGeometry(0.018, 0.0018, 8, 64).rotateX(Math.PI / 2),
  new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.95, depthWrite: false }));
selRing.visible = false;

function arcPoints(from, to) {
  const a = from.clone().normalize(), b = to.clone().normalize(), angle = a.angleTo(b), pts = [];
  const q = new THREE.Quaternion().setFromUnitVectors(a, b), step = new THREE.Quaternion();
  for (let i = 0; i <= 64; i++) {
    const t = i / 64;
    pts.push(a.clone().applyQuaternion(step.identity().slerp(q, t)).multiplyScalar(1.003 + Math.sin(Math.PI * t) * (0.06 + 0.22 * angle / Math.PI)));
  }
  return pts;
}

function disposePins() {
  selRing.removeFromParent();
  clearGroup(pins);
}
function clearGroup(group) {
  group.traverse((o) => { if (o.material) o.material.dispose(); if (o.geometry && !SHARED_GEO.has(o.geometry)) o.geometry.dispose(); });
  group.clear();
}

// Light up the borders of every country that has an incident in the current view, in that incident's colour.
function outlineCountries(shown) {
  if (!world) return;
  const colour = new Map();
  for (const o of shown) if (o.c.country_key && !colour.has(o.c.country_key)) colour.set(o.c.country_key, typeOf(o.c).color);   // newest wins
  const sig = [...colour].join('|');
  if (sig === outlines.userData.sig) return;                       // same countries as last time: nothing to redraw
  outlines.userData.sig = sig;
  clearGroup(outlines);
  for (const g of world.objects.countries.geometries) {
    const col = colour.get(g.properties.name);
    if (!col) continue;
    const pts = [];
    for (const line of topojson.mesh(world, g).coordinates) for (let i = 0; i < line.length - 1; i++) pts.push(sph(line[i][1], line[i][0], 1.0022), sph(line[i + 1][1], line[i + 1][0], 1.0022));
    outlines.add(new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(pts), new THREE.LineBasicMaterial({ color: col, transparent: true, opacity: 0.8, depthWrite: false })));
  }
}

function buildPins(list) {
  disposePins();
  incidents = [];
  const placed = [];
  for (const c of list) {
    const o = { c, mapped: false, phase: (parseInt(c.id.slice(0, 6), 16) % 628) / 100 };
    incidents.push(o);
    const lat = Number(c.lat), lon0 = Number(c.lon);
    if (c.lat == null || c.lon == null || !Number.isFinite(lat) || !Number.isFinite(lon0)) continue;
    // several incidents at one spot are fanned out in a small circle so each can be picked
    const twins = placed.filter(p => Math.abs(p[0] - lat) < 0.05 && Math.abs(p[1] - lon0) < 0.05).length;
    placed.push([lat, lon0]);
    const ang = twins * 2.4, rad = twins ? 0.9 + 0.25 * twins : 0;
    o.lat = lat + Math.sin(ang) * rad; o.lon = lon0 + Math.cos(ang) * rad / Math.max(0.3, Math.cos(THREE.MathUtils.degToRad(lat)));
    o.mapped = true;
    o.up = sph(o.lat, o.lon).normalize();
    o.g = new THREE.Group(); o.g.position.copy(sph(o.lat, o.lon, 1)); o.g.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), o.up);
    const color = new THREE.Color(typeOf(c).color), fresh = ageHours(c.last_seen) < FRESH_HOURS;
    o.g.add(new THREE.Mesh(dotGeo, new THREE.MeshBasicMaterial({ color, depthWrite: false, transparent: true })));
    o.glow = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTex, color, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, opacity: fresh ? 1 : 0.6 }));
    o.glowBase = fresh ? 0.1 : 0.06; o.glow.scale.setScalar(o.glowBase); o.glow.position.y = 0.003; o.g.add(o.glow);
    o.beamH = fresh ? 0.085 : 0.045;
    o.beam = new THREE.Mesh(beamGeo, beamMaterial(color)); o.beam.scale.y = o.beamH; o.beam.material.uniforms.o.value = fresh ? 0.95 : 0.55; o.g.add(o.beam);
    if (fresh) {
      o.rings = [0, 0.5].map((offset) => {
        const r = new THREE.Mesh(ringGeo, new THREE.MeshBasicMaterial({ color, transparent: true, depthWrite: false, side: THREE.DoubleSide }));
        r.userData.offset = offset; o.g.add(r); return r;
      });
    }
    pins.add(o.g);
    if (c.attacker_lat != null && c.attacker_lon != null) o.from = sph(c.attacker_lat, c.attacker_lon);
  }
}

// ---------- filters ----------
const search = $('#search'), windowSel = $('#window'), list = $('#list');
let selected = null, updatedAt = null, feedErrors = [], onlyType = '';
const typeKey = (c) => (TYPES[c.type] ? c.type : 'other');

function matches(o) {
  const c = o.c, days = Number(windowSel.value), q = search.value.trim().toLowerCase();
  if (onlyType && typeKey(c) !== onlyType) return false;
  if (days && ageHours(c.last_seen) > days * 24) return false;
  if (!q) return true;
  return [c.victim, c.country, c.city, c.sector, c.actor, c.attacker_country, typeOf(c).label, ...c.sources.map(s => s.title)]
    .some(v => (v || '').toLowerCase().includes(q));
}

// ---------- recent activity list ----------
function row(o) {
  const t = typeOf(o.c), src = o.c.sources[0];
  const open = el('button', { type: 'button', class: 'open', 'data-id': o.c.id, 'aria-current': selected === o ? 'true' : 'false' },
    el('span', { class: 'tile', 'aria-hidden': 'true' }, el('i', { style: `background:${t.color};box-shadow:0 0 10px ${t.color}` })),
    el('span', { class: 'txt' }, el('span', { class: 'nm', text: nameOf(o.c) }),
      el('span', { class: 'meta', text: [t.label, o.c.country || 'Location not reported', ago(o.c.last_seen)].join(' • ') })));
  open.addEventListener('click', () => select(o, true));
  const link = src && safeUrl(src.url)
    ? el('a', { class: 'go', href: safeUrl(src.url), target: '_blank', rel: 'noopener', title: 'Open the report at ' + src.name, 'aria-label': 'Open the report at ' + src.name, text: '↗' })
    : null;
  return el('li', {}, open, link);
}

function refresh() {
  const shown = incidents.filter(matches);                       // already newest first
  const shownSet = new Set(shown);
  for (const o of incidents) if (o.g) o.g.visible = shownSet.has(o);
  view.mapped = shown.filter(o => o.mapped); view.k = -1;
  list.replaceChildren(...shown.map(row));
  $('#listCount').textContent = shown.length ? String(shown.length) : '';
  $('#empty').hidden = shown.length > 0;
  const unm = shown.filter(o => !o.mapped).length;
  $('#unmapped').textContent = (unm ? `${unm} of these ${unm === 1 ? 'is' : 'are'} in this list only: the reports do not say where the victim is based. ` : '')
    + (feedErrors.length ? 'Some news sources could not be read on the last update.' : '');
  if (selected && !shownSet.has(selected)) select(null);
  for (const b of $('#legend').children) b.setAttribute('aria-current', String(b.dataset.type === onlyType));
  outlineCountries(shown);
  ticker.items = shown.slice(0, 6); ticker.i = -1; tick();
  drawStats(shown); drawRank(shown);
}

// ---------- stat cards ----------
function dial(target, share, color, half) {
  const pct = Math.round(share * 100);
  target.innerHTML = half
    ? `<svg viewBox="0 0 64 64"><path class="track" d="M8 44 A24 24 0 0 1 56 44" fill="none" stroke-width="4" stroke-linecap="round"/>`
      + `<path d="M8 44 A24 24 0 0 1 56 44" fill="none" stroke="${color}" stroke-width="4" stroke-linecap="round" stroke-dasharray="${(75.4 * share).toFixed(1)} 76"/>`
      + `<text x="32" y="44" text-anchor="middle">${pct}%</text></svg>`
    : `<svg viewBox="0 0 64 64"><circle class="track" cx="32" cy="32" r="22" fill="none" stroke-width="4"/>`
      + `<circle cx="32" cy="32" r="22" fill="none" stroke="${color}" stroke-width="4" stroke-linecap="round" stroke-dasharray="${(138.2 * share).toFixed(1)} 139" transform="rotate(-90 32 32)"/>`
      + `<text x="32" y="36" text-anchor="middle">${pct}%</text></svg>`;
}
function bars(target, values, titles) {
  const max = Math.max(1, ...values);
  target.replaceChildren(...values.map((n, i) => el('i', { style: `height:${n ? 18 + 82 * n / max : 6}%;opacity:${n ? 1 : 0.3}`, title: titles[i] })));
}
function drawStats(shown) {
  const n = shown.length, days = Number(windowSel.value);
  $('#kIncidents').textContent = String(n);
  $('#kIncidentsSub').textContent = days === 1 ? 'in the last 24 hours' : days ? `in the last ${days} days` : 'currently on the map';
  const span = 14, perDay = new Array(span).fill(0), today = Math.floor(Date.now() / 864e5);
  for (const o of shown) { const i = span - 1 - (today - Math.floor(Date.parse(o.c.first_seen) / 864e5)); if (i >= 0 && i < span) perDay[i]++; }
  bars($('#sparkBars'), perDay, perDay.map((v, i) => `${v} first reported on ${fmtDate(new Date((today - (span - 1 - i)) * 864e5).toISOString())}`));

  const located = shown.filter(o => o.c.country).length;
  $('#kCountries').textContent = String(new Set(shown.map(o => o.c.country).filter(Boolean)).size);
  $('#kCountriesSub').textContent = n ? `${located} of ${n} reports name a country` : '';
  dial($('#kCountriesDial'), n ? located / n : 0, '#ff4b14', false);

  const byType = {};
  for (const o of shown) byType[typeKey(o.c)] = (byType[typeKey(o.c)] || 0) + 1;
  const top = Object.keys(byType).sort((a, b) => byType[b] - byType[a])[0];
  $('#kType').textContent = top ? TYPES[top].label : '–';
  $('#kTypeSub').textContent = top ? `${byType[top]} of ${n} incidents` : '';
  dial($('#kTypeDial'), top ? byType[top] / n : 0, top ? TYPES[top].color : '#9b968f', true);

  const bySource = new Map();
  for (const o of shown) for (const s of o.c.sources) bySource.set(s.name, (bySource.get(s.name) || 0) + 1);
  const ranked = [...bySource].sort((a, b) => b[1] - a[1]);
  $('#kLatest').textContent = n ? ago(shown[0].c.last_seen).replace(' ago', '') : '–';
  $('#kLatestSub').textContent = n ? 'ago, from ' + shown[0].c.sources[shown[0].c.sources.length - 1].name : '';
  bars($('#kLatestBars'), ranked.map(r => r[1]), ranked.map(r => `${r[0]}: ${r[1]} ${r[1] === 1 ? 'story' : 'stories'}`));
}

// ---------- most reported countries ----------
function drawRank(shown) {
  const by = new Map();
  for (const o of shown) if (o.c.country) by.set(o.c.country, (by.get(o.c.country) || 0) + 1);
  const top = [...by].sort((a, b) => b[1] - a[1]).slice(0, 4), max = top.length ? top[0][1] : 1;
  $('#rank').replaceChildren(...top.map(([name, n]) => {
    const b = el('button', { type: 'button', title: `Show incidents in ${name}` },
      el('span', { class: 'n', text: String(n) }), el('span', { class: 'c', text: name }), el('span', { class: 'bar' }, el('i', { style: `width:${100 * n / max}%` })));
    b.addEventListener('click', () => { search.value = search.value === name ? '' : name; refresh(); });
    return b;
  }));
  $('#rankWrap').hidden = !top.length;
}

// ---------- ticker: shows the incident being animated, or cycles the newest headlines ----------
const ticker = { items: [], i: -1, shown: null };
const tickText = $('#tickText');
function showTicker(o) {
  ticker.shown = o;
  tickText.classList.remove('in'); void tickText.offsetWidth;          // restart the fade
  tickText.replaceChildren(el('span', { class: 'tdot', style: `background:${typeOf(o.c).color}` }), nameOf(o.c), el('span', { class: 'tago', text: ' · ' + ago(o.c.last_seen) }));
  tickText.classList.add('in');
}
function tick() {
  const n = ticker.items.length;
  $('#ticker').hidden = !n;
  if (!n) return;
  ticker.i = (ticker.i + 1) % n;
  showTicker(ticker.items[ticker.i]);
}
tickText.addEventListener('click', () => { if (ticker.shown && incidents.includes(ticker.shown)) select(ticker.shown, true); });

// ---------- attack-type navigation in the sidebar ----------
function buildLegend() {
  const counts = {};
  for (const o of incidents) counts[typeKey(o.c)] = (counts[typeKey(o.c)] || 0) + 1;
  if (onlyType && !counts[onlyType]) onlyType = '';
  const item = (key, label, n, color) => {
    const b = el('button', { type: 'button', 'data-type': key }, el('span', { class: 'sw', style: color ? `background:${color}` : null }), label, el('span', { class: 'n', text: String(n) }));
    b.addEventListener('click', () => { onlyType = key; refresh(); });
    return b;
  };
  $('#legend').replaceChildren(item('', 'All incidents', incidents.length, null),
    ...Object.entries(TYPES).filter(([k]) => counts[k]).map(([k, t]) => item(k, t.label, counts[k], t.color)));
}

// ---------- detail card ----------
function select(o, fly) {
  selected = o;
  for (const b of list.querySelectorAll('button.open')) b.setAttribute('aria-current', b.dataset.id === (o && o.c.id) ? 'true' : 'false');
  if (!o) { $('#card').hidden = true; selRing.visible = false; history.replaceState(null, '', location.pathname + location.search); resize(); return; }
  renderCard(o.c); resize();
  if (o.mapped) { o.g.add(selRing); selRing.visible = true; if (fly) flyTo(o); } else selRing.visible = false;
  history.replaceState(null, '', '#incident=' + encodeURIComponent(o.c.id));
}
function renderCard(c) {
  const t = typeOf(c);
  const dl = el('dl', {});
  for (const [k, v] of [['Victim', c.victim], ['Attack type', t.label], ['Sector', c.sector], ['Scale', c.records], ['Group named', c.actor],
    ['Attributed to', c.attacker_country ? c.attacker_country + ' (as stated in the report)' : null],
    ['First reported', fmtDate(c.first_seen)], ['Latest report', c.sources.length > 1 ? fmtDate(c.last_seen) : null]]) {
    if (v) dl.append(el('dt', { text: k }), el('dd', { text: v }));
  }
  const kids = [
    el('span', { class: 'pill', style: `background:${t.color};color:#0b1e16`, text: t.label }),
    el('h2', { id: 'cardTitle', text: nameOf(c) }),
    el('p', { class: 'where', text: [c.city, c.country].filter(Boolean).join(', ') || 'Location not reported' }),
  ];
  if (c.summary) kids.push(el('p', { class: 'summary', text: c.summary }));
  kids.push(dl);
  kids.push(el('h3', { text: 'How solid is this' }), el('ul', {},
    el('li', { text: CONF_LABEL[c.confidence] || CONF_LABEL.low }),
    el('li', { text: PIN_LABEL[c.precision] || PIN_LABEL.none }),
    el('li', { text: 'Details were picked out automatically by keyword rules from the reports below' })));
  const srcs = c.sources.filter(s => safeUrl(s.url));
  if (srcs.length) kids.push(el('h3', { text: srcs.length > 1 ? `Reported by ${srcs.length} stories` : 'Source' }), el('ul', { class: 'src' }, ...srcs.map(s =>
    el('li', {}, el('a', { href: safeUrl(s.url), target: '_blank', rel: 'noopener', text: s.title }), ` · ${s.name}, ${fmtDate(s.published)}`))));
  $('#cardBody').replaceChildren(...kids);
  const card = $('#card'); card.hidden = false; card.setAttribute('aria-labelledby', 'cardTitle'); card.scrollTop = 0;
}
$('#cardClose').addEventListener('click', () => select(null));
addEventListener('keydown', (e) => { if (e.key === 'Escape' && !$('#card').hidden) select(null); });

// ---------- attack animations: an SVG layer drawn over the globe ----------
// Each strike is a missile flying from the reported origin to the victim, with a fading trail, an impact burst and
// two popup labels. When no report names an origin, the missile drops in from above the victim and the label says so.
const fx = $('#fx'), fxLabels = $('#fxLabels'), SVG_NS = 'http://www.w3.org/2000/svg';
const svg = (tag, attrs = {}) => { const e = document.createElementNS(SVG_NS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); return e; };
const FLIGHT = 1700, IMPACT = 1300, MAX_STRIKES = 4;
const strikes = [];
const view = { mapped: [], k: -1, w: 1, h: 1 };
const pv = new THREE.Vector3(), pd = new THREE.Vector3(), pp = new THREE.Vector3();
let strikeSeq = 0;

// screen position of a 3D point; returns false when the globe is in the way
function project(p, out) {
  pd.copy(p).sub(camera.position);
  const t = clamp(-camera.position.dot(pd) / pd.lengthSq());
  const hiddenByGlobe = t < 1 && pv.copy(camera.position).addScaledVector(pd, t).lengthSq() < 0.97;
  pv.copy(p).project(camera);
  out[0] = (pv.x * 0.5 + 0.5) * view.w; out[1] = (-pv.y * 0.5 + 0.5) * view.h;
  return !hiddenByGlobe && pv.z < 1;
}
function dropPoints(o) {                       // straight descent from above and slightly to one side of the victim
  const side = new THREE.Vector3(0, 1, 0).cross(o.up);
  if (side.lengthSq() < 1e-4) side.set(1, 0, 0);
  const start = o.up.clone().multiplyScalar(1.3).addScaledVector(side.normalize(), 0.3), pts = [];
  for (let i = 0; i <= 32; i++) pts.push(start.clone().lerp(o.g.position, i / 32));
  return pts;
}
function popup(title, sub, color) {
  const e = el('div', { class: 'fxlabel', style: `border-color:${color}` }, el('b', { text: title }), sub ? el('span', { text: sub }) : null);
  fxLabels.append(e);
  return e;
}
function place(label, xy, on) {
  label.classList.toggle('on', on);
  if (on) label.style.transform = `translate(${xy[0].toFixed(1)}px, ${xy[1].toFixed(1)}px)`;
}
function endStrike(k) {
  k.g.remove(); k.fromLabel.remove(); k.toLabel.remove();
  strikes.splice(strikes.indexOf(k), 1);
}
function launch(o, urgent) {
  if (REDUCED || !o.mapped || !o.g.visible || document.hidden) return;
  if (strikes.some(k => k.o === o)) return;
  if (strikes.length >= MAX_STRIKES) { if (!urgent) return; endStrike(strikes[0]); }
  const color = typeOf(o.c).color, id = 'trail' + (++strikeSeq);
  const grad = svg('linearGradient', { id, gradientUnits: 'userSpaceOnUse' });
  grad.append(svg('stop', { offset: 0, 'stop-color': color, 'stop-opacity': 0 }), svg('stop', { offset: 1, 'stop-color': color, 'stop-opacity': 1 }));
  const halo = svg('path', { fill: 'none', stroke: `url(#${id})`, 'stroke-width': 7, 'stroke-linecap': 'round', opacity: 0.28 });
  const trail = svg('path', { fill: 'none', stroke: `url(#${id})`, 'stroke-width': 2.2, 'stroke-linecap': 'round' });
  const missile = svg('g', { visibility: 'hidden' });
  missile.append(svg('path', { class: 'flame', d: 'M-3 0 L-15 -2.6 L-11 0 L-15 2.6 Z', fill: color }), svg('path', { d: 'M11 0 L-6 -4 L-2.5 0 L-6 4 Z', fill: '#fff' }));
  const flash = svg('circle', { r: 1, fill: color });
  const rings = [0, 1, 2].map(() => svg('circle', { r: 1, fill: 'none', stroke: color, 'stroke-width': 2 }));
  const impact = svg('g', { visibility: 'hidden' });
  impact.append(flash, ...rings);
  const g = svg('g');
  g.append(grad, halo, trail, missile, impact);
  fx.append(g);
  strikes.push({
    o, g, grad, halo, trail, missile, impact, rings, flash, t0: performance.now(), angle: 0, a: [0, 0], b: [0, 0],
    pts: o.from ? arcPoints(o.from, o.g.position) : dropPoints(o),
    fromLabel: popup(o.from ? (o.c.attacker_country || 'Origin').toUpperCase() : 'ORIGIN NOT REPORTED', o.from ? 'Attributed origin' : null, color),
    toLabel: popup((o.c.country || '').toUpperCase(), typeOf(o.c).label, color),
  });
}
function stepStrikes(now) {
  for (let s = strikes.length - 1; s >= 0; s--) {
    const k = strikes[s], age = now - k.t0;
    if (age > FLIGHT + IMPACT || !k.o.g.parent || !k.o.g.visible) { endStrike(k); continue; }
    const n = k.pts.length - 1, f = clamp(age / FLIGHT), q = clamp((age - FLIGHT) / IMPACT);
    const head = Math.pow(f, 1.6) * n, tail = Math.max(0, head - n * 0.45);       // accelerates like a launch
    let d = '', pen = false, first = true, hx = 0, hy = 0, px = 0, py = 0, headSeen = false;
    for (let i = Math.floor(tail), last = Math.ceil(head); i <= last; i++) {
      const u = Math.min(head, Math.max(tail, i)), seg = Math.min(n - 1, Math.floor(u));
      pp.lerpVectors(k.pts[seg], k.pts[seg + 1], u - seg);
      headSeen = project(pp, k.b);
      if (headSeen) {
        d += (pen ? 'L' : 'M') + k.b[0].toFixed(1) + ' ' + k.b[1].toFixed(1);
        if (first) { k.a[0] = k.b[0]; k.a[1] = k.b[1]; first = false; }
      }
      pen = headSeen; px = hx; py = hy; hx = k.b[0]; hy = k.b[1];
    }
    k.trail.setAttribute('d', d); k.halo.setAttribute('d', d);
    k.grad.setAttribute('x1', k.a[0]); k.grad.setAttribute('y1', k.a[1]); k.grad.setAttribute('x2', hx + 0.01); k.grad.setAttribute('y2', hy + 0.01);
    k.trail.setAttribute('opacity', 1 - q); k.halo.setAttribute('opacity', 0.28 * (1 - q));
    if (f < 1 && headSeen) {
      if (Math.abs(hx - px) + Math.abs(hy - py) > 0.3) k.angle = Math.atan2(hy - py, hx - px) * 57.29578;
      k.missile.setAttribute('transform', `translate(${hx.toFixed(1)} ${hy.toFixed(1)}) rotate(${k.angle.toFixed(1)})`);
      k.missile.setAttribute('visibility', 'visible');
    } else k.missile.setAttribute('visibility', 'hidden');
    place(k.fromLabel, k.b, project(k.pts[0], k.b) && f < 0.75);
    const hit = project(k.pts[n], k.b);
    place(k.toLabel, k.b, hit && f > 0.8 && q < 0.85);
    if (f >= 1 && hit) {
      k.impact.setAttribute('visibility', 'visible');
      k.impact.setAttribute('transform', `translate(${k.b[0].toFixed(1)} ${k.b[1].toFixed(1)})`);
      k.flash.setAttribute('r', (14 * (1 - q)).toFixed(1)); k.flash.setAttribute('opacity', (0.9 * (1 - q)).toFixed(2));
      k.rings.forEach((r, i) => {
        const w = clamp(q * 1.5 - i * 0.2);
        r.setAttribute('r', (4 + 38 * ease(w)).toFixed(1)); r.setAttribute('opacity', w > 0 ? (1 - w).toFixed(2) : 0);
      });
    } else k.impact.setAttribute('visibility', 'hidden');
  }
}

// ---------- Replay or Realtime ----------
// Replay loops through the incidents in view. Realtime stays quiet until a report arrives that was not there before.
let mode = 'replay', beats = 0;
try { if (localStorage.getItem('mapMode') === 'realtime') mode = 'realtime'; } catch (e) { /* storage unavailable */ }
function setMode(m) {
  mode = m;
  $('#modeReplay').setAttribute('aria-pressed', String(m === 'replay'));
  $('#modeLive').setAttribute('aria-pressed', String(m === 'realtime'));
  $('#liveBadge').classList.toggle('replay', m === 'replay');
  $('#liveText').textContent = m === 'realtime' ? 'LIVE' : 'REPLAY';
  $('#modeNote').textContent = m === 'realtime' ? 'Fires when a new report arrives. Checks every minute.' : 'Replaying recent reports in a loop.';
  try { localStorage.setItem('mapMode', m); } catch (e) { /* storage unavailable */ }
}
$('#modeReplay').addEventListener('click', () => setMode('replay'));
$('#modeLive').addEventListener('click', () => { setMode('realtime'); while (strikes.length) endStrike(strikes[0]); loadData().catch(() => {}); });
setMode(mode);
function beat() {
  if (document.hidden) return;
  if (mode === 'replay' && view.mapped.length) {
    view.k = (view.k + 1) % view.mapped.length;
    showTicker(view.mapped[view.k]); launch(view.mapped[view.k]);
  } else if (++beats % 2 === 0) tick();
}
if (!REDUCED) setInterval(beat, 3200);

// ---------- camera moves ----------
let tween = null;
function animateCamera(toPos, ms = 1100) {
  controls.autoRotate = false;
  if (REDUCED) { camera.position.copy(toPos); controls.update(); return; }
  const fromDir = camera.position.clone().normalize(), toDir = toPos.clone().normalize();
  tween = { t0: performance.now(), ms, fromDir, q: new THREE.Quaternion().setFromUnitVectors(fromDir, toDir), fromD: camera.position.length(), toD: toPos.length() };
}
function stepTween(now) {
  if (!tween) return;
  const k = ease(clamp((now - tween.t0) / tween.ms));
  const dir = tween.fromDir.clone().applyQuaternion(new THREE.Quaternion().slerp(tween.q, k));
  const lift = Math.sin(Math.PI * k) * 0.25 * Math.min(1, tween.fromDir.angleTo(dir) + 0.4);
  camera.position.copy(dir.multiplyScalar(THREE.MathUtils.lerp(tween.fromD, tween.toD, k) + lift));
  if (k >= 1) tween = null;
}
const flyTo = (o) => animateCamera(sph(o.lat - 7, o.lon, NARROW() ? 2.6 : 2.3));
$('#zin').addEventListener('click', () => animateCamera(camera.position.clone().multiplyScalar(Math.max(controls.minDistance / camera.position.length(), 0.75)), 450));
$('#zout').addEventListener('click', () => animateCamera(camera.position.clone().multiplyScalar(Math.min(controls.maxDistance / camera.position.length(), 1.33)), 450));
$('#zreset').addEventListener('click', () => { select(null); animateCamera(home()); });

// ---------- hover and click on the globe ----------
const tip = $('#tip');
const hideTip = () => { tip.hidden = true; canvas.style.cursor = ''; };
const tmp = new THREE.Vector3();
function pick(clientX, clientY) {
  const rect = canvas.getBoundingClientRect(), px = clientX - rect.left, py = clientY - rect.top;
  let best = null, bestD = NARROW() ? 24 : 15;
  for (const o of incidents) {
    if (!o.mapped || !o.g.visible) continue;
    if (o.up.dot(tmp.copy(camera.position).sub(o.g.position).normalize()) < 0.02) continue;     // far side of the globe
    tmp.copy(o.g.position).project(camera);
    const d = Math.hypot(px - (tmp.x * 0.5 + 0.5) * rect.width, py - (-tmp.y * 0.5 + 0.5) * rect.height);
    if (d < bestD) { bestD = d; best = o; }
  }
  return best;
}
let downAt = null;
canvas.addEventListener('pointerdown', (e) => { downAt = [e.clientX, e.clientY]; });
canvas.addEventListener('pointermove', (e) => {
  if (e.buttons || e.pointerType === 'touch') return;
  const o = pick(e.clientX, e.clientY);
  if (!o) return hideTip();
  tip.replaceChildren(el('strong', { text: nameOf(o.c) }), el('span', { style: `color:${typeOf(o.c).color}`, text: typeOf(o.c).label }), document.createTextNode(' · ' + ago(o.c.last_seen)));
  const r = $('#stage').getBoundingClientRect();
  tip.style.left = Math.min(e.clientX - r.left + 14, r.width - 290) + 'px';
  tip.style.top = (e.clientY - r.top + 14) + 'px';
  tip.hidden = false; canvas.style.cursor = 'pointer';
});
canvas.addEventListener('pointerleave', hideTip);
canvas.addEventListener('pointerup', (e) => {
  if (!downAt || Math.hypot(e.clientX - downAt[0], e.clientY - downAt[1]) > 6) return;   // that was a drag
  const o = pick(e.clientX, e.clientY);
  if (o) select(o, false);
});

// ---------- filter controls ----------
windowSel.addEventListener('change', refresh);
search.addEventListener('input', refresh);

// ---------- size and render loop ----------
function resize() {
  const r = $('#stage').getBoundingClientRect();
  if (!r.width || !r.height) return;
  renderer.setSize(r.width, r.height, false);
  view.w = r.width; view.h = r.height;
  camera.aspect = r.width / r.height;
  camera.fov = camera.aspect < 0.8 ? 50 : 35;                 // tall, narrow panels get a wider lens
  controls.maxDistance = Math.max(6, homeDistance() * 1.2);
  camera.updateProjectionMatrix();
}
new ResizeObserver(resize).observe($('#stage'));

function frame(now) {
  stepTween(now);
  controls.update();
  const zoom = clamp(camera.position.length() / 3.2, 0.45, 1.3);      // pins shrink as you zoom in so neighbours separate
  for (const o of incidents) {
    if (!o.mapped || !o.g.visible) continue;
    const w = REDUCED ? 0.5 : (now / 1600 + o.phase) % 1;
    const beat = o.rings ? Math.sin(w * Math.PI * 2) : 0;
    o.glow.scale.setScalar(o.glowBase * zoom * (1 + 0.25 * beat));
    o.beam.scale.set(zoom, o.beamH * (1 + 0.12 * beat), zoom);
    if (o.rings) for (const r of o.rings) {
      const k = REDUCED ? 0.4 : (w + r.userData.offset) % 1;
      r.scale.setScalar((1 + k * 4) * zoom); r.material.opacity = REDUCED ? 0.5 : 0.85 * (1 - k);
    }
  }
  if (earth.uniforms && !REDUCED) earth.uniforms.time.value = now / 1000;
  stepStrikes(now);
  if (selRing.visible) selRing.scale.setScalar(zoom * (1 + 0.15 * Math.sin(now / 300)));
  renderer.render(scene, camera);
  requestAnimationFrame(frame);
}

// ---------- data ----------
async function loadData() {
  const data = await (await fetch('data/incidents.json?t=' + Math.floor(Date.now() / 60000), { cache: 'no-store' })).json();
  if (data.updated === updatedAt) { refresh(); return; }            // nothing new; just refresh the "x min ago" labels
  const keep = selected && selected.c.id;
  const firstLoad = !updatedAt, known = new Set(incidents.map(o => o.c.id));
  updatedAt = data.updated; feedErrors = data.feed_errors || [];
  buildPins(data.incidents || []);
  buildLegend(); refresh();
  if (!firstLoad) for (const o of incidents) if (!known.has(o.c.id)) { showTicker(o); launch(o, true); }      // a new report: animate it now
  $('#sources').textContent = (data.sources || []).join(', ');
  $('#asof').textContent = 'Last updated ' + new Date(data.updated).toLocaleString('en-GB', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', timeZone: 'UTC' }) + ' UTC.';
  selected = null;
  const again = keep && incidents.find(x => x.c.id === keep);
  if (again) select(again, false); else if (keep) select(null);
}

(async function boot() {
  try {
    await new Promise(r => (window.topojson ? r() : addEventListener('load', r, { once: true })));
    await buildBorders();                                            // loads the border file the hologram globe is painted from
    await buildEarth();
    await loadData();
    resize();
    camera.position.copy(home()); controls.update();
    if (!REDUCED) {                                                  // opening move: swing in from further out
      const fromDir = HOME_DIR.clone().applyAxisAngle(new THREE.Vector3(0, 1, 0), -1.1);
      camera.position.copy(fromDir).multiplyScalar(homeDistance() * 1.9);
      tween = { t0: performance.now(), ms: 2600, fromDir, q: new THREE.Quaternion().setFromUnitVectors(fromDir, HOME_DIR), fromD: homeDistance() * 1.9, toD: homeDistance() };
    }
    requestAnimationFrame(frame);
    $('#loading').classList.add('done'); setTimeout(() => $('#loading').remove(), 600);
    const m = location.hash.match(/incident=([^&]+)/);
    const o = m && incidents.find(x => x.c.id === decodeURIComponent(m[1]));
    if (o) select(o, true);
    (function poll() {                                               // a failed refresh keeps the last good data on screen
      setTimeout(() => loadData().catch(() => {}).finally(poll), mode === 'realtime' ? 60 * 1000 : REFRESH_MS);
    })();
    window.mapReady = true;
    window.mapDebug = { camera, scene, renderer, controls, frame, select, launch, incidents: () => incidents, strikes: () => strikes };
  } catch (err) {
    $('#loading').textContent = 'The map could not load. ' + err;
    window.mapError = String(err);
  }
})();
