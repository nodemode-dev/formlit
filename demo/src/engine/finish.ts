import {
  LAB_FROM_LMS, LAB_I2, LAB_M2, LAB_TO_LMS, LOG_MID, LUMA_2020, MID, apply, hsvHueToOklch, mul, workingToSrgb, type Mat3,
} from './colour';
import {
  SAT_SLOPE, PIVOT, composite, decLut, encLut, lut1, lutV, parametricLut, pointLut, toneLuts, vAt,
} from './curves';
import { BANDS, get, sectionEnabled, type Dev } from './settings';
import { buildClarity, buildHaze, buildHs, buildTexture, sharpDetail, type Planes } from './planes';

const K1 = 2.3892, K2 = 0.8552;
const HL_K = 0.62, HL_W = 0.6;
const SH_K = 0.9, SH_W = 0.7, SH_MAX = 2.6;
const WH_K = 0.85, WH_W = 0.5;
const BL_K = 0.75, BL_W = 0.6, BL_CLIP = 0.035;
const CON_K = 0.45;
const CLA_K = 1.1, CLA_W = 2.2, CLA_NEG = 0.75;
const TEX_K = 1.6, TEX_POS = 0.35, TEX_NEG = 0.22;
const SHARP_K = 1.6;
const DH_OMEGA = 0.95, DH_TMIN = 0.2, DH_K = 0.7, DH_SAT = 0.9, DH_FLOOR = 0.03;
const HAZE_ADD = [0.25, 0.75, 0.85];
const VIG_STOPS = 2;
const GRAIN_SIGMA = 0.075, GRAIN_REF = 6000;
const E_HL = 0.62, E_SH = 0.35, E_WH = 0.82, E_BL = 0.18, E_MID = 0.5, E_AIR = 0.92;
const GAMUT_TOL = 1e-3;
const VIB_SKIN = 0.6, VIB_NEG = 0.5;
const VIG_PAINT = 0.85, VIG_PROTECT = 0.45;
const VIG_SHAPE = [2, 6, 1.6, 0.9, 0.02];
const GRAIN_MID = [0.25, 3];
const GRAIN_OCT = [0.55, 0.25, 0.75];
const SHARP_CORE = [0.012, 1e-4], SHARP_CLAMP = [0.06, 0.45], SHARP_MASK = [0.004, 0.14];
const C0 = 0.02, HUE_SHIFT = 0.5, LUM_STOPS = 1.25, BW_STOPS = 1.5;
const SKIN_HUE = (58 * Math.PI) / 180, SKIN_WIDTH = (24 * Math.PI) / 180;
const VIB_CHROMA = 0.16;
const CAL_HUE = (18 * Math.PI) / 180, CAL_SAT = 0.6, SHADOW_TINT = 0.35;
const GRADE_TINT = 0.075, GRADE_LUM = 0.12, GRADE_EDGE = 0.18;
const NH = 2048;
const TWO_PI = Math.PI * 2;
const VIG_STYLES: Record<string, number> = { highlightPriority: 0, colorPriority: 1, paintOverlay: 2 };

const smooth = (a: number, b: number, x: number): number => { const t = Math.min(1, Math.max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t); };
const softplus = (z: number): number => (z > 20 ? z : Math.log1p(Math.exp(Math.min(z, 20))));
const wrap = (a: number): number => ((((a + Math.PI) % TWO_PI) + TWO_PI) % TWO_PI) - Math.PI;
const mod = (a: number, n: number): number => ((a % n) + n) % n;

function mantiuk(gam: number, gain: number): number {
  if (gam <= 1e-9) return 0;
  const gp = Math.pow(gam, K2);
  return ((1 + K1) * gp) / (1 + K1 * gp) * gain;
}

let bandCache: { cs: number[]; order: number[]; shifts: number[][] } | null = null;
function bands() {
  if (bandCache) return bandCache;
  const hues = [0, 30, 60, 120, 180, 240, 270, 300];
  const c = hues.map((h) => mod(hsvHueToOklch(h), TWO_PI));
  const order = c.map((_, i) => i).sort((a, b) => c[a] - c[b]);
  const cs = order.map((i) => c[i]);
  const shifts = c.map((ck) => {
    let up = Infinity, down = -Infinity;
    for (const cj of c) {
      const d = mod(cj - ck + Math.PI, TWO_PI) - Math.PI;
      if (d > 1e-6) up = Math.min(up, d);
      if (d < -1e-6) down = Math.max(down, d);
    }
    return [Number.isFinite(up) ? up : 0.5, Number.isFinite(down) ? -down : 0.5];
  });
  bandCache = { cs, order, shifts };
  return bandCache;
}

