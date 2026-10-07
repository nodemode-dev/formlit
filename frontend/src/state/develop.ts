import { api } from '../io/api';
import { events } from '../io/events';
import { library } from './library';

export type Dev = Record<string, unknown>;

export interface ControlSpec {
  id: string;
  label: string;
  section: string;
  min: number;
  max: number;
  default: number;
  step: number;
  decimals: number;
  track: { kind: string; band?: number; from?: string; to?: string };
}

export interface ControlsDoc {
  controls: ControlSpec[];
  local: ControlSpec[];
  panels: Array<{ id: string; label: string; sections: string[]; toggle: string | null }>;
  wbPresets: Array<{ id: string; label: string; temp: number | null; tint: number | null }>;
  mixerBands: Array<{ id: string; label: string; hue: number }>;
  aspects: Array<{ id: string; label: string; ratio: [number, number] | null }>;
}

export interface Profile { id: string; group: string; name: string; mono: boolean; raw: boolean }

export interface DevInfo {
  id: number;
  kind: string;
  raw: boolean;
  asShotTemp: number;
  asShotTint: number;
  temp: number;
  tint: number;
  relativeWb: boolean;
  cameraLook: boolean;
  width: number;
  height: number;
  profiles: Profile[];
}

type Fn = (why: string) => void;

export function getPath(obj: Dev, path: string): unknown {
  let cur: unknown = obj;
  for (const p of path.split('.')) {
    if (!cur || typeof cur !== 'object') return undefined;
    cur = (cur as Record<string, unknown>)[p];
  }
  return cur;
}

export function setPath(obj: Dev, path: string, value: unknown): void {
  const parts = path.split('.');
  let cur = obj as Record<string, unknown>;
  for (const p of parts.slice(0, -1)) {
    const next = cur[p];
    if (!next || typeof next !== 'object' || Array.isArray(next)) cur[p] = {};
    cur = cur[p] as Record<string, unknown>;
  }
  if (value === undefined) delete cur[parts[parts.length - 1]];
  else cur[parts[parts.length - 1]] = value;
}

export function clone<T>(v: T): T { return JSON.parse(JSON.stringify(v ?? {})) as T; }

export class DevelopSession {
  doc: ControlsDoc | null = null;
  specs = new Map<string, ControlSpec>();
  id: number | null = null;
  settings: Dev = {};
  committed = '{}';
  info: DevInfo | null = null;
  pendingLabel = '';
  private commitTimer = 0;
  private loadSeq = 0;
  private readonly fns = new Set<Fn>();
  dirty = false;

  constructor() {
    events.on('photos.changed', (e) => {
      if (this.id === null) return;
      const map = (e.photos ?? {}) as Record<string, string[]>;
      const f = map[String(this.id)];
      if (f && f.includes('develop') && !this.dirty) void this.reload();
    });
    for (const t of ['undo', 'redo']) events.on(t, () => { if (this.id !== null && !this.dirty) void this.reload(); });
  }

  listen(fn: Fn): () => void { this.fns.add(fn); return () => { this.fns.delete(fn); }; }

  emit(why: string): void { for (const fn of this.fns) fn(why); }

  async init(): Promise<void> {
    if (this.doc) return;
    this.doc = await api.cmd<ControlsDoc>('develop.controls');
    for (const c of this.doc.controls) this.specs.set(c.id, c);
  }

  async open(id: number | null): Promise<void> {
    await this.init();
    if (id === this.id) return;
    await this.flush();
    this.id = id;
    this.info = null;
    if (id === null) { this.settings = {}; this.emit('photo'); return; }
    await this.reload('photo');
  }

  async reload(why = 'reload'): Promise<void> {
    const id = this.id;
    if (id === null) return;
    const seq = ++this.loadSeq;
    const [got, info] = await Promise.all([
      api.cmd<{ settings: Dev }>('develop.get', { id }),
      api.cmd<DevInfo>('develop.info', { id }).catch(() => null),
    ]);
    if (seq !== this.loadSeq || id !== this.id) return;
    this.settings = got.settings ?? {};
    this.committed = JSON.stringify(this.settings);
    if (info) this.info = info;
    this.dirty = false;
    this.emit(why);
  }

  value(cid: string): number {
    const spec = this.specs.get(cid);
    if ((cid === 'wb.temp' || cid === 'wb.tint') && this.wbMode() !== 'custom' && this.info) return cid === 'wb.temp' ? this.info.temp : this.info.tint;
    const v = getPath(this.settings, cid);
    return typeof v === 'number' ? v : spec?.default ?? 0;
  }

  wbMode(): string { return String((getPath(this.settings, 'wb.mode') as string | undefined) ?? 'asShot'); }

