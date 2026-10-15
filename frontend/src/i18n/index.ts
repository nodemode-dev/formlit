import keys from './keys.json';
import keys2 from './keys2.json';
import keys3 from './keys3.json';
import keys4 from './keys4.json';
import keys5 from './keys5.json';
import keys6 from './keys6.json';
import keys7 from './keys7.json';
import keys8 from './keys8.json';
import keys9 from './keys9.json';
import keys10 from './keys10.json';
import keys11 from './keys11.json';
import keys12 from './keys12.json';
import keys13 from './keys13.json';
import keys14 from './keys14.json';

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
const loaders6 = import.meta.glob('./locales6/*.json');
const loaders7 = import.meta.glob('./locales7/*.json');
const loaders8 = import.meta.glob('./locales8/*.json');
const loaders9 = import.meta.glob('./locales9/*.json');
const loaders10 = import.meta.glob('./locales10/*.json');
const loaders11 = import.meta.glob('./locales11/*.json');
const loaders12 = import.meta.glob('./locales12/*.json');
const loaders13 = import.meta.glob('./locales13/*.json');
const loaders14 = import.meta.glob('./locales14/*.json');

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
  const more = loaders2[`./locales2/${want}.json`], more3 = loaders3[`./locales3/${want}.json`], more4 = loaders4[`./locales4/${want}.json`], more5 = loaders5[`./locales5/${want}.json`], more6 = loaders6[`./locales6/${want}.json`], more7 = loaders7[`./locales7/${want}.json`];
  const none = Promise.resolve({ default: {} });
  const [mod, mod2, mod3, mod4, mod5, mod6, mod7] = (await Promise.all([load(), more ? more() : none, more3 ? more3() : none, more4 ? more4() : none, more5 ? more5() : none, more6 ? more6() : none, more7 ? more7() : none])) as Array<{ default: Record<string, string> }>;
  const more8 = loaders8[`./locales8/${want}.json`], more9 = loaders9[`./locales9/${want}.json`];
  const mod8 = (more8 ? await more8() : { default: {} }) as { default: Record<string, string> };
  const mod9 = (more9 ? await more9() : { default: {} }) as { default: Record<string, string> };
  const more10 = loaders10[`./locales10/${want}.json`];
  const mod10 = (more10 ? await more10() : { default: {} }) as { default: Record<string, string> };
  const more11 = loaders11[`./locales11/${want}.json`], more12 = loaders12[`./locales12/${want}.json`], more13 = loaders13[`./locales13/${want}.json`];
  const more14 = loaders14[`./locales14/${want}.json`];
  const [mod11, mod12, mod13, mod14] = (await Promise.all([more11 ? more11() : none, more12 ? more12() : none, more13 ? more13() : none, more14 ? more14() : none])) as Array<{ default: Record<string, string> }>;
  const fixes = () => {
    (keys7 as string[]).forEach((en, i) => add(en, mod7.default[String(i)]));
    (keys8 as string[]).forEach((en, i) => add(en, mod8.default[String(i)]));
    (keys9 as string[]).forEach((en, i) => add(en, mod9.default[String(i)]));
  };
  code = want;
  document.documentElement.lang = locale();
  const add = (en: string, tr: string | undefined) => {
    if (!tr || tr === en) return;
    if (!/\{\d+\}/.test(en)) { exact.set(en, tr); return; }
    const plural = new Set([...en.matchAll(/[A-Za-z]\{(\d+)\}/g)].map((m) => m[1]));
    const fixed = plural.size ? tr.replace(/\{(\d+)\}/g, (all, n: string) => (plural.has(n) ? `{p${n}}` : all)) : tr;
    patterns.push([new RegExp('^' + escape(en).replace(/\\\{\d+\\\}/g, '([\\s\\S]*?)') + '$'), fixed]);
  };
  fixes();
  (keys4 as string[]).forEach((en, i) => add(en, mod4.default[String(i)]));
  (keys as string[]).forEach((en, i) => add(en, mod.default[String(i)]));
  (keys2 as string[]).forEach((en, i) => add(en, mod2.default[String(i)]));
  (keys3 as string[]).forEach((en, i) => add(en, mod3.default[String(i)]));
  (keys5 as string[]).forEach((en, i) => add(en, mod5.default[String(i)]));
  (keys6 as string[]).forEach((en, i) => add(en, mod6.default[String(i)]));
  (keys10 as string[]).forEach((en, i) => add(en, mod10.default[String(i)]));
  (keys11 as string[]).forEach((en, i) => add(en, mod11.default[String(i)]));
  (keys12 as string[]).forEach((en, i) => add(en, mod12.default[String(i)]));
  (keys13 as string[]).forEach((en, i) => add(en, mod13.default[String(i)]));
  (keys14 as string[]).forEach((en, i) => add(en, mod14.default[String(i)]));
  fixes();
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