function segment(h: number): [number, number, number, number] {
  const { cs, order } = bands();
  const n = cs.length;
  const hh = mod(h, TWO_PI);
  let k = -1;
  for (let i = 0; i < n; i += 1) if (cs[i] <= hh) k = i;
  const lo = k < 0 ? cs[n - 1] - TWO_PI : cs[k];
  const hi = k < 0 ? cs[0] : k + 1 < n ? cs[k + 1] : cs[0] + TWO_PI;
  const i0 = order[mod(k, n)], i1 = order[mod(k + 1, n)];
  const t = Math.min(1, Math.max(0, (hh - lo) / Math.max(hi - lo, 1e-9)));
  const w1 = t * t * (3 - 2 * t);
  return [i0, i1, 1 - w1, w1];
}

function hueTable(vals: (i: number) => number): Float32Array {
  const out = new Float32Array(NH + 1);
  for (let k = 0; k <= NH; k += 1) {
    const [i0, i1, w0, w1] = segment((k / NH) * TWO_PI);
    out[k] = w0 * vals(i0) + w1 * vals(i1);
  }
  return out;
}

function wheelDir(deg: number): [number, number] {
  const h = hsvHueToOklch(deg);
  return [Math.cos(h), Math.sin(h)];
}

function rodrigues(theta: number): Mat3 {
  const u = 1 / Math.sqrt(3);
  const k: Mat3 = [0, -u, u, u, 0, -u, -u, u, 0];
  const k2 = mul(k, k);
  const s = Math.sin(theta), c = 1 - Math.cos(theta);
  return [1, 0, 0, 0, 1, 0, 0, 0, 1].map((v, i) => v + s * k[i] + c * k2[i]);
}

function calibrationMatrix(dev: Dev): Mat3 | null {
  if (!sectionEnabled(dev, 'calibration')) return null;
  const vals = ['red', 'green', 'blue'].map((p) => [get(dev, `calibration.${p}Hue`) / 100, get(dev, `calibration.${p}Sat`) / 100]);
  if (!vals.some(([h, s]) => h || s)) return null;
  const cols = vals.map(([h, s], i) => {
    const p = [0, 0, 0]; p[i] = 1;
    const n = LUMA_2020[i];
    const d = apply(rodrigues(h * CAL_HUE), [p[0] - n, p[1] - n, p[2] - n]);
    return d.map((v) => n + (1 + s * CAL_SAT) * v);
  });
  const m = [cols[0][0], cols[1][0], cols[2][0], cols[0][1], cols[1][1], cols[2][1], cols[0][2], cols[1][2], cols[2][2]];
  const out = m.slice();
  for (let r = 0; r < 3; r += 1) {
    const rest = 1 - (m[r * 3] + m[r * 3 + 1] + m[r * 3 + 2]);
    for (let c = 0; c < 3; c += 1) out[r * 3 + c] += rest * LUMA_2020[c];
  }
  return out;
}

export interface Plan {
  w: number; h: number; ev: number;
  tone: { e: Float32Array; g: Float32Array }; satLut: Float32Array; dec: Float32Array; enc: Float32Array;
  vHl: number; vSh: number; vWh: number; vBl: number; vMid: number; air: number;
  con: number; hl: number; sh: number; wh: number; bl: number; tex: number; cla: number; dhz: number; vib: number; sat: number;
  m0: Mat3 | null; stint: number;
  par: { y: Float32Array; d: Float32Array } | null; ccurve: Float32Array[] | null; refine: number;
  mixer: number[][] | null; mixDh: Float32Array; mixDs: Float32Array; mixDl: Float32Array;
  bw: boolean; bwLut: Float32Array;
  grade: number[][] | null; gshape: number[];
  hs?: Float32Array; dc?: Float32Array; dt?: Float32Array; hd?: Float32Array; ds?: Float32Array; edge?: Float32Array;
  sAmt: number; sCore: number; sTcl: number; sMask: number; sThr: number; scale: number;
  vAmt: number; vRound: number; vHlProtect: number; vStyle: number; vPow: number; vInner: number; vOuter: number;
  gAmt: number; gRough: number; gCell: number; gGain: number;
  doLab: boolean; hueMod: boolean; doCurve: boolean;
  mout: Mat3; labOut: Mat3;
}

