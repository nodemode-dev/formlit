export interface Row {
  slug: string;
  pack: string;
  title: string;
  caption: string;
  who: string;
  camera: string;
  focal: number | null;
  aperture: number | null;
  iso: number | null;
  shutter: number | null;
  date: string | null;
  gps: [number, number] | null;
  keywords: string[];
  rating: number;
  flag: number;
  label: string;
}

const R = (slug: string, pack: string, title: string, caption: string, who: string, camera: string, focal: number | null, aperture: number | null, iso: number | null, shutter: number | null, date: string | null, gps: [number, number] | null, keywords: string[], rating: number, flag: number, label = ''): Row =>
  ({ slug, pack, title, caption, who, camera, focal, aperture, iso, shutter, date, gps, keywords, rating, flag, label });

export const ROWS: Row[] = [
  R('alps-01-walensee', 'alps', 'Walensee', 'Sailing on Walensee, Switzerland', 'Paolo Bici', 'X-E5', 23, 8, 500, 1 / 1700, '2026-04-27', [47.1167, 9.2], ['Lake', 'Mountains', 'Switzerland'], 4, 1, 'blue'),
  R('alps-02-lunersee', 'alps', 'Lunersee', 'Lunersee in the Raetikon Alps, Austria', 'David Waschbüsch', 'Canon EOS 600D', 18, 5.6, 100, 1 / 100, '2022-08-03', [47.0536, 9.7642], ['Lake', 'Mountains', 'Austria'], 5, 1, 'green'),
  R('alps-03-braies', 'alps', 'Lago di Braies', 'Lago di Braies in the Dolomites, Italy', 'Sara Rubini', 'Redmi Note 8T', 4.74, 1.8, 160, 1 / 2662, '2021-08-05', [46.6945, 12.085], ['Lake', 'Mountains', 'Italy'], 4, 0),
  R('alps-04-hallstatt', 'alps', 'Hallstatt', 'Lakeside village of Hallstatt, Austria', 'Ahmet Yüksek', 'FC8482', 6.72, 1.7, 120, 1 / 15, '2025-07-05', [47.5622, 13.6493], ['Village', 'Lake', 'Austria'], 3, 0),
  R('alps-05-bled', 'alps', 'Lake Bled', 'Lake Bled and its island church, Slovenia', 'Jon Eliya', '', null, null, null, null, null, [46.3639, 14.0938], ['Lake', 'Aerial', 'Slovenia'], 4, 1, 'yellow'),
  R('world-01-reine', 'world', 'Reine', 'Reine in the Lofoten Islands, Norway', 'op23', 'X-T30', 34.3, 8, 200, 1 / 320, '2021-09-02', [67.9328, 13.0889], ['Village', 'Coast', 'Norway'], 5, 1, 'green'),
  R('world-02-kirkjufell', 'world', 'Kirkjufell', 'Kirkjufell and its waterfall, Iceland', 'Lorenzo Castellino', 'ILCE-7RM4A', 28, 7.1, 200, 10, '2026-07-15', [64.9419, -23.3067], ['Waterfall', 'Mountains', 'Iceland'], 5, 1, 'purple'),
  R('world-03-santorini', 'world', 'Santorini', 'White houses of Santorini, Greece', 'Ayoub SOUSSI', '', null, null, null, null, null, [36.3932, 25.4615], ['Village', 'Coast', 'Greece'], 3, 0),
  R('world-04-rila', 'world', 'Rila Lakes', 'Rila Lakes, Bulgaria', 'Bob Krustev', 'Canon EOS 600D', 10, 10, 100, 1 / 160, '2014-08-02', [42.15, 23.35], ['Lake', 'Mountains', 'Bulgaria'], 3, 0),
  R('world-05-kolsai', 'world', 'Kolsai Lakes', 'Kolsai Lakes, Kazakhstan', 'Necip Duman', 'Canon EOS R6m2', 39, 4, 100, 1 / 320, '2026-05-23', [42.9917, 78.3275], ['Lake', 'Mountains', 'Kazakhstan'], 4, 0),
  R('world-06-milford', 'world', 'Milford Sound', 'Waterfalls of Milford Sound, New Zealand', 'Ling Xu', 'iPhone 16 Pro Max', 6.76, 1.8, 100, 1 / 580, '2025-06-19', [-44.671, 167.93], ['Waterfall', 'Fjord', 'New Zealand'], 4, 1, 'blue'),
  R('world-07-austin', 'world', 'Austin', 'Skyscrapers by the river in Austin, Texas', 'Elsie Soto', 'Canon EOS R', 35, 2.8, 3200, 1 / 60, '2021-11-12', [30.2672, -97.7431], ['City', 'Night', 'Texas'], 2, 0),
  R('world-08-mexico-city', 'world', 'Mexico City', 'Traffic in motion, Mexico City', 'Famitsay Tamayo', 'NIKON Z 6', 30, 20, 80, 15, '2021-09-30', [19.4326, -99.1332], ['City', 'Night', 'Mexico'], 3, 0),
  R('more-01-boats', 'more', 'Mountain Lake', 'A lake among green trees and snowy peaks', 'Markus Spiske', 'Canon EOS 5D Mark III', 24, 9, 160, 1 / 100, '2016-08-10', null, ['Lake', 'Mountains'], 3, 0),
  R('more-02-tarn', 'more', 'Mountain Stream', 'A stream in a mountain valley', 'Hristofor Stoyanov', 'NIKON D7000', 17, 5, 250, 1 / 200, '2023-07-29', null, ['Stream', 'Mountains'], 2, 0),
  R('more-03-surf', 'more', 'Coastline', 'Surf along a pristine coastline', 'Laszlo Magyar', 'ILCE-6700', 54, 2.2, 100, 1 / 4000, '2026-05-13', null, ['Coast', 'Aerial'], 4, 0),
  R('more-04-misty-cliffs', 'more', 'Misty Cliffs', 'Misty coastal cliffs at daybreak', 'Sandra', 'NIKON D5300', 55, 19, 100, 1 / 180, '2025-10-24', null, ['Coast', 'Mist'], 4, 1, 'yellow'),
  R('more-05-autumn-mist', 'more', 'Autumn Mist', 'Misty autumn forest with colourful foliage', 'Adrian Limani', 'NIKON D7000', 55, 7.1, 500, 1 / 125, '2025-11-08', null, ['Forest', 'Mist'], 3, 0),
  R('more-06-roundabout', 'more', 'Roundabout', 'Light trails around a roundabout at night', 'Oleksiy', 'NIKON Df', 50, 16, 100, 30, '2025-04-07', null, ['City', 'Night'], 2, 0),
];