  set(cid: string, v: number, phase: 'drag' | 'end', label?: string): void {
    if (cid === 'wb.temp' || cid === 'wb.tint') {
      if (this.wbMode() !== 'custom') {
        setPath(this.settings, 'wb.temp', this.value('wb.temp'));
        setPath(this.settings, 'wb.tint', this.value('wb.tint'));
        setPath(this.settings, 'wb.mode', 'custom');
      }
    }
    const spec = this.specs.get(cid);
    const clamped = spec ? Math.max(spec.min, Math.min(spec.max, v)) : v;
    const rounded = spec ? Number(clamped.toFixed(spec.decimals)) : clamped;
    setPath(this.settings, cid, rounded);
    this.changed(phase, label ?? this.labelFor(cid, rounded));
  }

  patch(path: string, value: unknown, phase: 'drag' | 'end', label: string): void {
    setPath(this.settings, path, value === null ? undefined : value);
    this.changed(phase, label);
  }

  replace(next: Dev, phase: 'drag' | 'end', label: string): void {
    this.settings = next;
    this.changed(phase, label);
  }

  isDisabled(section: string): boolean { return ((this.settings.disabled as string[] | undefined) ?? []).includes(section); }

  toggleSection(section: string): void {
    const cur = new Set((this.settings.disabled as string[] | undefined) ?? []);
    if (cur.has(section)) cur.delete(section); else cur.add(section);
    this.settings.disabled = [...cur];
    this.changed('end', `${cur.has(section) ? 'Disable' : 'Enable'} ${section}`);
  }

  labelFor(cid: string, v: number): string {
    const spec = this.specs.get(cid);
    if (!spec) return cid;
    const sign = v > 0 && spec.min < 0 ? '+' : '';
    return `${spec.label} ${sign}${v.toFixed(spec.decimals)}`;
  }

  private changed(phase: 'drag' | 'end', label: string): void {
    this.dirty = true;
    this.pendingLabel = label;
    this.emit(phase === 'drag' ? 'drag' : 'edit');
    window.clearTimeout(this.commitTimer);
    this.commitTimer = window.setTimeout(() => void this.flush(), phase === 'drag' ? 900 : 350);
  }

  async flush(): Promise<void> {
    window.clearTimeout(this.commitTimer);
    const id = this.id;
    if (id === null || !this.dirty) return;
    const snapshot = JSON.stringify(this.settings);
    if (snapshot === this.committed) { this.dirty = false; return; }
    const label = this.pendingLabel || 'Develop';
    try {
      const before = JSON.parse(this.committed) as Dev;
      await api.cmd('develop.update', { ids: [id], patch: JSON.parse(snapshot), replace: true, label });
      const others = this.autoSync ? library.selected().filter((x) => x !== id) : [];
      if (others.length) await this.syncOthers(id, before, JSON.parse(snapshot) as Dev, others);
      if (id === this.id) {
        this.committed = snapshot;
        if (JSON.stringify(this.settings) === snapshot) this.dirty = false;
      }
    } catch (err) {
      this.emit('error');
      throw err;
    }
  }

  get autoSync(): boolean {
    try { return localStorage.getItem('formlit_auto_sync') === '1'; } catch { return false; }
  }

  set autoSync(on: boolean) {
    try { localStorage.setItem('formlit_auto_sync', on ? '1' : '0'); } catch { this.emit('info'); }
    this.emit('info');
  }

  private async syncOthers(from: number, before: Dev, after: Dev, ids: number[]): Promise<void> {
    const values: Record<string, number> = {};
    const covered = new Set<string>();
    for (const cid of this.specs.keys()) {
      const a = getPath(after, cid), b = getPath(before, cid);
      if (a !== b && typeof (a ?? 0) === 'number') { values[cid] = Number(a ?? this.specs.get(cid)?.default ?? 0); covered.add(cid.split('.')[0]); }
    }
    const groups = Array.from(new Set([...Object.keys(after), ...Object.keys(before)])).filter((k) => JSON.stringify(after[k]) !== JSON.stringify(before[k]) && !covered.has(k) && !['crop', 'orientation'].includes(k));
    if (Object.keys(values).length) await api.cmd('develop.set', { ids, values });
    if (groups.length) await api.cmd('develop.sync', { from, ids, groups });
  }

  async refreshInfo(): Promise<void> {
    if (this.id === null) return;
    const info = await api.cmd<DevInfo>('develop.info', { id: this.id, settings: this.settings }).catch(() => null);
    if (info) { this.info = info; this.emit('info'); }
  }
}

export const develop = new DevelopSession();

export function activePhoto() { return library.photo(library.active); }
