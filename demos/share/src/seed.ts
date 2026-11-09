import { COLLECTIONS, OUTPUTS } from './data';
import { autoBook } from './layout';
import { store } from './store';

export function seedCollections(): void {
  const book = COLLECTIONS.book;
  const { coverTexts, ...bookLook } = OUTPUTS.book;
  store.addCollection({
    name: book.name, kind: 'book', ids: book.ids,
    settings: {
      ...bookLook,
      cover: { template: 'cover', photos: [book.ids[0]], texts: coverTexts },
      pages: autoBook(book.ids.slice(1), store.aspects(book.ids.slice(1)), 'mixed'),
    },
  });
  const show = COLLECTIONS.slideshow;
  store.addCollection({ name: show.name, kind: 'slideshow', ids: show.ids, settings: OUTPUTS.slideshow });
  const print = COLLECTIONS.print;
  store.addCollection({ name: print.name, kind: 'print', ids: print.ids, settings: OUTPUTS.print });
  const web = COLLECTIONS.web;
  store.addCollection({ name: web.name, kind: 'web', ids: web.ids, settings: OUTPUTS.web });
}
