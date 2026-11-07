import { COLLECTIONS, MUSIC } from './data';
import { autoBook } from './layout';
import { store } from './store';

export function seedCollections(): void {
  const book = COLLECTIONS.book;
  store.addCollection({
    name: book.name, kind: 'book', ids: book.ids,
    settings: {
      size: 'standard-landscape', background: '#f4efe6', textColor: '#3a3128', captions: true, captionField: 'titleCaption', pageNumbers: true,
      cover: { template: 'cover', photos: [book.ids[0]], texts: ['Lakes and Peaks', 'Photographs from the Alps and beyond'] },
      pages: autoBook(book.ids.slice(1), store.aspects(book.ids.slice(1)), 'mixed'),
    },
  });
  const show = COLLECTIONS.slideshow;
  store.addCollection({
    name: show.name, kind: 'slideshow', ids: show.ids,
    settings: {
      background: '#0d0d0f', fill: false, margin: 0.06, shadow: true, panZoom: 0.45, duration: 4, fade: 1.5, repeat: true,
      intro: { on: true, text: 'Alpine and Nordic', seconds: 3 }, ending: { on: true, text: 'Thank you for watching', seconds: 3 },
      caption: { on: true, field: 'title', size: 12, color: '#e8e8e8' },
      music: { path: `${MUSIC.folder}/${MUSIC.file}`, fit: true, balance: 100 },
    },
  });
  const print = COLLECTIONS.print;
  store.addCollection({
    name: print.name, kind: 'print', ids: print.ids,
    settings: {
      style: 'grid', paper: 'letter', orientation: 'landscape', rows: 2, cols: 2, gapX: 0.3, gapY: 0.45, margins: [0.6, 0.6, 1.1, 0.7], stroke: 0.5, strokeColor: '#bbbbbb',
      identity: { on: true, text: 'Alpine and Nordic', size: 16, x: 0.5, y: 0.07, color: '#333333' }, caption: { on: true, field: 'titleCaption', size: 9, custom: '' }, pageNumbers: true,
    },
  });
  const web = COLLECTIONS.web;
  store.addCollection({
    name: web.name, kind: 'web', ids: web.ids,
    settings: {
      layout: 'justified', rowHeight: 250, gap: 6,
      site: { title: 'Lakes and Peaks', collection: 'Alpine and Nordic', description: 'Thirteen photographs from the Alps, the Nordic coast and beyond.', contact: 'Photographs from Pexels photographers', link: '' },
      captions: { field: 'title', lightbox: 'titleCaption', exposure: true },
      watermark: { on: true, text: '{copyright}', size: 0.025, opacity: 0.65, anchor: 'br' },
    },
  });
}
