import type { Dev } from '../engine/settings';
import { PRESETS, presetDev } from '../presets';

export interface Collection { id: string; name: string }
export interface Edit { label: string; patch: Dev }
export interface Entry { file: string; pack: string; collection: string; keywords: string[]; rating: number; flag: number; label: string; edits: Edit[] }

export const COLLECTIONS: Collection[] = [
  { id: 'lakes', name: 'Mountain Lakes' },
  { id: 'coast', name: 'Coastlines' },
  { id: 'city', name: 'City After Dark' },
  { id: 'autumn', name: 'Autumn Woods' },
];

const P = (id: string, amount = 1): Edit => {
  const p = PRESETS.find((x) => x.id === id);
  return { label: `Preset: ${p?.name ?? id}`, patch: p ? presetDev({}, p, amount) : {} };
};
const E = (label: string, patch: Dev): Edit => ({ label, patch });

export const PHOTOS: Entry[] = [
  { file: 'lakes-01-walensee.jpg', pack: 'lakes', collection: 'lakes', keywords: ['lake', 'alps', 'sailboat', 'sunset sky'], rating: 5, flag: 1, label: 'green',
    edits: [E('Highlights -38', { light: { highlights: -38 } }), E('Shadows +34', { light: { shadows: 34 } }), E('Vibrance +28', { color: { vibrance: 28 } }),
      E('Color Grading', { grading: { highlights: { hue: 36, sat: 22 }, shadows: { hue: 205, sat: 16 }, blending: 60 } })] },
  { file: 'lakes-02-kolsai.jpg', pack: 'lakes', collection: 'lakes', keywords: ['lake', 'valley', 'spruce'], rating: 4, flag: 1, label: '',
    edits: [P('vivid-green'), E('Clarity +12', { effects: { clarity: 12 } })] },
  { file: 'lakes-03-green-water.jpg', pack: 'lakes', collection: 'lakes', keywords: ['lake', 'turquoise', 'dolomites'], rating: 3, flag: 0, label: '',
    edits: [E('Dehaze +24', { effects: { dehaze: 24 } }), E('Contrast +16', { light: { contrast: 16 } }), E('Vibrance +20', { color: { vibrance: 20 } })] },
  { file: 'lakes-04-braies.jpg', pack: 'lakes', collection: 'lakes', keywords: ['lake', 'reflection', 'boats', 'clouds'], rating: 4, flag: 0, label: 'blue', edits: [] },
  { file: 'lakes-05-lunersee.jpg', pack: 'lakes', collection: 'lakes', keywords: ['lake', 'alpenglow', 'reflection'], rating: 5, flag: 1, label: 'yellow', edits: [] },
  { file: 'lakes-06-misty-lake.jpg', pack: 'lakes', collection: 'lakes', keywords: ['lake', 'mist', 'reflection', 'moody'], rating: 3, flag: 0, label: '',
    edits: [P('clean-punch'), E('Vibrance +18', { color: { vibrance: 18 } })] },
  { file: 'lakes-07-cirque.jpg', pack: 'lakes', collection: 'lakes', keywords: ['tarn', 'cirque', 'snow patches'], rating: 2, flag: -1, label: '', edits: [] },

  { file: 'coast-01-foggy-beach.jpg', pack: 'coast', collection: 'coast', keywords: ['beach', 'fog', 'cliffs', 'footprints'], rating: 5, flag: 1, label: 'red',
    edits: [E('Temperature 7200', { wb: { mode: 'custom', temp: 7200, tint: 4 } }), E('Exposure +0.25', { light: { exposure: 0.25 } }), E('Contrast +14', { light: { contrast: 14 } }),
      E('Color Grading', { grading: { highlights: { hue: 42, sat: 24 }, shadows: { hue: 210, sat: 14 } } })] },
  { file: 'coast-02-long-surf.jpg', pack: 'coast', collection: 'coast', keywords: ['aerial', 'surf', 'beach', 'ocean'], rating: 4, flag: 0, label: '',
    edits: [P('deep-sky'), E('Texture +10', { effects: { texture: 10 } })] },
  { file: 'coast-03-blue-rocks.jpg', pack: 'coast', collection: 'coast', keywords: ['sea', 'rocks', 'horizon'], rating: 3, flag: 0, label: '',
    edits: [P('teal-amber')] },
  { file: 'coast-04-cliff-bay.jpg', pack: 'coast', collection: 'coast', keywords: ['aerial', 'cliff', 'bay', 'turquoise'], rating: 4, flag: 1, label: 'blue', edits: [] },
  { file: 'coast-05-misty-cliffs.jpg', pack: 'coast', collection: 'coast', keywords: ['cliffs', 'mist', 'daybreak', 'black and white'], rating: 5, flag: 1, label: 'purple',
    edits: [P('mono-contrast'), E('Dehaze +14', { effects: { dehaze: 14 } })] },
  { file: 'coast-06-sea-cliff.jpg', pack: 'coast', collection: 'coast', keywords: ['cliff', 'sea', 'clear sky'], rating: 2, flag: 0, label: '',
    edits: [E('Highlights -26', { light: { highlights: -26 } }), E('Blue Saturation +24', { mixer: { blue: { sat: 24, lum: -18 } } })] },

  { file: 'city-01-roundabout.jpg', pack: 'city', collection: 'city', keywords: ['night', 'long exposure', 'light trails', 'street'], rating: 4, flag: 0, label: '', edits: [] },
  { file: 'city-02-hill-town.jpg', pack: 'city', collection: 'city', keywords: ['night', 'rooftops', 'hillside town'], rating: 3, flag: 0, label: '',
    edits: [E('Temperature 5600', { wb: { mode: 'custom', temp: 5600, tint: -6 } }), E('Shadows +22', { light: { shadows: 22 } }), E('Clarity +14', { effects: { clarity: 14 } })] },
  { file: 'city-03-river-towers.jpg', pack: 'city', collection: 'city', keywords: ['night', 'towers', 'river', 'reflection', 'black and white'], rating: 5, flag: 1, label: 'green',
    edits: [P('mono-contrast', 0.9), E('Exposure +0.2', { light: { exposure: 0.2 } })] },
  { file: 'city-04-traffic-streaks.jpg', pack: 'city', collection: 'city', keywords: ['night', 'traffic', 'light trails', 'neon'], rating: 4, flag: 1, label: 'purple',
    edits: [E('Exposure +0.3', { light: { exposure: 0.3 } }), E('Vibrance +22', { color: { vibrance: 22 } }), E('Clarity +12', { effects: { clarity: 12 } })] },
  { file: 'city-05-waterfront.jpg', pack: 'city', collection: 'city', keywords: ['night', 'waterfront', 'reflection', 'panorama'], rating: 3, flag: 0, label: '',
    edits: [P('night-lift')] },
  { file: 'city-06-skyline.jpg', pack: 'city', collection: 'city', keywords: ['night', 'skyline', 'stars', 'reflection'], rating: 2, flag: 0, label: '', edits: [] },

  { file: 'autumn-01-mist-branch.jpg', pack: 'autumn', collection: 'autumn', keywords: ['forest', 'mist', 'red leaves', 'moody'], rating: 5, flag: 1, label: 'red',
    edits: [P('soft-film', 0.8), E('Vibrance +14', { color: { vibrance: 14 } })] },
  { file: 'autumn-02-birch-light.jpg', pack: 'autumn', collection: 'autumn', keywords: ['forest', 'beech', 'sunburst', 'leaf litter'], rating: 4, flag: 1, label: 'yellow',
    edits: [E('Highlights -28', { light: { highlights: -28 } }), E('Orange Saturation +20', { mixer: { orange: { sat: 20 } } }), E('Texture +14', { effects: { texture: 14 } })] },
  { file: 'autumn-03-red-maple.jpg', pack: 'autumn', collection: 'autumn', keywords: ['forest', 'red maple', 'woodland'], rating: 4, flag: 0, label: '',
    edits: [E('Clarity +16', { effects: { clarity: 16 } }), E('Vignette -24', { vignette: { amount: -24, midpoint: 42, feather: 65 } })] },
  { file: 'autumn-04-orange-beech.jpg', pack: 'autumn', collection: 'autumn', keywords: ['forest', 'beech', 'orange leaves'], rating: 3, flag: 0, label: '', edits: [] },
  { file: 'autumn-05-hillside.jpg', pack: 'autumn', collection: 'autumn', keywords: ['aerial', 'hillside', 'mixed forest'], rating: 4, flag: 0, label: '',
    edits: [P('hazy-clear'), E('Vibrance +10', { color: { vibrance: 10 } })] },
  { file: 'autumn-06-tall-trees.jpg', pack: 'autumn', collection: 'autumn', keywords: ['forest', 'tall trees', 'blue sky'], rating: 3, flag: 0, label: '', edits: [P('clean-punch', 0.8)] },
];
