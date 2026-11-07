import { clone, merge, prune, type Dev } from './engine/settings';

export interface Preset { id: string; group: string; name: string; dev: Dev }

export const PRESETS: Preset[] = [
  { id: 'clean-punch', group: 'General', name: 'Clean Punch', dev: { light: { contrast: 14, highlights: -22, shadows: 18, whites: 6, blacks: -6 }, color: { vibrance: 18, saturation: 4 }, effects: { clarity: 12 } } },
  { id: 'soft-film', group: 'Film', name: 'Soft Film', dev: { light: { contrast: -8, highlights: -18, shadows: 22, blacks: 14 }, color: { saturation: -10 }, curve: { master: [[0, 0.05], [0.25, 0.27], [0.75, 0.78], [1, 0.97]] }, grain: { amount: 22, size: 30, roughness: 55 } } },
  { id: 'golden-hour', group: 'Light', name: 'Golden Hour', dev: { wb: { mode: 'custom', temp: 7600, tint: 6 }, light: { exposure: 0.15, highlights: -30, shadows: 20 }, color: { vibrance: 26 }, grading: { highlights: { hue: 48, sat: 28 }, shadows: { hue: 215, sat: 14 } } } },
  { id: 'cool-shade', group: 'Light', name: 'Cool Shade', dev: { wb: { mode: 'custom', temp: 5200, tint: -4 }, light: { contrast: 8, shadows: 12 }, color: { saturation: -6 }, grading: { shadows: { hue: 220, sat: 22 } } } },
  { id: 'teal-amber', group: 'Grade', name: 'Teal and Amber', dev: { light: { contrast: 12 }, color: { vibrance: 12 }, grading: { shadows: { hue: 195, sat: 34, lum: -4 }, highlights: { hue: 38, sat: 30 }, blending: 62, balance: -8 } } },
  { id: 'faded-matte', group: 'Grade', name: 'Faded Matte', dev: { light: { contrast: -14, blacks: 30, whites: -8 }, color: { saturation: -14 }, curve: { master: [[0, 0.09], [1, 0.95]] } } },
  { id: 'deep-sky', group: 'Landscape', name: 'Deep Sky', dev: { light: { highlights: -34, contrast: 10 }, mixer: { blue: { sat: 28, lum: -22 }, aqua: { sat: 18, lum: -14 } }, effects: { clarity: 14, dehaze: 14 } } },
  { id: 'vivid-green', group: 'Landscape', name: 'Vivid Greens', dev: { color: { vibrance: 20 }, mixer: { green: { sat: 32, hue: -12 }, yellow: { sat: 14, hue: -10 } }, effects: { texture: 14 } } },
  { id: 'mono-contrast', group: 'Black and White', name: 'Mono Contrast', dev: { treatment: 'bw', light: { contrast: 28, highlights: -16, shadows: 10, blacks: -14 }, bw: { red: 16, orange: 8, blue: -22 }, effects: { clarity: 18 }, vignette: { amount: -18, midpoint: 48, feather: 60 } } },
  { id: 'mono-soft', group: 'Black and White', name: 'Mono Soft', dev: { treatment: 'bw', light: { contrast: -6, shadows: 16, blacks: 10 }, grain: { amount: 28, size: 35, roughness: 60 } } },
  { id: 'night-lift', group: 'Low Light', name: 'Night Lift', dev: { light: { exposure: 0.45, shadows: 42, blacks: -10, highlights: -20 }, effects: { dehaze: 8, clarity: 10 }, detail: { sharpenAmount: 40 } } },
  { id: 'hazy-clear', group: 'Landscape', name: 'Haze Clear', dev: { effects: { dehaze: 46, clarity: 16 }, light: { contrast: 8, blacks: -10 }, color: { vibrance: 14 } } },
];

export function presetDev(base: Dev, preset: Preset, amount = 1): Dev {
  const over = clone(preset.dev);
  if (amount !== 1) scaleNumbers(over, amount);
  const keepGeo: Dev = {};
  for (const k of ['crop', 'orientation', 'geometry']) if (base[k] !== undefined) keepGeo[k] = base[k];
  return prune(merge(keepGeo, over));
}

function scaleNumbers(o: Dev, k: number): void {
  for (const [key, v] of Object.entries(o)) {
    if (typeof v === 'number' && key !== 'hue' && key !== 'temp' && key !== 'tint') o[key] = v * k;
    else if (v && typeof v === 'object' && !Array.isArray(v)) scaleNumbers(v as Dev, k);
  }
}