export function prepare(dev: Dev, lin: Float32Array, planes: Planes, w: number, h: number, ppl: number, fullLong: number): Plan {
  const g = (cid: string): number => get(dev, cid);
  const tone = toneLuts();
  const p = {} as Plan;
  p.w = w; p.h = h;
  p.tone = tone;
  p.satLut = new Float32Array(tone.g.length);
  for (let i = 0; i < tone.g.length; i += 1) p.satLut[i] = mantiuk(tone.g[i], 1);
  p.dec = decLut(); p.enc = encLut();
  p.vHl = vAt(tone.e, E_HL); p.vSh = vAt(tone.e, E_SH); p.vWh = vAt(tone.e, E_WH); p.vBl = vAt(tone.e, E_BL); p.vMid = vAt(tone.e, E_MID);
  const vAir = vAt(tone.e, E_AIR);
  p.ev = g('light.exposure');
  p.con = g('light.contrast') / 100; p.hl = g('light.highlights') / 100; p.sh = g('light.shadows') / 100;
  p.wh = g('light.whites') / 100; p.bl = g('light.blacks') / 100;
  p.tex = g('effects.texture') / 100; p.cla = g('effects.clarity') / 100; p.dhz = g('effects.dehaze') / 100;
  p.vib = g('color.vibrance') / 100; p.sat = g('color.saturation') / 100;
  p.m0 = calibrationMatrix(dev);
  p.stint = sectionEnabled(dev, 'calibration') ? (g('calibration.shadowsTint') / 100) * SHADOW_TINT : 0;
  p.air = MID * 2 ** (vAir - p.ev);

  const curveOn = sectionEnabled(dev, 'curve');
  const crv = (dev.curve && typeof dev.curve === 'object' ? dev.curve : {}) as Record<string, unknown>;
  p.par = curveOn ? parametricLut(crv) : null;
  const luts = ['master', 'red', 'green', 'blue'].map((ch) => (curveOn ? pointLut(crv[ch]) : null));
  p.ccurve = composite(luts[0], luts.slice(1));
  p.doCurve = luts.some((l) => l);
  p.refine = g('curve.refineSaturation') / 100;

  const mixOn = sectionEnabled(dev, 'mixer');
  let mixer: number[][] | null = null;
  if (mixOn) {
    const sh = bands().shifts;
    const tab = BANDS.map((b, k) => {
      const hv = g(`mixer.${b}.hue`) / 100;
      return [hv * HUE_SHIFT * (hv > 0 ? sh[k][0] : sh[k][1]), g(`mixer.${b}.sat`) / 100, (g(`mixer.${b}.lum`) / 100 * LUM_STOPS) / 3];
    });
    if (tab.some((r) => r.some((v) => v !== 0))) mixer = tab;
  }
  p.mixer = mixer;
  p.mixDh = mixer ? hueTable((i) => mixer![i][0]) : new Float32Array(0);
  p.mixDs = mixer ? hueTable((i) => mixer![i][1]) : new Float32Array(0);
  p.mixDl = mixer ? hueTable((i) => mixer![i][2]) : new Float32Array(0);
  p.bw = dev.treatment === 'bw';
  const bwt = BANDS.map((b) => (mixOn ? (g(`bw.${b}`) / 100 * BW_STOPS) / 3 : 0));
  p.bwLut = p.bw ? hueTable((i) => bwt[i]) : new Float32Array(0);

  let grade: number[][] | null = null;
  if (sectionEnabled(dev, 'grading')) {
    const tab = ['shadows', 'midtones', 'highlights', 'global'].map((r) => {
      const sat = g(`grading.${r}.sat`) / 100;
      const [ca, sa] = wheelDir(g(`grading.${r}.hue`));
      return [sat * GRADE_TINT * ca, sat * GRADE_TINT * sa, (g(`grading.${r}.lum`) / 100) * GRADE_LUM];
    });
    if (tab.some((r) => r.some((v) => v !== 0))) grade = tab;
  }
  p.grade = grade;
  const blend = g('grading.blending') / 100, bal = g('grading.balance') / 100;
  p.gshape = [0.36 - 0.22 * bal, 0.7 - 0.22 * bal, 0.05 + 0.32 * blend];

  const detOn = sectionEnabled(dev, 'detail');
  p.scale = Math.min(ppl / Math.max(fullLong, 1), 4);
  p.sAmt = detOn ? g('detail.sharpenAmount') / 100 : 0;
  const sRad = g('detail.sharpenRadius'), sDet = g('detail.sharpenDetail') / 100;
  p.sMask = g('detail.sharpenMasking') / 100;
  p.sCore = SHARP_CORE[0] * (1 - sDet) + SHARP_CORE[1];
  p.sTcl = SHARP_CLAMP[0] + SHARP_CLAMP[1] * sDet;
  p.sThr = SHARP_MASK[0] + SHARP_MASK[1] * p.sMask ** 2;
  const fxOn = sectionEnabled(dev, 'effects');
  p.vAmt = fxOn ? g('vignette.amount') / 100 : 0;
  const midR = 0.3 + (0.9 * g('vignette.midpoint')) / 100;
  p.vRound = g('vignette.roundness') / 100;
  const feather = g('vignette.feather') / 100;
  p.vHlProtect = g('vignette.highlights') / 100;
  p.vStyle = VIG_STYLES[String((dev.vignette as Dev | undefined)?.style ?? 'highlightPriority')] ?? 0;
  p.vPow = VIG_SHAPE[0] + VIG_SHAPE[1] * Math.max(-p.vRound, 0) ** 1.5;
  p.vInner = midR * (1 - VIG_SHAPE[3] * feather);
  p.vOuter = midR + (VIG_SHAPE[2] - midR) * feather + VIG_SHAPE[4];
  p.gAmt = fxOn ? g('grain.amount') / 100 : 0;
  const gSize = g('grain.size') / 100;
  p.gRough = g('grain.roughness') / 100;
  const cell = ((0.7 + 3.2 * gSize ** 1.3) * Math.max(w, h)) / GRAIN_REF;
  p.gCell = Math.max(cell, 1);
  p.gGain = GRAIN_SIGMA * p.gAmt * Math.min(1, cell);

  p.doLab = !!(p.mixer || p.bw || p.grade || p.vib || p.sat);
  p.hueMod = !!(p.mixer && p.mixer.some((r) => r[0] !== 0));
  p.mout = workingToSrgb;
  p.labOut = mul(workingToSrgb, LAB_FROM_LMS);

  const needHs = p.hl !== 0 || p.sh !== 0;
  if (needHs) p.hs = buildHs(planes, lin, w, h, ppl);
  if (p.cla) p.dc = buildClarity(planes, lin, w, h, ppl);
  if (p.tex) p.dt = buildTexture(planes, lin, w, h, ppl);
  if (p.dhz) p.hd = buildHaze(planes, lin, w, h, ppl);
  if (p.sAmt > 0) {
    const sig = Math.max(sRad * p.scale * 0.85, 0);
    if (sig >= 0.12) { const s = sharpDetail(planes, lin, w, h, sig); p.ds = s.d; p.edge = s.edge; } else p.sAmt = 0;
  }
  return p;
}

