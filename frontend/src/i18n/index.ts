import keys from './keys.json';
import keys2 from './keys2.json';
import keys3 from './keys3.json';
import keys4 from './keys4.json';
import keys5 from './keys5.json';

export const LANGUAGES: Array<[string, string]> = [
  ['en', 'English'], ['es', 'Español (España)'], ['es-MX', 'Español (México)'], ['pt-BR', 'Português (Brasil)'], ['fr', 'Français (France)'],
  ['fr-CA', 'Français (Canada)'], ['de', 'Deutsch'], ['it', 'Italiano'], ['nl', 'Nederlands'], ['da', 'Dansk'], ['fi', 'Suomi'], ['nb', 'Norsk bokmål'],
  ['sv', 'Svenska'], ['ru', 'Русский'], ['pl', 'Polski'], ['cs', 'Čeština'], ['hu', 'Magyar'], ['uk', 'Українська'], ['tr', 'Türkçe'],
  ['zh-Hans', '简体中文'], ['zh-Hant', '繁體中文'], ['ja', '日本語'], ['ko', '한국어'], ['id', 'Bahasa Indonesia'], ['th', 'ไทย'], ['vi', 'Tiếng Việt'],
];
const STORE = 'formlit_lang';
const ATTRS = ['title', 'placeholder', 'aria-label', 'alt'];
const SKIP = 'script, style, textarea, code, pre, [translate="no"], [contenteditable="true"], .xterm, .fl-chat-msg, .fl-cmt-list, .fl-cell-name, .fl-md, .fl-code';
const loaders = import.meta.glob('./locales/*.json');
const loaders2 = import.meta.glob('./locales2/*.json');
const loaders3 = import.meta.glob('./locales3/*.json');
const loaders4 = import.meta.glob('./locales4/*.json');
const loaders5 = import.meta.glob('./locales5/*.json');

let code = 'en';
const exact = new Map<string, string>();
const patterns: Array<[RegExp, string]> = [];
const cache = new Map<string, string | null>();
const wroteText = new WeakMap<Node, string>();
const wroteAttr = new WeakMap<Element, Map<string, string>>();

export function language(): string { return code; }

export function locale(): string { return code === 'zh-Hans' ? 'zh-CN' : code === 'zh-Hant' ? 'zh-TW' : code; }

function stored(): string {
  try { return localStorage.getItem(STORE) || 'en'; } catch { return 'en'; }
}

export function setLanguage(next: string): void {
  try { localStorage.setItem(STORE, next); } catch { return; }
  window.location.reload();
}

function lookup(en: string): string | null {
  const hit = cache.get(en);
  if (hit !== undefined) return hit;
  cache.set(en, null);
  let out = exact.get(en) ?? null;
  if (out === null) {
    for (const [re, tr] of patterns) {
      const m = re.exec(en);
      if (m) { out = tr.replace(/\{(\d+):([^{}]+)\}/g, (_, n: string, forms: string) => plural(m[Number(n) + 1] ?? '', forms)).replace(/\{(p?)(\d+)\}/g, (_, p: string, n: string) => { if (p) return ''; const v = m[Number(n) + 1] ?? ''; return lookup(v) ?? v; }); break; }
    }
  }
  if (out === null && /[:.]$/.test(en) && !en.endsWith('...')) {
    const base = lookup(en.slice(0, -1));
    if (base !== null) out = base + en.slice(-1);
  }
  const keyed = out === null ? /^([\s\S]+?) \(([^()]{1,24})\)$/.exec(en) : null;
  if (keyed && /^((Alt|Shift|Ctrl|Cmd|Mod|Option)\+)*(\S{1,9}|Left|Right|Up|Down|Space|Enter|Esc|Tab|Backspace|Delete)$/.test(keyed[2])) {
    const base = lookup(keyed[1]);
    if (base !== null) out = `${base} (${keyed[2]})`;
  }
  if (out === null && en.includes(' · ')) {
    const parts = en.split(' · ').map((p) => lookup(p));
    if (parts.some((p) => p !== null)) out = en.split(' · ').map((p, i) => parts[i] ?? p).join(' · ');
  }
  if (cache.size > 20000) cache.clear();
  cache.set(en, out);
  return out;
}

