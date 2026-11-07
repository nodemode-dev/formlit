export type Mat3 = number[];

export const D65: [number, number] = [0.3127, 0.3290];
export const MID = 0.18;
export const LOG_MID = Math.log2(MID);
export const LUMA_2020 = [0.2627, 0.6780, 0.0593];

const PRIMARIES: Record<string, { r: [number, number]; g: [number, number]; b: [number, number]; w: [number, number] }> = {
  srgb: { r: [0.64, 0.33], g: [0.3, 0.6], b: [0.15, 0.06], w: D65 },
  rec2020: { r: [0.708, 0.292], g: [0.17, 0.797], b: [0.131, 0.046], w: D65 },
};

const BRADFORD: Mat3 = [0.8951, 0.2664, -0.1614, -0.7502, 1.7135, 0.0367, 0.0389, -0.0685, 1.0296];
const OKLAB_M1: Mat3 = [0.8189330101, 0.3618667424, -0.1288597137, 0.0329845436, 0.9293118715, 0.0361456387, 0.0482003018, 0.2643662691, 0.6338517070];
const OKLAB_M2: Mat3 = [0.2104542553, 0.7936177850, -0.0040720468, 1.9779984951, -2.4285922050, 0.4505937099, 0.0259040371, 0.7827717662, -0.8086757660];

export function mul(a: Mat3, b: Mat3): Mat3 {
  const o = new Array<number>(9).fill(0);
  for (let i = 0; i < 3; i += 1) for (let j = 0; j < 3; j += 1) for (let k = 0; k < 3; k += 1) o[i * 3 + j] += a[i * 3 + k] * b[k * 3 + j];
  return o;
}

export function inv(m: Mat3): Mat3 {
  const [a, b, c, d, e, f, g, h, i] = m;
  const A = e * i - f * h, B = -(d * i - f * g), C = d * h - e * g;
  const det = a * A + b * B + c * C;
  const s = 1 / det;
  return [A * s, -(b * i - c * h) * s, (b * f - c * e) * s, B * s, (a * i - c * g) * s, -(a * f - c * d) * s, C * s, -(a * h - b * g) * s, (a * e - b * d) * s];
}

export function apply(m: Mat3, v: number[]): number[] {
  return [m[0] * v[0] + m[1] * v[1] + m[2] * v[2], m[3] * v[0] + m[4] * v[1] + m[5] * v[2], m[6] * v[0] + m[7] * v[1] + m[8] * v[2]];
}

export const eye = (): Mat3 => [1, 0, 0, 0, 1, 0, 0, 0, 1];
export const isEye = (m: Mat3, tol = 1e-9): boolean => m.every((v, k) => Math.abs(v - eye()[k]) <= tol);

const xyOf = (xy: [number, number]): number[] => [xy[0] / xy[1], 1, (1 - xy[0] - xy[1]) / xy[1]];

export function toXyz(space: string): Mat3 {
  const p = PRIMARIES[space];
  const r = xyOf(p.r), g = xyOf(p.g), b = xyOf(p.b);
  const prim: Mat3 = [r[0], g[0], b[0], r[1], g[1], b[1], r[2], g[2], b[2]];
  const s = apply(inv(prim), xyOf(p.w));
  return [prim[0] * s[0], prim[1] * s[1], prim[2] * s[2], prim[3] * s[0], prim[4] * s[1], prim[5] * s[2], prim[6] * s[0], prim[7] * s[1], prim[8] * s[2]];
}

export const fromXyz = (space: string): Mat3 => inv(toXyz(space));

export function bradford(src: [number, number], dst: [number, number]): Mat3 {
  if (Math.abs(src[0] - dst[0]) <= 1e-12 && Math.abs(src[1] - dst[1]) <= 1e-12) return eye();
  const s = apply(BRADFORD, xyOf(src)), d = apply(BRADFORD, xyOf(dst));
  const cone = [d[0] / s[0], d[1] / s[1], d[2] / s[2]];
  const scale: Mat3 = [cone[0], 0, 0, 0, cone[1], 0, 0, 0, cone[2]];
  return mul(inv(BRADFORD), mul(scale, BRADFORD));
}

export const workingToSrgb: Mat3 = mul(fromXyz('srgb'), mul(bradford(D65, D65), toXyz('rec2020')));
export const srgbToWorking: Mat3 = mul(fromXyz('rec2020'), toXyz('srgb'));

export const LAB_TO_LMS: Mat3 = mul(OKLAB_M1, toXyz('rec2020'));
export const LAB_FROM_LMS: Mat3 = inv(LAB_TO_LMS);
export const LAB_M2 = OKLAB_M2;
export const LAB_I2: Mat3 = inv(OKLAB_M2);