function hash(ix: number, iy: number): number {
  let x = (Math.imul(ix, 374761393) + Math.imul(iy, 668265263)) | 0;
  x = Math.imul(x ^ (x >>> 13), 1274126177);
  x ^= x >>> 16;
  return (x & 0xffff) * (2 / 65535) - 1;
}

function valueNoise(x: number, y: number, cell: number, seed: number): number {
  const fx = x / cell, fy = y / cell;
  const ix = Math.floor(fx), iy = Math.floor(fy);
  let tx = fx - ix, ty = fy - iy;
  tx = tx * tx * (3 - 2 * tx);
  ty = ty * ty * (3 - 2 * ty);
  const jx = ix + seed, jy = iy - seed;
  const a = hash(jx, jy), b = hash(jx + 1, jy), c = hash(jx, jy + 1), d = hash(jx + 1, jy + 1);
  const top = a + (b - a) * tx;
  return top + (c + (d - c) * tx - top) * ty;
}

export function renderRows(p: Plan, lin: Float32Array, out: Uint8ClampedArray, y0: number, y1: number): void {
  const { w, h } = p;
  const tone = p.tone;
  const lab1 = LAB_TO_LMS, lab2 = LAB_M2, i2 = LAB_I2, i1 = LAB_FROM_LMS;
  const mout = p.mout, labOut = p.labOut;
  const E = p.ev, expGain = 2 ** E;
  const doHs = p.hl !== 0 || p.sh !== 0;
  const doCon = p.con !== 0;
  const gA = 1 - GRAIN_OCT[0] * p.gRough, gB = GRAIN_OCT[1] + GRAIN_OCT[2] * p.gRough;
  const gK = 1 / (Math.sqrt(gA * gA + gB * gB) * 0.5);
  const Wd = Math.max(w, 1), Hd = Math.max(h, 1), Lmax = Math.max(Wd, Hd);
  const ct = Math.min(0.9, Math.max(-0.9, p.con * CON_K));
  const cosw = Math.cos, sinw = Math.sin;
  const m0 = p.m0;
  const gt = p.grade;
  const [gts, gtm, gth, gtg] = gt ?? [[0, 0, 0], [0, 0, 0], [0, 0, 0], [0, 0, 0]];
  const [tS, tH, wD] = p.gshape;
  const oa = new Float64Array(3);

  for (let y = y0; y < y1; y += 1) {
    for (let x = 0; x < w; x += 1) {
      const i = y * w + x;
      const j = i * 3;
      let r = Math.max(lin[j], 0), gg = Math.max(lin[j + 1], 0), b = Math.max(lin[j + 2], 0);

      if (p.dhz) {
        const D = p.dhz;
        const air = p.air;
        const t = Math.min(1, Math.max(DH_TMIN, 1 - (DH_OMEGA * p.hd![i]) / air));
        if (D > 0) {
          const tt = Math.max(1 - D * DH_K * (1 - t), DH_TMIN);
          const Y0 = Math.max(r * LUMA_2020[0] + gg * LUMA_2020[1] + b * LUMA_2020[2], 1e-12);
          const yj = Math.max(air + (Y0 - air) / tt, Y0 * DH_FLOOR);
          const sd = 1 + DH_SAT * D * (1 - t);
          const k = yj / Y0;
          r = Math.max(k * (Y0 + sd * (r - Y0)), 0);
          gg = Math.max(k * (Y0 + sd * (gg - Y0)), 0);
          b = Math.max(k * (Y0 + sd * (b - Y0)), 0);
        } else {
          const hz = Math.min(-D * (HAZE_ADD[0] + HAZE_ADD[1] * (1 - t)) * HAZE_ADD[2], 0.95);
          r += hz * (air - r); gg += hz * (air - gg); b += hz * (air - b);
        }
      }
      if (m0) {
        const nr = m0[0] * r + m0[1] * gg + m0[2] * b, ng = m0[3] * r + m0[4] * gg + m0[5] * b, nb = m0[6] * r + m0[7] * gg + m0[8] * b;
        r = Math.max(nr, 0); gg = Math.max(ng, 0); b = Math.max(nb, 0);
      }
      r *= expGain; gg *= expGain; b *= expGain;
      if (p.stint) {
        const Yt = r * LUMA_2020[0] + gg * LUMA_2020[1] + b * LUMA_2020[2];
        const vt = Math.log2(Math.max(Yt, 1e-12)) - LOG_MID;
        const wt = p.stint * (1 - smooth(-5, -1, vt));
        const r2 = r * 2 ** wt, g2 = gg * 2 ** (-0.5 * wt), b2 = b * 2 ** wt;
        const k = Yt / Math.max(r2 * LUMA_2020[0] + g2 * LUMA_2020[1] + b2 * LUMA_2020[2], 1e-12);
        r = r2 * k; gg = g2 * k; b = b2 * k;
      }
      const Y = r * LUMA_2020[0] + gg * LUMA_2020[1] + b * LUMA_2020[2];
      const Yc = Math.max(Y, 1e-12);
      const lg = Math.log2(Yc);
      let delta = 0;
      if (doHs) {
        const ub = p.hs![i] + E - LOG_MID;
        if (p.hl) delta += p.hl * HL_K * HL_W * softplus((ub - p.vHl) / HL_W);
        if (p.sh) {
          const gsh = SH_W * softplus((p.vSh - ub) / SH_W);
          delta += p.sh * SH_MAX * Math.tanh((SH_K * gsh) / SH_MAX);
        }
      }
      if (p.cla) {
        const ub = lg - LOG_MID;
        const mw = Math.exp(-0.5 * ((ub - p.vMid) / CLA_W) ** 2);
        delta += (p.cla > 0 ? p.cla * CLA_K : p.cla * CLA_NEG) * mw * p.dc![i];
      }
      if (p.tex) {
        const dt = p.dt![i];
        const r2 = dt * dt;
        delta += (p.tex > 0 ? p.tex * TEX_K * Math.exp((r2 * -0.5) / TEX_POS ** 2) : p.tex * Math.exp((r2 * -0.5) / TEX_NEG ** 2)) * dt;
      }
      if (p.sAmt > 0 && p.ds) {
        const d = p.ds[i];
        let dd = d * ((d * d) / (d * d + p.sCore * p.sCore));
        dd /= Math.sqrt(1 + (dd / p.sTcl) ** 2);
        if (p.sMask > 0) dd *= smooth(0.5 * p.sThr, 1.5 * p.sThr, p.edge![i] * p.scale);
        delta += p.sAmt * SHARP_K * dd;
      }
      let v = lg + delta - LOG_MID;
      if (p.wh) v += p.wh * WH_K * WH_W * softplus((v - p.vWh) / WH_W);
      let blk = 0;
      if (p.bl) {
        v += p.bl * BL_K * BL_W * softplus((p.vBl - v) / BL_W);
        blk = Math.max(-p.bl, 0) * BL_CLIP;
      }
      let e = lutV(v, tone.e);
      let gam = lutV(v, tone.g);
      if (blk) e = Math.max(e - blk, 0) / (1 - blk);
      if (doCon || p.par) {
        let fs = 1;
        if (doCon) {
          const lo = e < PIVOT;
          const u = lo ? e / PIVOT : (e - PIVOT) / (1 - PIVOT);
          const wv = (lo ? PIVOT : 1 - PIVOT) / Math.PI;
          const uc = Math.min(1, Math.max(0, u));
          const s = sinw(Math.PI * uc), c = cosw(Math.PI * uc);
          if (e >= 0 && e <= 1) {
            const e1 = lo ? e - ct * wv * s : e + ct * wv * s;
            const ds = lo ? 1 - ct * c : 1 + ct * c;
            fs *= (ds * (e + 0.055)) / (e1 + 0.055);
            e = e1;
          }
        }
        if (p.par) {
          const e1 = lut1(e, p.par.y);
          fs *= (lut1(e, p.par.d) * (e + 0.055)) / (e1 + 0.055);
          e = e1;
        }
        gam *= Math.min(SAT_SLOPE[1], Math.max(SAT_SLOPE[0], fs));
      }
      const Yd = lut1(e, p.dec);
      const s = doCon || p.par ? mantiuk(gam, 1) : lutV(v, p.satLut);
      let R = Yd * (1 + s * (r / Yc - 1)), G = Yd * (1 + s * (gg / Yc - 1)), B = Yd * (1 + s * (b / Yc - 1));

      if (p.doLab) {
        const l0 = Math.cbrt(lab1[0] * R + lab1[1] * G + lab1[2] * B), m_ = Math.cbrt(lab1[3] * R + lab1[4] * G + lab1[5] * B), s_ = Math.cbrt(lab1[6] * R + lab1[7] * G + lab1[8] * B);
        let L = lab2[0] * l0 + lab2[1] * m_ + lab2[2] * s_;
        let a = lab2[3] * l0 + lab2[4] * m_ + lab2[5] * s_;
        let bb = lab2[6] * l0 + lab2[7] * m_ + lab2[8] * s_;
        let C = Math.sqrt(a * a + bb * bb);
        let hh = Math.atan2(bb, a);
        const Cin = C;
        if (p.mixer) {
          const cw = (C * C) / (C * C + C0 * C0);
          const t = mod(hh, TWO_PI) / TWO_PI;
          hh += lut1(t, p.mixDh);
          C *= Math.max(1 + lut1(t, p.mixDs), 0);
          L *= 2 ** (lut1(t, p.mixDl) * cw);
        }
        if (p.vib) {
          let vw = 1 - smooth(0, VIB_CHROMA, C);
          if (p.vib > 0) {
            const skin = Math.exp(-0.5 * (wrap(hh - SKIN_HUE) / SKIN_WIDTH) ** 2);
            vw *= 1 - VIB_SKIN * skin;
            C *= 1 + p.vib * vw;
          } else C *= 1 + p.vib * (1 - VIB_NEG * smooth(0, VIB_CHROMA, C));
        }
        if (p.sat) C *= Math.max(1 + p.sat, 0);
        if (p.bw) {
          const cw = (C * C) / (C * C + C0 * C0);
          L *= 2 ** (lut1(mod(hh, TWO_PI) / TWO_PI, p.bwLut) * cw);
          C = 0;
        }
        if (p.hueMod) { a = C * Math.cos(hh); bb = C * Math.sin(hh); } else {
          const k = Cin > 1e-12 ? C / Math.max(Cin, 1e-12) : 0;
          a *= k; bb *= k;
        }
        if (gt) {
          const env = Math.min(1, Math.max(0, L / GRADE_EDGE)) * Math.min(1, Math.max(0, (1 - L) / GRADE_EDGE));
          const ws = 1 - smooth(tS - wD, tS + wD, L);
          const wh = smooth(tH - wD, tH + wD, L);
          const wm = Math.max(1 - ws - wh, 0);
          a += env * (ws * gts[0] + wm * gtm[0] + wh * gth[0] + gtg[0]);
          bb += env * (ws * gts[1] + wm * gtm[1] + wh * gth[1] + gtg[1]);
          L += ws * gts[2] + wm * gtm[2] + wh * gth[2] + gtg[2];
        }
        const q0 = i2[0] * L + i2[1] * a + i2[2] * bb, q1 = i2[3] * L + i2[4] * a + i2[5] * bb, q2 = i2[6] * L + i2[7] * a + i2[8] * bb;
        const c0 = q0 * q0 * q0, c1 = q1 * q1 * q1, c2 = q2 * q2 * q2;
        R = i1[0] * c0 + i1[1] * c1 + i1[2] * c2;
        G = i1[3] * c0 + i1[4] * c1 + i1[5] * c2;
        B = i1[6] * c0 + i1[7] * c1 + i1[8] * c2;
      }
      if (p.doCurve && p.ccurve) {
        const bR = R, bG = G, bB = B;
        const cc = p.ccurve;
        const ap = (x: number, lut: Float32Array): number => { const xc = Math.min(1, Math.max(0, x)); return lut1(Math.sqrt(Math.sqrt(xc)), lut) + (x - xc); };
        R = ap(R, cc[0]); G = ap(G, cc[1]); B = ap(B, cc[2]);
        if (p.refine < 1) {
          const lab = (rr: number, g2: number, b2: number): [number, number, number] => {
            const a0 = Math.cbrt(lab1[0] * rr + lab1[1] * g2 + lab1[2] * b2), a1 = Math.cbrt(lab1[3] * rr + lab1[4] * g2 + lab1[5] * b2), a2 = Math.cbrt(lab1[6] * rr + lab1[7] * g2 + lab1[8] * b2);
            return [lab2[0] * a0 + lab2[1] * a1 + lab2[2] * a2, lab2[3] * a0 + lab2[4] * a1 + lab2[5] * a2, lab2[6] * a0 + lab2[7] * a1 + lab2[8] * a2];
          };
          const la = lab(R, G, B), lb = lab(bR, bG, bB);
          const ca = Math.hypot(la[1], la[2]), cb = Math.hypot(lb[1], lb[2]);
          const k = ca > 1e-9 ? (cb + p.refine * (ca - cb)) / Math.max(ca, 1e-9) : 1;
          const L = la[0], a = la[1] * k, bb = la[2] * k;
          const q0 = i2[0] * L + i2[1] * a + i2[2] * bb, q1 = i2[3] * L + i2[4] * a + i2[5] * bb, q2 = i2[6] * L + i2[7] * a + i2[8] * bb;
          const c0 = q0 * q0 * q0, c1 = q1 * q1 * q1, c2 = q2 * q2 * q2;
          R = i1[0] * c0 + i1[1] * c1 + i1[2] * c2;
          G = i1[3] * c0 + i1[4] * c1 + i1[5] * c2;
          B = i1[6] * c0 + i1[7] * c1 + i1[8] * c2;
        }
      }
      let o0 = mout[0] * R + mout[1] * G + mout[2] * B;
      let o1 = mout[3] * R + mout[4] * G + mout[5] * B;
      let o2 = mout[6] * R + mout[7] * G + mout[8] * B;
      const bad = o0 < -GAMUT_TOL || o0 > 1 + GAMUT_TOL || o1 < -GAMUT_TOL || o1 > 1 + GAMUT_TOL || o2 < -GAMUT_TOL || o2 > 1 + GAMUT_TOL;
      if (bad) {
        const l0 = Math.cbrt(lab1[0] * R + lab1[1] * G + lab1[2] * B), m_ = Math.cbrt(lab1[3] * R + lab1[4] * G + lab1[5] * B), s_ = Math.cbrt(lab1[6] * R + lab1[7] * G + lab1[8] * B);
        const L = lab2[0] * l0 + lab2[1] * m_ + lab2[2] * s_, a = lab2[3] * l0 + lab2[4] * m_ + lab2[5] * s_, bb = lab2[6] * l0 + lab2[7] * m_ + lab2[8] * s_;
        const Lc = Math.min(1, Math.max(0, L));
        const inGamut = (t: number): boolean => {
          const y0_ = i2[0] * Lc + i2[1] * a * t + i2[2] * bb * t, y1_ = i2[3] * Lc + i2[4] * a * t + i2[5] * bb * t, y2_ = i2[6] * Lc + i2[7] * a * t + i2[8] * bb * t;
          const c0 = y0_ * y0_ * y0_, c1 = y1_ * y1_ * y1_, c2 = y2_ * y2_ * y2_;
          oa[0] = labOut[0] * c0 + labOut[1] * c1 + labOut[2] * c2;
          oa[1] = labOut[3] * c0 + labOut[4] * c1 + labOut[5] * c2;
          oa[2] = labOut[6] * c0 + labOut[7] * c1 + labOut[8] * c2;
          return oa[0] >= -GAMUT_TOL && oa[0] <= 1 + GAMUT_TOL && oa[1] >= -GAMUT_TOL && oa[1] <= 1 + GAMUT_TOL && oa[2] >= -GAMUT_TOL && oa[2] <= 1 + GAMUT_TOL;
        };
        let t = 1;
        if (!inGamut(1)) {
          let lo = 0, hi = 1;
          for (let it = 0; it < 22; it += 1) { const mid = (lo + hi) / 2; if (inGamut(mid)) lo = mid; else hi = mid; }
          t = Math.max(lo, 1e-6);
        }
        inGamut(t);
        if (L >= 1) { o0 = 1; o1 = 1; o2 = 1; } else if (L <= 0) { o0 = 0; o1 = 0; o2 = 0; } else {
          o0 = Math.min(1, Math.max(0, oa[0])); o1 = Math.min(1, Math.max(0, oa[1])); o2 = Math.min(1, Math.max(0, oa[2]));
        }
      } else {
        o0 = Math.min(1, Math.max(0, o0)); o1 = Math.min(1, Math.max(0, o1)); o2 = Math.min(1, Math.max(0, o2));
      }
      let e0 = lut1(Math.sqrt(Math.sqrt(o0)), p.enc), e1 = lut1(Math.sqrt(Math.sqrt(o1)), p.enc), e2 = lut1(Math.sqrt(Math.sqrt(o2)), p.enc);

      if (p.vAmt) {
        let X = (x + 0.5) / Wd * 2 - 1, Yv = (y + 0.5) / Hd * 2 - 1;
        if (p.vRound > 0) { X *= 1 + (Wd / Lmax - 1) * p.vRound; Yv *= 1 + (Hd / Lmax - 1) * p.vRound; }
        const pw = p.vPow;
        const d = Math.pow(Math.pow(Math.abs(X) + 1e-9, pw) + Math.pow(Math.abs(Yv) + 1e-9, pw), 1 / pw);
        const wv = smooth(p.vInner, p.vOuter, d);
        const amt = p.vAmt;
        if (p.vStyle === 2) {
          const target = amt < 0 ? 0 : 1;
          const k = wv * Math.abs(amt) * VIG_PAINT;
          e0 += k * (target - e0); e1 += k * (target - e1); e2 += k * (target - e2);
        } else if (wv > 0) {
          const dec = p.dec;
          let l0 = lut1(Math.min(1, Math.max(0, e0)), dec), l1 = lut1(Math.min(1, Math.max(0, e1)), dec), l2 = lut1(Math.min(1, Math.max(0, e2)), dec);
          let gain = 2 ** (amt * VIG_STOPS * wv);
          if (amt < 0) {
            if (p.vHlProtect > 0) {
              const lum = Math.max(e0, e1, e2);
              gain += (1 - gain) * p.vHlProtect * smooth(VIG_PROTECT, 1, lum);
            }
            l0 *= gain; l1 *= gain; l2 *= gain;
          } else if (p.vStyle === 0) {
            l0 = (l0 * gain) / (1 + (gain - 1) * l0); l1 = (l1 * gain) / (1 + (gain - 1) * l1); l2 = (l2 * gain) / (1 + (gain - 1) * l2);
          } else {
            l0 *= gain; l1 *= gain; l2 *= gain;
            const mx = Math.max(l0, l1, l2, 1);
            l0 /= mx; l1 /= mx; l2 /= mx;
          }
          const enc = p.enc;
          e0 = lut1(Math.sqrt(Math.sqrt(Math.min(1, Math.max(0, l0)))), enc);
          e1 = lut1(Math.sqrt(Math.sqrt(Math.min(1, Math.max(0, l1)))), enc);
          e2 = lut1(Math.sqrt(Math.sqrt(Math.min(1, Math.max(0, l2)))), enc);
        }
      }
      if (p.gAmt > 0) {
        const n = (valueNoise(x, y, p.gCell, 17) * gA + valueNoise(x, y, p.gCell * 0.5, 91) * gB) * gK;
        const lum = e0 * 0.2126 + e1 * 0.7152 + e2 * 0.0722;
        const add = p.gGain * n * (GRAIN_MID[0] + GRAIN_MID[1] * lum * (1 - lum));
        e0 += add; e1 += add; e2 += add;
      }
      const o = i * 4;
      out[o] = e0 * 255;
      out[o + 1] = e1 * 255;
      out[o + 2] = e2 * 255;
      out[o + 3] = 255;
    }
  }
}
