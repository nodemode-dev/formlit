import type { Ctx } from '../../app';
import { catalog, type KeywordRow } from '../../state/catalog';
import { library } from '../../state/library';
import { askForm } from '../../ui/askform';
import { confirmAction } from '../../ui/dialogs';
import { PopupMenu } from '../../ui/menu';
import { toast } from '../../ui/toast';

const ROW_ITEMS = ['kw.assign', 'kw.unassign', 'kw.show', '-', 'kw.createInside', 'kw.edit', 'kw.toTop', 'kw.merge', '-', 'kw.delete', '-', 'kw.create', 'kw.purge'];
const PANEL_ITEMS = ['kw.create', '-', 'kw.purge'];

function list(s: unknown): string[] {
  return String(s ?? '').split(',').map((x) => x.trim()).filter(Boolean);
}

export class KeywordListMenu {
  private readonly menu: PopupMenu;
  private node: KeywordRow | null = null;

  constructor(private readonly ctx: Ctx) {
    this.menu = new PopupMenu(ctx.commands, null, true);
    const k = () => this.node;
    const has = () => !!k() && library.targets().length > 0;
    const fail = (e: unknown) => ctx.fail(e);
    ctx.commands.add(
      { id: 'kw.create', label: 'Create Keyword Tag...', run: () => void this.create(null) },
      { id: 'kw.createInside', label: 'Create Keyword Tag inside...', run: () => { const n = k(); if (n) void this.create(n); }, enabled: () => !!k() },
      { id: 'kw.edit', label: 'Edit Keyword Tag...', run: () => { const n = k(); if (n) void this.edit(n); }, enabled: () => !!k() },
      { id: 'kw.assign', label: 'Assign to Selected Photos', run: () => { const n = k(); if (n) void ctx.api.cmd('photo.addKeywords', { ids: library.targets(), keywords: [catalog.keywordPath(n.id)] }).catch(fail); }, enabled: has },
      { id: 'kw.unassign', label: 'Remove from Selected Photos', run: () => { const n = k(); if (n) void ctx.api.cmd('photo.removeKeywords', { ids: library.targets(), keywords: [catalog.keywordPath(n.id)] }).catch(fail); }, enabled: has },
      { id: 'kw.show', label: 'Show Photos with This Keyword', run: () => { const n = k(); if (n) library.setSource({ kind: 'keyword', id: n.id, label: n.name }); }, enabled: () => !!k() },
      { id: 'kw.toTop', label: 'Move to Top Level', run: () => { const n = k(); if (n) void ctx.api.cmd('keyword.update', { id: n.id, parent: null }).catch(fail); }, enabled: () => k()?.parent != null },
      { id: 'kw.merge', label: 'Merge Into...', run: () => { const n = k(); if (n) void this.merge(n); }, enabled: () => !!k() },
      { id: 'kw.delete', label: 'Delete...', run: () => { const n = k(); if (n) void this.remove(n); }, enabled: () => !!k() },
      { id: 'kw.purge', label: 'Purge Unused Keywords...', run: () => void this.purge() },
    );
  }

  openFor(node: KeywordRow | null, x: number, y: number): void {
    this.node = node;
    this.menu.setItems(node ? ROW_ITEMS : PANEL_ITEMS);
    this.menu.openAt(x, y);
  }

  private parents(): Array<[string, string]> {
    return [['', 'Top level'], ...catalog.tree.keywords.map((r): [string, string] => [String(r.id), catalog.keywordPath(r.id).split('|').join(' > ')]).sort((a, b) => a[1].localeCompare(b[1]))];
  }