const ROBERTSON: number[][] = [
  [0, 0.18006, 0.26352, -0.24341], [10, 0.18066, 0.26589, -0.25479], [20, 0.18133, 0.26846, -0.26876], [30, 0.18208, 0.27119, -0.28539],
  [40, 0.18293, 0.27407, -0.3047], [50, 0.18388, 0.27709, -0.32675], [60, 0.18494, 0.28021, -0.35156], [70, 0.18611, 0.28342, -0.37915],
  [80, 0.1874, 0.28668, -0.40955], [90, 0.1888, 0.28997, -0.44278], [100, 0.19032, 0.29326, -0.47888], [125, 0.19462, 0.30141, -0.58204],
  [150, 0.19962, 0.30921, -0.70471], [175, 0.20525, 0.31647, -0.84901], [200, 0.21142, 0.32312, -1.0182], [225, 0.21807, 0.32909, -1.2168],
  [250, 0.22511, 0.33439, -1.4512], [275, 0.23247, 0.33904, -1.7298], [300, 0.2401, 0.34308, -2.0637], [325, 0.24792, 0.34655, -2.4681],
  [350, 0.25591, 0.34951, -2.9641], [375, 0.264, 0.352, -3.5814], [400, 0.27218, 0.35407, -4.3633], [425, 0.28039, 0.35577, -5.3762],
  [450, 0.28863, 0.35714, -6.7262], [475, 0.29685, 0.35823, -8.5955], [500, 0.30505, 0.35907, -11.324], [525, 0.3132, 0.35968, -15.628],
  [550, 0.32129, 0.36011, -23.325], [575, 0.32931, 0.36038, -40.77], [600, 0.33724, 0.36051, -116.45],
  [625, 0.34508, 0.36053, 189.78], [650, 0.35281, 0.36044, 57.748], [675, 0.36044, 0.36026, 35.979], [700, 0.36795, 0.36002, 27.095],
];
const TINT_SCALE = 3000;

const ISO = ROBERTSON.map(([r, u, v, t]) => {
  const k = Math.sign(-t || 1) / Math.hypot(1, t);
  return [r, u, v, k, k * t];
});

function between(i: number, f: number): number[] {
  const [r0, u0, v0, du0, dv0] = ISO[i];
  const [r1, u1, v1, du1, dv1] = ISO[i + 1];
  const du = du0 + (du1 - du0) * f, dv = dv0 + (dv1 - dv0) * f;
  const n = Math.hypot(du, dv);
  return [r0 + (r1 - r0) * f, u0 + (u1 - u0) * f, v0 + (v1 - v0) * f, du / n, dv / n];
}

export function tempTintToXy(t: number, tint: number): [number, number] {
  const last = ISO.length - 1;
  const r = t > 0 ? Math.min(1e6 / t, ISO[last][0]) : ISO[last][0];
  let i = 0;
  while (i < last - 1 && ISO[i + 1][0] <= r) i += 1;
  const [r0, u0, v0, du0, dv0] = ISO[i];
  const [r1, u1, v1, du1, dv1] = ISO[i + 1];
  const f = (r - r0) / (r1 - r0);
  const [, lu, lv, du, dv] = between(i, f);
  const nu = -(dv0 + (dv1 - dv0) * f), nv = du0 + (du1 - du0) * f;
  const c = (1 - f) * (v0 * du0 - u0 * dv0) + f * (v1 * du1 - u1 * dv1);
  const a = (c - (nu * lu + nv * lv)) / (nu * nu + nv * nv);
  const s = -tint / TINT_SCALE;
  const U = lu + a * nu + s * du, V = lv + a * nv + s * dv;
  const d = 2 * U - 8 * V + 4;
  return [(3 * U) / d, (2 * V) / d];
}

function wbMatrixXy(xy: [number, number]): Mat3 {
  return mul(fromXyz('rec2020'), mul(bradford(xy, D65), toXyz('rec2020')));
}

export function wbMatrix(temp: number, tint: number, shotTemp: number, shotTint: number): Mat3 | null {
  if (Math.abs(temp - shotTemp) <= 1e-6 && Math.abs(tint - shotTint) <= 1e-6) return null;
  const m = mul(wbMatrixXy(tempTintToXy(temp, tint)), inv(wbMatrixXy(tempTintToXy(shotTemp, shotTint))));
  const y = toXyz('rec2020');
  const rows = [m[0] + m[1] + m[2], m[3] + m[4] + m[5], m[6] + m[7] + m[8]];
  const grey = y[3] * rows[0] + y[4] * rows[1] + y[5] * rows[2];
  return m.map((v) => v / grey);
}

export function srgbEncode(v: number): number {
  const c = v < 0 ? 0 : v > 1 ? 1 : v;
  return c <= 0.0031308 ? c * 12.92 : 1.055 * Math.pow(c, 1 / 2.4) - 0.055;
}

export function srgbDecode(v: number): number {
  const c = v < 0 ? 0 : v > 1 ? 1 : v;
  return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
}

export function hsvHueToOklch(deg: number): number {
  const h6 = (((deg % 360) + 360) % 360) / 60;
  const rgb = [Math.abs(h6 - 3) - 1, 2 - Math.abs(h6 - 2), 2 - Math.abs(h6 - 4)].map((v) => srgbDecode(Math.min(1, Math.max(0, v))));
  const lin = apply(srgbToWorking, rgb);
  const lms = apply(LAB_TO_LMS, lin).map(Math.cbrt);
  const lab = apply(OKLAB_M2, lms);
  return Math.atan2(lab[2], lab[1]);
}
