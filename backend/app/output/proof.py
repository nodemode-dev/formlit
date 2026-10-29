import hashlib
import html
import json
import secrets
from pathlib import Path
from typing import Any, Callable

from app.engine import catalog as catalog_mod
from app.engine.records import loads
from app.output import encode, export

FORMAT = "formlit-proof"


def key_of(pid: int, content_hash: str) -> str:
    return f"{pid}-{hashlib.sha1(f'{pid}:{content_hash}'.encode()).hexdigest()[:8]}"


PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<style>
:root{--bg:#141416;--panel:#1d1d21;--line:#2c2c32;--text:#ececf0;--muted:#9a9aa6;--accent:#f97316;--pick:#3fb950;--reject:#f85149}
*{box-sizing:border-box}html,body{margin:0;background:var(--bg);color:var(--text);font:14px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
header{position:sticky;top:0;z-index:2;display:flex;flex-wrap:wrap;gap:10px 16px;align-items:center;padding:12px 16px;background:var(--panel);border-bottom:1px solid var(--line)}
h1{font-size:17px;margin:0;font-weight:600;flex:1 1 auto}
.count{color:var(--muted);font-variant-numeric:tabular-nums}
button,select{font:inherit;color:var(--text);background:#26262c;border:1px solid var(--line);border-radius:6px;padding:6px 12px;cursor:pointer}
button.cta{background:var(--accent);border-color:var(--accent);color:#111;font-weight:600}
.note{color:var(--muted);padding:10px 16px 0;margin:0}
main{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px;padding:16px}
.cell{position:relative;background:var(--panel);border:2px solid transparent;border-radius:8px;overflow:hidden;cursor:zoom-in}
.cell img{display:block;width:100%;aspect-ratio:3/2;object-fit:contain;background:#000}
.cell.pick{border-color:var(--pick)}.cell.reject{border-color:var(--reject)}.cell.reject img{opacity:.45}
.bar{display:flex;align-items:center;gap:6px;padding:6px 8px;color:var(--muted);font-size:12px;min-height:30px}
.bar .stars{color:var(--accent);letter-spacing:1px}.bar .c{margin-left:auto}
.badge{position:absolute;top:6px;left:6px;padding:2px 7px;border-radius:10px;font-size:11px;font-weight:600;color:#111}
.badge.pick{background:var(--pick)}.badge.reject{background:var(--reject)}
#loupe{position:fixed;inset:0;z-index:3;display:none;grid-template-rows:1fr auto;background:rgba(10,10,12,.97)}
#loupe.on{display:grid}
#loupe .stage{display:flex;align-items:center;justify-content:center;min-height:0;padding:12px}
#loupe img{max-width:100%;max-height:100%;object-fit:contain}
#loupe .tools{display:flex;flex-wrap:wrap;gap:8px;align-items:center;padding:12px 16px;background:var(--panel);border-top:1px solid var(--line)}
#loupe textarea{flex:1 1 260px;min-height:38px;max-height:120px;resize:vertical;font:inherit;color:var(--text);background:#26262c;border:1px solid var(--line);border-radius:6px;padding:7px 9px}
.on-pick{background:var(--pick)!important;color:#111!important}.on-reject{background:var(--reject)!important;color:#111!important}.on-star{color:var(--accent)!important}
.help{color:var(--muted);font-size:12px;width:100%}
dialog{background:var(--panel);color:var(--text);border:1px solid var(--line);border-radius:10px;max-width:520px;width:calc(100% - 32px)}
dialog input,dialog textarea{width:100%;font:inherit;color:var(--text);background:#26262c;border:1px solid var(--line);border-radius:6px;padding:7px 9px;margin:6px 0 12px}
@media (max-width:600px){main{grid-template-columns:repeat(2,1fr);gap:8px;padding:8px}}
</style></head><body>
<header><h1>__TITLE__</h1><span class="count" id="count"></span>
<select id="filter" aria-label="Show"><option value="all">All photos</option><option value="pick">Picks</option><option value="unmarked">Not marked yet</option><option value="reject">Rejected</option></select>
<button class="cta" id="send" type="button">Send my selections</button></header>
<p class="note">__NOTE__</p>
<main id="grid"></main>
<div id="loupe" role="dialog" aria-label="Photo"><div class="stage"><img id="big" alt=""></div>
<div class="tools"><button id="prev" type="button">Previous</button><button id="next" type="button">Next</button>
<button id="bpick" type="button">Pick (P)</button><button id="breject" type="button">Reject (X)</button>
<span id="bstars"></span><textarea id="comment" placeholder="A comment for the photographer (optional)"></textarea><button id="close" type="button">Close (Esc)</button>
<div class="help">Keys: arrows to move, P pick, X reject, U unmark, 1 to 5 stars, 0 no stars, Esc back to the grid. Your choices are kept in this browser until you send them.</div></div></div>
<dialog id="sendDlg"><form method="dialog"><h3 style="margin-top:0">Send your selections</h3>
<label>Your name<input id="who" autocomplete="name" required></label>
<p class="count" id="summary"></p>
<p style="color:var(--muted)">This saves a small file. Send it to the photographer by email or message. If the download does not start, copy the text below instead.</p>
<textarea id="code" rows="4" readonly></textarea>
<div style="display:flex;gap:8px;justify-content:flex-end"><button value="cancel">Close</button><button id="copy" type="button">Copy text</button><button class="cta" id="save" type="button">Save file</button></div></form></dialog>
<script>
const DATA = __DATA__;
const store = (() => { try { const k = 'proof-' + DATA.id; return { get: () => JSON.parse(localStorage.getItem(k) || '{}'), set: (v) => localStorage.setItem(k, JSON.stringify(v)) }; } catch (e) { let m = {}; return { get: () => m, set: (v) => { m = v; } }; } })();
let marks = {}; try { marks = store.get() || {}; } catch (e) { marks = {}; }
const save = () => { try { store.set(marks); } catch (e) {} };
const $ = (id) => document.getElementById(id);
const grid = $('grid'); let cur = -1; let shown = DATA.photos.map((_, i) => i);
const m = (k) => marks[k] || (marks[k] = { pick: false, reject: false, rating: 0, comment: '' });
function cellHtml(p) { const s = marks[p.key] || {}; const st = s.rating ? '\u2605'.repeat(s.rating) : ''; return `${s.pick ? '<span class="badge pick">Pick</span>' : s.reject ? '<span class="badge reject">Reject</span>' : ''}<img loading="lazy" src="${p.thumb}" alt="${p.label}"><div class="bar"><span>${p.label}</span><span class="stars">${st}</span><span class="c">${s.comment ? 'Comment' : ''}</span></div>`; }
function paintCell(i) { const p = DATA.photos[i]; const el = grid.querySelector(`[data-i="${i}"]`); if (!el) return; const s = marks[p.key] || {}; el.className = 'cell' + (s.pick ? ' pick' : s.reject ? ' reject' : ''); el.innerHTML = cellHtml(p); }
function build() { const f = $('filter').value; shown = DATA.photos.map((_, i) => i).filter((i) => { const s = marks[DATA.photos[i].key] || {}; return f === 'all' || (f === 'pick' && s.pick) || (f === 'reject' && s.reject) || (f === 'unmarked' && !s.pick && !s.reject); });
  grid.innerHTML = shown.map((i) => `<div class="cell" data-i="${i}" tabindex="0"></div>`).join(''); shown.forEach(paintCell); count(); }
const picks = () => Object.values(marks).filter((s) => s.pick).length;
function count() { const v = Object.values(marks); $('count').textContent = `${DATA.photos.length} photos · ${picks()}${DATA.limit ? ` of ${DATA.limit}` : ''} picked · ${v.filter((s) => s.reject).length} rejected`; }
function open(i) { cur = i; const p = DATA.photos[i]; $('big').src = p.large; $('big').alt = p.label; $('loupe').classList.add('on'); tools(); }
function tools() { const p = DATA.photos[cur]; const s = marks[p.key] || {}; $('bpick').className = s.pick ? 'on-pick' : ''; $('breject').className = s.reject ? 'on-reject' : '';
  $('bstars').innerHTML = [1, 2, 3, 4, 5].map((n) => `<button type="button" data-star="${n}" class="${(s.rating || 0) >= n ? 'on-star' : ''}" aria-label="${n} stars">\u2605</button>`).join(''); if (document.activeElement !== $('comment')) $('comment').value = s.comment || ''; }
function setMark(fn) { const p = DATA.photos[cur]; fn(m(p.key)); save(); tools(); paintCell(cur); count(); }
function move(d) { const at = shown.indexOf(cur); const nx = shown[Math.max(0, Math.min(shown.length - 1, (at < 0 ? 0 : at) + d))]; if (nx !== undefined) open(nx); }
grid.addEventListener('click', (e) => { const c = e.target.closest('[data-i]'); if (c) open(+c.dataset.i); });
grid.addEventListener('keydown', (e) => { const c = e.target.closest('[data-i]'); if (c && e.key === 'Enter') open(+c.dataset.i); });
$('filter').addEventListener('change', build);
$('prev').onclick = () => move(-1); $('next').onclick = () => move(1); $('close').onclick = () => { $('loupe').classList.remove('on'); build(); };
$('bpick').onclick = () => { const s = marks[DATA.photos[cur].key] || {};
  if (!s.pick && DATA.limit && picks() >= DATA.limit) { $('count').textContent = `You have picked ${DATA.limit}, the most for this gallery. Unpick one to choose another.`; return; }
  setMark((s) => { s.pick = !s.pick; if (s.pick) s.reject = false; }); };
$('breject').onclick = () => setMark((s) => { s.reject = !s.reject; if (s.reject) s.pick = false; });
$('bstars').onclick = (e) => { const b = e.target.closest('[data-star]'); if (b) setMark((s) => { const n = +b.dataset.star; s.rating = s.rating === n ? 0 : n; }); };
$('comment').addEventListener('input', () => { const p = DATA.photos[cur]; m(p.key).comment = $('comment').value; save(); paintCell(cur); });
document.addEventListener('keydown', (e) => { if (!$('loupe').classList.contains('on') || e.target === $('comment')) return; const k = e.key.toLowerCase();
  if (k === 'arrowright') move(1); else if (k === 'arrowleft') move(-1); else if (k === 'escape') $('close').onclick(); else if (k === 'p') $('bpick').onclick(); else if (k === 'x') $('breject').onclick();
  else if (k === 'u') setMark((s) => { s.pick = false; s.reject = false; }); else if (/^[0-5]$/.test(k)) setMark((s) => { s.rating = +k; }); else return; e.preventDefault(); });
function payload() { const photos = DATA.photos.map((p) => ({ key: p.key, ...(marks[p.key] || {}) })).filter((s) => s.pick || s.reject || s.rating || (s.comment || '').trim());
  return { format: 'formlit-proof-selections', version: 1, proof: DATA.id, title: DATA.title, client: $('who').value.trim(), sent: new Date().toISOString(), photos }; }
function refreshCode() { const p = payload(); $('code').value = JSON.stringify(p); $('summary').textContent = `${p.photos.filter((s) => s.pick).length} picked, ${p.photos.filter((s) => s.reject).length} rejected, ${p.photos.filter((s) => (s.comment || '').trim()).length} with comments.`; }
$('send').onclick = () => { refreshCode(); $('sendDlg').showModal(); };
$('who').addEventListener('input', refreshCode);
$('copy').onclick = async () => { refreshCode(); try { await navigator.clipboard.writeText($('code').value); $('copy').textContent = 'Copied'; } catch (e) { $('code').select(); } };
$('save').onclick = () => { if (!$('who').value.trim()) { $('who').focus(); return; } refreshCode(); const blob = new Blob([$('code').value], { type: 'application/json' }); const a = document.createElement('a');
  a.href = URL.createObjectURL(blob); a.download = `selections-${DATA.title.replace(/[^\w-]+/g, '_')}-${$('who').value.trim().replace(/[^\w-]+/g, '_')}.json`; document.body.appendChild(a); a.click(); a.remove(); };
build();
</script></body></html>"""


def write(ids: list[int], folder: Path, title: str, note: str = "", size: int = 1600, names: bool = False, progress: Callable[..., Any] | None = None, limit: int = 0) -> dict:
    cat = catalog_mod.get()
    proof_id = secrets.token_hex(6)
    (folder / "images" / "thumb").mkdir(parents=True, exist_ok=True)
    (folder / "images" / "large").mkdir(parents=True, exist_ok=True)
    photos = []
    for i, pid in enumerate(ids):
        r = cat.row("SELECT file_name, content_hash FROM photos WHERE id=?", (pid,))
        if r is None:
            continue
        n = len(photos) + 1
        for kind, long in (("thumb", 480), ("large", int(size))):
            out = export.render_photo(pid, {"resize": True, "mode": "long", "value": long}, "srgb")
            (folder / "images" / kind / f"{n:04d}.jpg").write_bytes(encode.encode(out, "jpeg", "srgb", 84, 8, 72, {}))
        photos.append({"key": key_of(pid, r["content_hash"] or ""), "label": html.escape(Path(r["file_name"]).stem if names else f"{n:03d}"),
                       "thumb": f"images/thumb/{n:04d}.jpg", "large": f"images/large/{n:04d}.jpg"})
        if progress is not None:
            if getattr(progress, "cancelled", False):
                break
            progress(i + 1, len(ids), f"Photo {i + 1} of {len(ids)}")
    data = {"format": FORMAT, "version": 1, "id": proof_id, "title": title, "photos": photos, "limit": max(int(limit or 0), 0)}
    page = PAGE.replace("__DATA__", json.dumps(data).replace("</", "<\\/")).replace("__TITLE__", html.escape(title)).replace(
        "__NOTE__", html.escape(note or "Click a photo to see it large. Mark the ones you like with Pick, add stars or a comment, then press Send my selections."))
    (folder / "index.html").write_text(page, encoding="utf-8")
    proofs = cat.get_meta("proofs", {}) or {}
    proofs[proof_id] = {"title": title, "created": catalog_mod.now_iso(), "folder": str(folder), "ids": ids[:len(photos)]}
    with cat.change("Proofing Gallery", undoable=False) as ch:
        ch.set_meta("proofs", proofs)
    return {"id": proof_id, "folder": str(folder), "index": str(folder / "index.html"), "photos": len(photos)}


def parse(text: str) -> dict:
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise ValueError("That is not a selections file from a formlit proofing gallery") from exc
    if not isinstance(data, dict) or data.get("format") != "formlit-proof-selections" or not isinstance(data.get("photos"), list):
        raise ValueError("That is not a selections file from a formlit proofing gallery")
    return data


def apply(data: dict, flags: bool = True, ratings: bool = True) -> dict:
    cat = catalog_mod.get()
    proof = (cat.get_meta("proofs", {}) or {}).get(str(data.get("proof")))
    client = str(data.get("client") or "Client").strip()[:80] or "Client"
    title = str(data.get("title") or (proof or {}).get("title") or "Proof")
    keys = {}
    for r in cat.rows("SELECT id, content_hash FROM photos"):
        keys[key_of(int(r["id"]), r["content_hash"] or "")] = int(r["id"])
    found, missing, picked, rejected, rated, commented = [], 0, [], [], 0, 0
    with cat.change(f"Client Selections: {client}") as ch:
        for s in data["photos"]:
            pid = keys.get(str(s.get("key")))
            if pid is None:
                missing += 1
                continue
            found.append(pid)
            fields: dict = {}
            if flags and s.get("pick"):
                fields["flag"] = 1
                picked.append(pid)
            elif flags and s.get("reject"):
                fields["flag"] = -1
                rejected.append(pid)
            if ratings and isinstance(s.get("rating"), int) and 1 <= s["rating"] <= 5:
                fields["rating"] = int(s["rating"])
                rated += 1
            text = str(s.get("comment") or "").strip()[:2000]
            if text:
                meta = loads(cat.scalar("SELECT meta FROM photos WHERE id=?", (pid,)), {})
                notes = [c for c in meta.get("clientComments", []) if not (c.get("proof") == data.get("proof") and c.get("author") == client)]
                notes.append({"author": client, "text": text, "time": str(data.get("sent") or catalog_mod.now_iso()), "proof": str(data.get("proof") or ""), "title": title})
                meta["clientComments"] = notes
                fields["meta"] = meta
                commented += 1
            if fields:
                ch.update("photos", pid, **fields)
    collection = None
    chosen = picked or [pid for pid in found if pid not in rejected]
    if chosen:
        from app.engine.cmd_library import collection_create
        collection = collection_create(f"Proof: {title} ({client})", "collection", None, chosen).get("id")
    return {"client": client, "title": title, "matched": len(found), "missing": missing, "picked": len(picked), "rejected": len(rejected), "rated": rated,
            "commented": commented, "collection": collection, "known": proof is not None}


def comment_threads(pid: int) -> list[dict]:
    cat = catalog_mod.get()
    meta = loads(cat.scalar("SELECT meta FROM photos WHERE id=?", (pid,)), {})
    by: dict[str, list] = {}
    for c in meta.get("clientComments", []) or []:
        by.setdefault(str(c.get("title") or "Proof"), []).append({"author": str(c.get("author") or "Client"), "text": str(c.get("text") or ""), "time": str(c.get("time") or "")})
    return [{"collection": 0, "name": f"Client proofing: {t}", "comments": cs, "error": ""} for t, cs in by.items()]
