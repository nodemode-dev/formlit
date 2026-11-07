export function boxBlur(src: Float32Array, w: number, h: number, r: number): Float32Array {
  if (r < 1) return src;
  const tmp = new Float32Array(src.length);
  const out = new Float32Array(src.length);
  const k = 1 / (2 * r + 1);
  for (let y = 0; y < h; y += 1) {
    const o = y * w;
    let acc = 0;
    for (let x = -r; x <= r; x += 1) acc += src[o + Math.min(w - 1, Math.max(0, x))];
    for (let x = 0; x < w; x += 1) {
      tmp[o + x] = acc * k;
      acc += src[o + Math.min(w - 1, x + r + 1)] - src[o + Math.max(0, x - r)];
    }
  }
  for (let x = 0; x < w; x += 1) {
    let acc = 0;
    for (let y = -r; y <= r; y += 1) acc += tmp[Math.min(h - 1, Math.max(0, y)) * w + x];
    for (let y = 0; y < h; y += 1) {
      out[y * w + x] = acc * k;
      acc += tmp[Math.min(h - 1, y + r + 1) * w + x] - tmp[Math.max(0, y - r) * w + x];
    }
  }
  return out;
}

export function gauss(src: Float32Array, w: number, h: number, sigma: number): Float32Array {
  if (sigma < 0.4) return src;
  const r = Math.max(1, Math.round(Math.sqrt((12 * sigma * sigma) / 3 + 1) / 2));
  let cur = src;
  for (let i = 0; i < 3; i += 1) cur = boxBlur(cur, w, h, r);
  return cur;
}

export function guided(guide: Float32Array, p: Float32Array, w: number, h: number, r: number, eps: number): Float32Array {
  const n = w * h;
  const mi = boxBlur(guide, w, h, r), mp = boxBlur(p, w, h, r);
  const ii = new Float32Array(n), ip = new Float32Array(n);
  for (let i = 0; i < n; i += 1) { ii[i] = guide[i] * guide[i]; ip[i] = guide[i] * p[i]; }
  const mii = boxBlur(ii, w, h, r), mip = boxBlur(ip, w, h, r);
  const a = new Float32Array(n), b = new Float32Array(n);
  for (let i = 0; i < n; i += 1) {
    const v = Math.max(0, mii[i] - mi[i] * mi[i]);
    const c = mip[i] - mi[i] * mp[i];
    a[i] = c / (v + eps);
    b[i] = mp[i] - a[i] * mi[i];
  }
  const ma = boxBlur(a, w, h, r), mb = boxBlur(b, w, h, r);
  const out = new Float32Array(n);
  for (let i = 0; i < n; i += 1) out[i] = Math.min(1, Math.max(0, ma[i] * guide[i] + mb[i]));
  return out;
}

export function morph(src: Float32Array, w: number, h: number, r: number, grow: boolean): Float32Array {
  if (r < 1) return src;
  const tmp = new Float32Array(src.length);
  const out = new Float32Array(src.length);
  const pick = grow ? Math.max : Math.min;
  const init = grow ? 0 : 1;
  for (let y = 0; y < h; y += 1) {
    const o = y * w;
    for (let x = 0; x < w; x += 1) {
      let v = init;
      for (let k = Math.max(0, x - r); k <= Math.min(w - 1, x + r); k += 1) v = pick(v, src[o + k]);
      tmp[o + x] = v;
    }
  }
  for (let x = 0; x < w; x += 1) {
    for (let y = 0; y < h; y += 1) {
      let v = init;
      for (let k = Math.max(0, y - r); k <= Math.min(h - 1, y + r); k += 1) v = pick(v, tmp[k * w + x]);
      out[y * w + x] = v;
    }
  }
  return out;
}

export const smooth = (t: number): number => {
  const c = t < 0 ? 0 : t > 1 ? 1 : t;
  return c * c * (3 - 2 * c);
};