export const MUSIC = { pack: 'music', file: 'piano-fantasia.ogg', folder: 'Demo Music', title: 'Piano Fantasia No. 1 (Peter Bille Larsen)' };

export const LOCATIONS = [
  { name: 'Alpine Lakes', lat: 47.0, lon: 11.2, radius: 330, private: false },
  { name: 'Home Studio', lat: 30.2672, lon: -97.7431, radius: 15, private: true },
];

export const COLLECTIONS = {
  book: { name: 'Lakes and Peaks', ids: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12] },
  slideshow: { name: 'Alpine and Nordic', ids: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10] },
  print: { name: 'Four Up Prints', ids: [1, 2, 4, 6] },
  web: { name: 'Lakes and Peaks Gallery', ids: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13] },
};

export const OUTPUTS = {
  book: {
    size: 'standard-landscape', background: '#f4efe6', textColor: '#3a3128', captions: true, captionField: 'titleCaption', pageNumbers: true,
    coverTexts: ['Lakes and Peaks', 'Photographs from the Alps and beyond'],
  },
  slideshow: {
    background: '#0d0d0f', fill: false, margin: 0.06, shadow: true, panZoom: 0.45, duration: 4, fade: 1.5, repeat: true,
    intro: { on: true, text: 'Alpine and Nordic', seconds: 3 }, ending: { on: true, text: 'Thank you for watching', seconds: 3 },
    caption: { on: true, field: 'title', size: 12, color: '#e8e8e8' },
    music: { path: `${MUSIC.folder}/${MUSIC.file}`, fit: true, balance: 100 },
  },
  print: {
    style: 'grid', paper: 'letter', orientation: 'landscape', rows: 2, cols: 2, gapX: 0.3, gapY: 0.45, margins: [0.6, 0.6, 1.1, 0.7], stroke: 0.5, strokeColor: '#bbbbbb',
    identity: { on: true, text: 'Alpine and Nordic', size: 16, x: 0.5, y: 0.07, color: '#333333' }, caption: { on: true, field: 'titleCaption', size: 9, custom: '' }, pageNumbers: true,
  },
  web: {
    layout: 'justified', rowHeight: 250, gap: 6,
    site: { title: 'Lakes and Peaks', collection: 'Alpine and Nordic', description: 'Thirteen photographs from the Alps, the Nordic coast and beyond.', contact: 'Photographs from Pexels photographers', link: '' },
    captions: { field: 'title', lightbox: 'titleCaption', exposure: true },
    watermark: { on: true, text: '{copyright}', size: 0.025, opacity: 0.65, anchor: 'br' },
  },
};
