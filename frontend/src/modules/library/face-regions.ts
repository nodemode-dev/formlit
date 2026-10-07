import type { Ctx } from '../../app';
import { events } from '../../io/events';
import { el, escapeHtml, patchList, q, setClass, setHidden, setStyleVar } from '../../ui/dom';
import { icon } from '../../ui/icons';
import { toast } from '../../ui/toast';
import type { Viewer } from '../../ui/viewer';

interface Face { id: number; box: [number, number, number, number]; person: number | null; name: string; confirmed: boolean }

export class FaceRegions {
  readonly bar = el(`<div class="fl-face-bar"><button class="cv-icon-btn" type="button" data-f="show" title="Show Face Regions">${icon('people', 15)}</button><button class="cv-icon-btn" type="button" data-f="draw" title="Draw Face Region">${icon('faceScan', 15)}</button></div>`);
  private readonly layer = el('<div class="fl-face-layer" hidden><div class="fl-face-ghost" hidden></div></div>');
  private readonly names = el('<datalist id="fl-face-names"></datalist>');
  private on = false;
  private drawing = false;
  private faces: Face[] = [];
  private photo: number | null = null;
  private seq = 0;

  constructor(private readonly ctx: Ctx, private readonly viewer: Viewer) {
    viewer.box.appendChild(this.layer);
    document.body.appendChild(this.names);
    this.bar.addEventListener('click', (e) => {
      const b = (e.target as HTMLElement).closest<HTMLElement>('[data-f]');
      if (b?.dataset.f === 'show') this.toggle();
      else if (b?.dataset.f === 'draw') this.setDrawing(!this.drawing);
    });
    this.layer.addEventListener('pointerdown', (e) => this.down(e));
    this.layer.addEventListener('keydown', (e) => this.key(e));
    this.layer.addEventListener('click', (e) => this.click(e));
    this.layer.addEventListener('focusout', (e) => this.commit(e.target as HTMLElement));
    events.on('list.changed', (e) => { if (e.list === 'people' && this.on) void this.load(); });
  }

  get visible(): boolean { return this.on; }

  toggle(force?: boolean): void {
    this.on = force ?? !this.on;
    if (!this.on) this.setDrawing(false);
    this.sync();
    if (this.on) void this.load();
  }

  setDrawing(on: boolean): void {
    this.drawing = on;
    if (on && !this.on) { this.on = true; void this.load(); }
    this.ctx.shell.setHint(on ? 'Drag a box around a face, then type the name' : '');
    this.sync();
  }

  show(id: number | null): void {
    if (id === this.photo) return;
    this.photo = id;
    this.faces = [];
    this.paint();
    if (this.on) void this.load();
  }

  private sync(): void {
    setHidden(this.layer, !this.on);
    setClass(q(this.bar, '[data-f="show"]'), 'is-on', this.on);
    setClass(q(this.bar, '[data-f="draw"]'), 'is-on', this.drawing);
    setClass(this.layer, 'is-drawing', this.drawing);
  }

  private async load(): Promise<void> {
    const id = this.photo;
    if (id === null) return;
    const seq = ++this.seq;
    try {
      const r = await this.ctx.api.cmd<{ faces: Face[]; names: string[] }>('faces.forPhoto', { id });
      if (seq !== this.seq || id !== this.photo) return;
      this.faces = r.faces;
      const opts = r.names.map((n) => `<option value="${escapeHtml(n)}"></option>`).join('');
      if (this.names.dataset.key !== opts) { this.names.dataset.key = opts; this.names.innerHTML = opts; }
      this.paint();
    } catch (err) { this.ctx.fail(err); }
  }

  private paint(): void {
    const fill = (n: HTMLElement, f: Face) => {
      setStyleVar(n, 'left', `${f.box[0] * 100}%`);
      setStyleVar(n, 'top', `${f.box[1] * 100}%`);
      setStyleVar(n, 'width', `${f.box[2] * 100}%`);
      setStyleVar(n, 'height', `${f.box[3] * 100}%`);
      const input = q<HTMLInputElement>(n, 'input');
      if (document.activeElement !== input && input.value !== f.name) input.value = f.name;
      setClass(n, 'is-named', !!f.name);
      setClass(n, 'is-suggested', !!f.name && !f.confirmed);
      setHidden(q(n, '[data-a="ok"]'), !f.name || f.confirmed);
      setHidden(q(n, '[data-a="not"]'), !f.name);
      n.dataset.face = String(f.id);
    };
    patchList(this.layer, this.faces, {
      key: (f) => `f${f.id}`,
      create: (f) => {
        const n = el(`<div class="fl-face-box"><div class="fl-face-tag"><input class="fl-face-input" type="text" list="fl-face-names" spellcheck="false" placeholder="Who is this?"><button class="cv-icon-btn" type="button" data-a="ok" title="Confirm">${icon('check', 11)}</button><button class="cv-icon-btn" type="button" data-a="not" title="Not this person">${icon('minus', 11)}</button><button class="cv-icon-btn" type="button" data-a="del" title="Delete region">${icon('close', 11)}</button></div></div>`);
        fill(n, f);
        return n;
      },
      update: fill,
    });
    const ghost = q(this.layer, '.fl-face-ghost');
    if (ghost !== this.layer.firstElementChild) this.layer.prepend(ghost);
  }

