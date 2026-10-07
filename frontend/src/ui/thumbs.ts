import { api } from '../io/api';
import type { Photo } from '../state/library';
import { el, q, setClass, setHidden, setHtml, setStyleVar, setText, setTitle } from './dom';
import { icon } from './icons';

const bumps = new Map<string, number>();

export function bump(id: number, size: string): void {
  const k = `${id}:${size}`;
  bumps.set(k, (bumps.get(k) ?? 0) + 1);
}

export function thumbUrl(p: Photo): string {
  const n = bumps.get(`${p.id}:t`) ?? 0;
  return api.url(`/api/photos/${p.id}/thumb?rev=${p.rev}${n ? `&n=${n}` : ''}`);
}

export function previewUrl(p: Photo): string {
  const n = bumps.get(`${p.id}:p`) ?? 0;
  return api.url(`/api/photos/${p.id}/preview?rev=${p.rev}${n ? `&n=${n}` : ''}`);
}

export function loadInto(img: HTMLImageElement, url: string): Promise<boolean> {
  if (img.dataset.src === url) return Promise.resolve(false);
  img.dataset.src = url;
  const next = new Image();
  next.decoding = 'async';
  next.src = url;
  return next.decode().then(() => {
    if (img.dataset.src !== url) return false;
    img.src = url;
    setClass(img, 'is-loaded', true);
    return true;
  }, () => {
    if (img.dataset.src === url) setClass(img, 'is-failed', true);
    return false;
  });
}

const BADGES = `<span class="fl-b-flag fl-b-flag-pick" hidden>${icon('flagPickFill', 12)}</span><span class="fl-b-flag fl-b-flag-reject" hidden>${icon('flagRejectFill', 12)}</span><span class="fl-b-stars" hidden>${'<i></i>'.repeat(5)}</span><span class="fl-b-gap"></span><span class="fl-b-edit" title="Edited" hidden>${icon('modDevelop', 11)}</span><span class="fl-b-miss" title="Original missing" hidden>${icon('warning', 12)}</span><span class="fl-b-dur" hidden></span>`;

export class ThumbCell {
  readonly root: HTMLElement;
  private readonly img: HTMLImageElement;
  private readonly badges: HTMLElement;
  private readonly name: HTMLElement;
  private readonly stack: HTMLElement;
  id = -1;

  constructor(cls: string, withName: boolean) {
    this.root = el(`<div class="fl-cell ${cls}" role="gridcell"><div class="fl-cell-frame"><img class="fl-cell-img" alt="" draggable="false"></div><span class="fl-cell-stack" hidden></span><span class="fl-cell-vc" hidden></span>${withName ? '<span class="fl-cell-name"></span>' : '<span class="fl-cell-name" hidden></span>'}<div class="fl-badges">${BADGES}</div></div>`);
    this.img = q<HTMLImageElement>(this.root, 'img');
    this.badges = q(this.root, '.fl-badges');
    this.name = q(this.root, '.fl-cell-name');
    this.stack = q(this.root, '.fl-cell-stack');
  }

  bind(p: Photo, compact = false): void {
    const fresh = this.id !== p.id;
    this.id = p.id;
    this.root.dataset.id = String(p.id);
    if (fresh) {
      this.img.removeAttribute('src');
      delete this.img.dataset.src;
      setClass(this.img, 'is-loaded', false);
      setClass(this.img, 'is-failed', false);
    }
    setStyleVar(this.root, '--fl-aspect', String(p.a || 1.5));
    void loadInto(this.img, thumbUrl(p));
    const [pick, reject, stars, , edit, miss, dur] = Array.from(this.badges.children) as HTMLElement[];
    setHidden(pick, p.f <= 0);
    setHidden(reject, p.f >= 0);
    setHidden(stars, !(p.r > 0));
    setStyleVar(stars, '--fl-r', String(p.r));
    setTitle(stars, `${p.r} stars`);
    setHidden(edit, !p.e || compact);
    setHidden(miss, !p.miss);
    setHidden(dur, !p.dur);
    if (p.dur) setText(dur, `${Math.floor(p.dur / 60)}:${String(Math.round(p.dur % 60)).padStart(2, '0')}`);
    setText(this.name, p.cn ? `${p.file} · ${p.cn}` : p.file);
    this.root.dataset.label = p.l || '';
    setClass(this.root, 'is-reject', p.f < 0);
    const vc = q(this.root, '.fl-cell-vc');
    vc.hidden = !p.m;
    const sn = p.sn ?? 0;
    this.stack.hidden = !(sn > 1 && (p.sp ?? 0) === 0);
    if (!this.stack.hidden) setHtml(this.stack, `${icon('stack', 11)}<span>${sn}</span>`, `${sn}|${p.sc ?? 0}`);
    setClass(this.stack, 'is-open', !p.sc);
    setTitle(this.root, `${p.file}${p.t ? ` · ${p.t.slice(0, 16).replace('T', ' ')}` : ''}`);
  }

  setState(selected: boolean, active: boolean): void {
    setClass(this.root, 'is-selected', selected);
    setClass(this.root, 'is-active', active);
  }
}