  private async create(parent: KeywordRow | null): Promise<void> {
    const v = await askForm('Create Keyword Tag', 'Synonyms are other words for the same thing; they are found by searches and can be exported.', [
      { path: 'name', label: 'Keyword Name', kind: 'text' },
      { path: 'synonyms', label: 'Synonyms', kind: 'text', placeholder: 'comma separated' },
      { path: 'parent', label: 'Put Inside', kind: 'select', options: () => this.parents() },
      { path: 'export', label: 'Include on Export', kind: 'check' },
      { path: 'person', label: 'Person', kind: 'check' },
      { path: 'apply', label: 'Add to Selected Photos', kind: 'check' },
    ], { name: '', synonyms: '', parent: parent ? String(parent.id) : '', export: true, person: false, apply: false }, 'Create');
    const name = String(v?.name ?? '').trim().replace(/\|/g, '/');
    if (!v || !name) return;
    const path = v.parent ? `${catalog.keywordPath(Number(v.parent))}|${name}` : name;
    try {
      const r = await this.ctx.api.cmd<{ id: number }>('keyword.create', { path, synonyms: list(v.synonyms), person: !!v.person });
      if (!v.export) await this.ctx.api.cmd('keyword.update', { id: r.id, export: false });
      if (v.apply && library.targets().length) await this.ctx.api.cmd('photo.addKeywords', { ids: library.targets(), keywords: [path] });
      toast(`Created ${name}`);
    } catch (err) { this.ctx.fail(err); }
  }

  private async edit(n: KeywordRow): Promise<void> {
    const v = await askForm('Edit Keyword Tag', '', [
      { path: 'name', label: 'Keyword Name', kind: 'text' },
      { path: 'synonyms', label: 'Synonyms', kind: 'text', placeholder: 'comma separated' },
      { path: 'parent', label: 'Put Inside', kind: 'select', options: () => this.parents().filter(([id]) => id !== String(n.id) && !catalog.keywordPath(Number(id) || 0).startsWith(`${catalog.keywordPath(n.id)}|`)) },
      { path: 'export', label: 'Include on Export', kind: 'check' },
      { path: 'person', label: 'Person', kind: 'check' },
    ], { name: n.name, synonyms: n.synonyms.join(', '), parent: n.parent != null ? String(n.parent) : '', export: n.export, person: n.person }, 'Save');
    if (!v || !String(v.name ?? '').trim()) return;
    try {
      await this.ctx.api.cmd('keyword.update', { id: n.id, name: String(v.name).trim().replace(/\|/g, '/'), parent: v.parent ? Number(v.parent) : null, synonyms: list(v.synonyms), export: !!v.export, person: !!v.person });
    } catch (err) { this.ctx.fail(err); }
  }

  private async merge(n: KeywordRow): Promise<void> {
    const v = await askForm('Merge Keyword', `Every photo with "${n.name}" gets the keyword chosen here instead, and "${n.name}" is removed.`, [
      { path: 'into', label: 'Merge Into', kind: 'select', options: () => this.parents().filter(([id]) => id && id !== String(n.id)) },
    ], { into: '' }, 'Merge');
    if (!v?.into) return;
    try { await this.ctx.api.cmd('keyword.merge', { ids: [n.id], into: Number(v.into) }); } catch (err) { this.ctx.fail(err); }
  }

  private async remove(n: KeywordRow): Promise<void> {
    const kids = catalog.tree.keywords.filter((r) => catalog.keywordPath(r.id).startsWith(`${catalog.keywordPath(n.id)}|`)).length;
    const what = kids ? `"${n.name}" and the ${kids} keyword${kids === 1 ? '' : 's'} inside it` : `"${n.name}"`;
    if (!await confirmAction('Delete Keyword', `Delete ${what}? ${n.count ? `It is removed from ${n.count} photo${n.count === 1 ? '' : 's'}. ` : ''}Undo brings it back.`, 'Delete', true)) return;
    try { await this.ctx.api.cmd('keyword.delete', { id: n.id }); } catch (err) { this.ctx.fail(err); }
  }

  private async purge(): Promise<void> {
    if (!await confirmAction('Purge Unused Keywords', 'Delete every keyword that no photo carries? Keywords holding used keywords, and people, are kept.', 'Purge', true)) return;
    try {
      const r = await this.ctx.api.cmd<{ deleted: number }>('keyword.purge');
      toast(r.deleted ? `Purged ${r.deleted} unused keyword${r.deleted === 1 ? '' : 's'}` : 'No unused keywords');
    } catch (err) { this.ctx.fail(err); }
  }
}