  private faceOf(t: HTMLElement): Face | undefined {
    const id = Number(t.closest<HTMLElement>('[data-face]')?.dataset.face);
    return this.faces.find((f) => f.id === id);
  }

  private click(e: MouseEvent): void {
    const t = e.target as HTMLElement;
    const a = t.closest<HTMLElement>('[data-a]')?.dataset.a;
    const f = this.faceOf(t);
    if (!a || !f) return;
    e.stopPropagation();
    const fail = (err: unknown) => this.ctx.fail(err);
    if (a === 'ok') void this.ctx.api.cmd('people.name', { faces: [f.id], name: f.name }).then(() => this.load(), fail);
    else if (a === 'not') void this.ctx.api.cmd('people.unassign', { faces: [f.id] }).then(() => { toast(`Removed ${f.name} from this face`); return this.load(); }, fail);
    else if (a === 'del') void this.ctx.api.cmd('faces.delete', { faces: [f.id] }).then(() => this.load(), fail);
  }

  private key(e: KeyboardEvent): void {
    const input = (e.target as HTMLElement).closest<HTMLInputElement>('.fl-face-input');
    if (!input) return;
    e.stopPropagation();
    if (e.key === 'Enter') { e.preventDefault(); input.blur(); }
    if (e.key === 'Escape') { const f = this.faceOf(input); input.value = f?.name ?? ''; input.blur(); }
  }

  private commit(t: HTMLElement): void {
    const input = t.closest<HTMLInputElement>('.fl-face-input');
    const f = input ? this.faceOf(input) : undefined;
    if (!input || !f) return;
    const name = input.value.trim();
    if (name === f.name) return;
    const fail = (err: unknown) => this.ctx.fail(err);
    if (!name) { void this.ctx.api.cmd('people.unassign', { faces: [f.id] }).then(() => this.load(), fail); return; }
    void this.ctx.api.cmd('people.name', { faces: [f.id], name }).then(() => this.load(), fail);
  }

  private down(e: PointerEvent): void {
    if ((e.target as HTMLElement).closest('.fl-face-tag')) { e.stopPropagation(); return; }
    if (!this.drawing || e.button !== 0 || this.photo === null) return;
    e.stopPropagation();
    e.preventDefault();
    const r = this.layer.getBoundingClientRect();
    const at = (ev: PointerEvent): [number, number] => [Math.min(1, Math.max(0, (ev.clientX - r.left) / r.width)), Math.min(1, Math.max(0, (ev.clientY - r.top) / r.height))];
    const a = at(e);
    let b = a;
    const ghost = q(this.layer, '.fl-face-ghost');
    const place = () => {
      setStyleVar(ghost, 'left', `${Math.min(a[0], b[0]) * 100}%`);
      setStyleVar(ghost, 'top', `${Math.min(a[1], b[1]) * 100}%`);
      setStyleVar(ghost, 'width', `${Math.abs(b[0] - a[0]) * 100}%`);
      setStyleVar(ghost, 'height', `${Math.abs(b[1] - a[1]) * 100}%`);
    };
    place();
    setHidden(ghost, false);
    this.layer.setPointerCapture(e.pointerId);
    const move = (ev: PointerEvent) => { b = at(ev); place(); };
    const up = () => {
      this.layer.removeEventListener('pointermove', move);
      this.layer.removeEventListener('pointerup', up);
      setHidden(ghost, true);
      const box = [Math.min(a[0], b[0]), Math.min(a[1], b[1]), Math.abs(b[0] - a[0]), Math.abs(b[1] - a[1])];
      if (box[2] < 0.01 || box[3] < 0.01) return;
      const id = this.photo;
      void this.ctx.api.cmd<{ face: number }>('faces.add', { id, box }).then(async (res) => {
        this.setDrawing(false);
        await this.load();
        const input = this.layer.querySelector<HTMLInputElement>(`[data-face="${res.face}"] .fl-face-input`);
        input?.focus();
      }, (err) => this.ctx.fail(err));
    };
    this.layer.addEventListener('pointermove', move);
    this.layer.addEventListener('pointerup', up);
  }
}
