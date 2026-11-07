import type { Dev } from '../../../demo/src/engine/settings';
import type { Mask, Shape } from './masks/types';

export interface Edit { label: string; patch: Dev }
export interface Entry { file: string; collection: string; keywords: string[]; rating: number; flag: number; label: string; edits: Edit[] }
export interface Collection { id: string; name: string }

export const COLLECTIONS: Collection[] = [
  { id: 'alpine', name: 'Alpine Evening' },
  { id: 'coast', name: 'Coast Walk' },
  { id: 'woods', name: 'Autumn Woods' },
  { id: 'virtual', name: 'Virtual Copies' },
];

const E = (label: string, patch: Dev): Edit => ({ label, patch });
const M = (id: number, name: string, shape: Shape, adjust: Record<string, number>, extra: Partial<Mask> = {}): Mask => ({ id, name, visible: true, components: [{ shape, op: 'add' }], adjust, ...extra });
const MASKS = (label: string, masks: Mask[]): Edit => E(label, { masks });

export const PHOTOS: Entry[] = [
  { file: 'lakes-01-walensee.jpg', collection: 'alpine', keywords: ['lake', 'alps', 'sailboat', 'sunset sky'], rating: 5, flag: 1, label: 'green', edits: [
    E('Highlights -34', { light: { highlights: -34 } }),
    E('Shadows +30', { light: { shadows: 30, whites: 8 } }),
    E('Tone Curve', { curve: { master: [[0, 0], [0.22, 0.18], [0.5, 0.5], [0.78, 0.84], [1, 1]] } }),
    E('Color Mixer', { mixer: { orange: { sat: 18, lum: 8 }, blue: { hue: -8, sat: -8 }, aqua: { sat: -16, lum: -8 } } }),
    E('Color Grading', { grading: { highlights: { hue: 34, sat: 26 }, shadows: { hue: 208, sat: 20 }, midtones: { hue: 22, sat: 6 }, blending: 55, balance: -10 } }),
    MASKS('Masks', [
      M(1, 'Sky', { kind: 'sky', bitmap: 'lakes-01-walensee_sky', refine: 40, shift: 0, feather: 6 }, { exposure: -0.3, highlights: -38, dehaze: 18, saturation: 20, temp: -6 }),
      M(2, 'Foreground Gradient', { kind: 'linear', start: [0.5, 1], end: [0.5, 0.68] }, { exposure: -0.35, shadows: 12, saturation: 8 }),
      M(3, 'Mountain Light', { kind: 'radial', center: [0.2, 0.57], rx: 0.22, ry: 0.13, angle: 0, feather: 70 }, { exposure: 0.3, clarity: 24, texture: 16, temp: 6 }),
    ]),
  ] },
  { file: 'lakes-05-lunersee.jpg', collection: 'alpine', keywords: ['lake', 'alpenglow', 'reflection', 'blue hour'], rating: 5, flag: 1, label: 'yellow', edits: [
    E('Contrast +10', { light: { contrast: 10, highlights: -18, shadows: 16 } }),
    E('Tone Curve', { curve: { master: [[0, 0.02], [0.3, 0.27], [0.7, 0.74], [1, 0.98]] } }),
    E('Color Mixer', { mixer: { blue: { sat: 14, lum: -12 }, orange: { sat: 12 } } }),
    MASKS('Masks', [
      M(1, 'Sky', { kind: 'sky', bitmap: 'lakes-05-lunersee_sky', refine: 30, shift: 0, feather: 4 }, { exposure: -0.2, saturation: 14, dehaze: 10 }),
      M(2, 'Alpenglow', { kind: 'colorRange', samples: [[0.7008, 0.0829, 0.1282]], refine: 62 }, { saturation: 28, exposure: 0.15, temp: 10 }),
    ]),
  ] },
  { file: 'lakes-02-kolsai.jpg', collection: 'alpine', keywords: ['lake', 'valley', 'spruce'], rating: 4, flag: 0, label: '', edits: [
    E('Dehaze +14', { effects: { dehaze: 14 } }),
    E('Greens', { mixer: { green: { sat: 20, hue: -10 }, yellow: { sat: 10 } } }),
    MASKS('Masks', [
      M(1, 'Highlights', { kind: 'luminanceRange', lo: 0.78, hi: 1, loFeather: 0.16, hiFeather: 0.05 }, { exposure: -0.35, highlights: -30 }),
    ]),
  ] },
  { file: 'coast-01-foggy-beach.jpg', collection: 'coast', keywords: ['beach', 'fog', 'cliffs', 'footprints'], rating: 5, flag: 1, label: 'red', edits: [
    E('Temperature 7000', { wb: { mode: 'custom', temp: 7000, tint: 4 } }),
    E('Contrast +12', { light: { contrast: 12 } }),
    E('Color Grading', { grading: { highlights: { hue: 42, sat: 22 }, shadows: { hue: 212, sat: 14 } } }),
    MASKS('Masks', [
      M(1, 'Sky', { kind: 'sky', bitmap: 'coast-01-foggy-beach_sky', refine: 30, shift: 0, feather: 8 }, { exposure: -0.15, temp: -12, tint: 6, saturation: 10 }),
      M(2, 'Sand Glow', { kind: 'radial', center: [0.45, 0.86], rx: 0.4, ry: 0.14, angle: 0, feather: 80 }, { exposure: 0.25, temp: 10, clarity: 14 }),
    ]),
  ] },
  { file: 'coast-03-blue-rocks.jpg', collection: 'coast', keywords: ['sea', 'rocks', 'horizon', 'teal'], rating: 4, flag: 0, label: 'blue', edits: [
    E('Highlights -22', { light: { highlights: -22 } }),
    E('Blue Saturation', { mixer: { aqua: { sat: 16, lum: -10 }, blue: { sat: 10 } } }),
    MASKS('Masks', [
      M(1, 'Sky', { kind: 'sky', bitmap: 'coast-03-blue-rocks_sky', refine: 25, shift: 0, feather: 4 }, { exposure: -0.35, temp: -10, saturation: 16, dehaze: 14 }),
    ]),
  ] },
  { file: 'coast-06-sea-cliff.jpg', collection: 'coast', keywords: ['cliff', 'sea', 'clear sky', 'portrait format'], rating: 3, flag: 0, label: '', edits: [
    E('Clarity +14', { effects: { clarity: 14 } }),
    MASKS('Masks', [
      M(1, 'Sky', { kind: 'sky', bitmap: 'coast-06-sea-cliff_sky', refine: 30, shift: 0, feather: 4 }, { exposure: -0.2, saturation: -10, temp: 8 }),
    ]),
  ] },
  { file: 'autumn-03-red-maple.jpg', collection: 'woods', keywords: ['forest', 'red maple', 'woodland'], rating: 5, flag: 1, label: 'red', edits: [
    E('Highlights -20', { light: { highlights: -20, shadows: 14 } }),
    E('Color Grading', { grading: { shadows: { hue: 190, sat: 16 }, highlights: { hue: 40, sat: 14 }, blending: 60 } }),
    MASKS('Masks', [
      M(1, 'Maple', { kind: 'subject', bitmap: 'autumn-03-red-maple_subject', refine: 55, shift: -6, feather: 8 }, { exposure: 0.3, saturation: 14, clarity: 26, texture: 14 }),
      M(2, 'Background', { kind: 'background', bitmap: 'autumn-03-red-maple_subject', refine: 55, shift: -6, feather: 8 }, { exposure: -0.4, saturation: -14, clarity: -10, temp: -6 }),
    ]),
  ] },
  { file: 'autumn-02-birch-light.jpg', collection: 'woods', keywords: ['forest', 'beech', 'sunburst', 'leaf litter'], rating: 4, flag: 1, label: 'yellow', edits: [
    E('Highlights -28', { light: { highlights: -28 } }),
    E('Orange Saturation', { mixer: { orange: { sat: 18 } } }),
    MASKS('Masks', [
      M(1, 'Edge Burn', { kind: 'radial', center: [0.5, 0.42], rx: 0.46, ry: 0.34, angle: 0, feather: 85, invert: true }, { exposure: -0.55, saturation: -8 }),
    ]),
  ] },
  { file: 'autumn-01-mist-branch.jpg', collection: 'woods', keywords: ['forest', 'mist', 'red leaves', 'moody'], rating: 4, flag: 0, label: 'purple', edits: [
    E('Soft Film', { light: { contrast: -8, shadows: 18, blacks: 12 }, curve: { master: [[0, 0.05], [0.25, 0.27], [0.75, 0.78], [1, 0.97]] }, grain: { amount: 18, size: 30, roughness: 55 } }),
    MASKS('Masks', [
      M(1, 'Top Fade', { kind: 'linear', start: [0.5, 0], end: [0.5, 0.38] }, { exposure: -0.3, dehaze: -12 }),
    ]),
  ] },
];