export function t(en: string): string {
  if (code === 'en') return en;
  const m = /^(\s*)([\s\S]*?)(\s*)$/.exec(en);
  if (!m || !m[2]) return en;
  const tr = lookup(m[2]);
  return tr === null ? en : m[1] + tr + m[3];
}

function skipped(el: Element | null): boolean {
  return !el || el.closest(SKIP) !== null;
}

function text(node: Text): void {
  const cur = node.data;
  if (wroteText.get(node) === cur || !/[A-Za-z]/.test(cur) || skipped(node.parentElement)) return;
  const next = t(cur);
  if (next !== cur) { wroteText.set(node, next); node.data = next; }
}

function attrs(el: Element): void {
  if (skipped(el)) return;
  for (const a of ATTRS) {
    const cur = el.getAttribute(a);
    if (!cur) continue;
    const mine = wroteAttr.get(el);
    if (mine?.get(a) === cur) continue;
    const next = t(cur);
    if (next !== cur) {
      const map = mine ?? new Map<string, string>();
      map.set(a, next);
      wroteAttr.set(el, map);
      el.setAttribute(a, next);
    }
  }
}

function walk(root: Node): void {
  if (root.nodeType === Node.TEXT_NODE) { text(root as Text); return; }
  if (root.nodeType !== Node.ELEMENT_NODE) return;
  const el = root as Element;
  if (skipped(el)) return;
  attrs(el);
  const w = document.createTreeWalker(el, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT, {
    acceptNode: (n) => (n.nodeType === Node.ELEMENT_NODE && (n as Element).matches(SKIP) ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT),
  });
  for (let n = w.nextNode(); n; n = w.nextNode()) {
    if (n.nodeType === Node.TEXT_NODE) text(n as Text); else attrs(n as Element);
  }
}

function escape(s: string): string { return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }

function plural(count: string, forms: string): string {
  const pick = new Map(forms.split(';').map((f) => f.split('=') as [string, string]));
  const cat = new Intl.PluralRules(locale()).select(Number(count.replace(/[^\d.]/g, '')) || 0);
  return pick.get(cat) ?? pick.get('other') ?? '';
}

export async function initLanguage(): Promise<void> {
  const want = stored();
  const load = loaders[`./locales/${want}.json`];
  if (want === 'en' || !load) return;
  const more = loaders2[`./locales2/${want}.json`], more3 = loaders3[`./locales3/${want}.json`], more4 = loaders4[`./locales4/${want}.json`], more5 = loaders5[`./locales5/${want}.json`];
  const none = Promise.resolve({ default: {} });
  const [mod, mod2, mod3, mod4, mod5] = (await Promise.all([load(), more ? more() : none, more3 ? more3() : none, more4 ? more4() : none, more5 ? more5() : none])) as Array<{ default: Record<string, string> }>;
  code = want;
  document.documentElement.lang = locale();
  const add = (en: string, tr: string | undefined) => {
    if (!tr || tr === en) return;
    if (!/\{\d+\}/.test(en)) { exact.set(en, tr); return; }
    const plural = new Set([...en.matchAll(/[A-Za-z]\{(\d+)\}/g)].map((m) => m[1]));
    const fixed = plural.size ? tr.replace(/\{(\d+)\}/g, (all, n: string) => (plural.has(n) ? `{p${n}}` : all)) : tr;
    patterns.push([new RegExp('^' + escape(en).replace(/\\\{\d+\\\}/g, '([\\s\\S]*?)') + '$'), fixed]);
  };
  (keys4 as string[]).forEach((en, i) => add(en, mod4.default[String(i)]));
  (keys as string[]).forEach((en, i) => add(en, mod.default[String(i)]));
  (keys2 as string[]).forEach((en, i) => add(en, mod2.default[String(i)]));
  (keys3 as string[]).forEach((en, i) => add(en, mod3.default[String(i)]));
  (keys5 as string[]).forEach((en, i) => add(en, mod5.default[String(i)]));
  patterns.sort((a, b) => b[0].source.length - a[0].source.length);
  document.title = t(document.title);
  walk(document.body);
  new MutationObserver((list) => {
    for (const m of list) {
      if (m.type === 'characterData') text(m.target as Text);
      else if (m.type === 'attributes') attrs(m.target as Element);
      else m.addedNodes.forEach(walk);
    }
  }).observe(document.body, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ATTRS });
}
