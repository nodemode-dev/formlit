import { COLLECTIONS as LIB_COLLECTIONS, PHOTOS as LIB_PHOTOS } from '../../../demo/src/data/library';
import { COLLECTIONS as DEV_COLLECTIONS, PHOTOS as DEV_PHOTOS } from '../../../demos/develop/src/data';
import { COLLECTIONS as SHARE_OUTPUTS, LOCATIONS, MUSIC, OUTPUTS, ROWS } from '../../../demos/share/src/data';

export interface SpecPhoto {
  file: string; collection?: string; keywords: string[]; rating: number; flag: number; label: string;
  edits: Array<{ label: string; patch: Record<string, unknown> }>; gps?: [number, number] | null; meta?: Record<string, string>;
}
export interface DemoSpec {
  id: string; name: string; collections: Array<{ id: string; name: string }>; photos: SpecPhoto[];
  bitmaps?: string[]; music?: string; locations?: typeof LOCATIONS;
  outputs?: Array<{ kind: string; name: string; photos: number[]; settings: Record<string, unknown> }>;
}

const masksOf = (edits: Array<{ patch: Record<string, unknown> }>): string[] => edits.flatMap((e) => (Array.isArray(e.patch.masks) ? e.patch.masks : []) as Array<{ components: Array<{ shape: { bitmap?: string } }> }>)
  .flatMap((m) => m.components.map((c) => c.shape.bitmap).filter((b): b is string => !!b));

export const SPECS: DemoSpec[] = [
  { id: 'library', name: 'formlit Demo Library', collections: LIB_COLLECTIONS, photos: LIB_PHOTOS.map(({ pack: _pack, ...p }) => p) },
  {
    id: 'develop', name: 'formlit Demo Develop', collections: DEV_COLLECTIONS, photos: DEV_PHOTOS,
    bitmaps: [...new Set(DEV_PHOTOS.flatMap((p) => masksOf(p.edits)))],
  },
  {
    id: 'share', name: 'formlit Demo Share', collections: [],
    photos: ROWS.map((r) => ({ file: `${r.slug}.jpg`, keywords: r.keywords, rating: r.rating, flag: r.flag, label: r.label, edits: [], gps: r.gps, meta: { title: r.title, caption: r.caption } })),
    music: MUSIC.file, locations: LOCATIONS,
    outputs: [
      { kind: 'book', name: SHARE_OUTPUTS.book.name, photos: SHARE_OUTPUTS.book.ids, settings: OUTPUTS.book },
      { kind: 'slideshow', name: SHARE_OUTPUTS.slideshow.name, photos: SHARE_OUTPUTS.slideshow.ids, settings: OUTPUTS.slideshow },
      { kind: 'print', name: SHARE_OUTPUTS.print.name, photos: SHARE_OUTPUTS.print.ids, settings: OUTPUTS.print },
      { kind: 'web', name: SHARE_OUTPUTS.web.name, photos: SHARE_OUTPUTS.web.ids, settings: OUTPUTS.web },
    ],
  },
];
