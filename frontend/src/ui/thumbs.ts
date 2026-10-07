import { api } from '../io/api';
import type { Photo } from '../state/library';
import { el, q, setClass, setHtml, setStyleVar, setText, setTitle } from './dom';
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

const FLAG_ICON: Record<number, string> = { 1: 'flagPickFill', [-1]: 'flagRejectFill' };

export function badgesHtml(p: Photo, compact = false): string {
  const parts: string[] = [];
  if (p.f) parts.push(`<span class="fl-b-flag fl-b-flag-${p.f > 0 ? 'pick' : 'reject'}">${icon(FLAG_ICON[p.f] ?? 'flagPick', 12)}</span>`);
  if (p.r > 0) parts.push(`<span class="fl-b-stars" aria-label="${p.r} stars">${'<i></i>'.repeat(p.r)}</span>`);
  parts.push('<span class="fl-b-gap"></span>');
  if (p.e && !compact) parts.push(`<span class="fl-b-edit" title="Edited">${icon('modDevelop', 11)}</span>`);
  if (p.miss) parts.push(`<span class="fl-b-miss" title="Original missing">${icon('warning', 12)}</span>`);
  if (p.dur) parts.push(`<span class="fl-b-dur">${Math.floor(p.dur / 60)}:${String(Math.round(p.dur % 60)).padStart(2, '0')}</span>`);
  return parts.join('');
}

export class ThumbCell {
  readonly root: HTMLElement;
  private readonly img: HTMLImageElement;
  private readonly badges: HTMLElement;
  private readonly name: HTMLElement;
  private readonly stack: HTMLElement;
  id = -1;

  constructor(cls: string, withName: boolean) {
    this.root = el(`<div class="fl-cell ${cls}" role="gridcell"><div class="fl-cell-frame"><img class="fl-cell-img" alt="" draggable="false"></div><span class="fl-cell-stack" hidden></span><span class="fl-cell-vc" hidden></span>${withName ? '<span class="fl-cell-name"></span>' : '<span class="fl-cell-name" hidden></span>'}<div class="fl-badges"></div></div>`);
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
    setHtml(this.badges, badgesHtml(p, compact), `${p.f}|${p.r}|${p.e}|${p.miss ?? 0}|${p.dur ?? 0}|${compact ? 1 : 0}`);
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
