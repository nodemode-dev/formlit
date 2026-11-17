import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import pytest

WINDOW_DIR = Path(__file__).resolve().parent
REPO = WINDOW_DIR.parents[2]

APP_ID = "formlit"
ENGINE_DIR = REPO / "backend"
ENGINE_CMD = [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "{port}"]
ENGINE_ENV = {"FORMLIT_DATA_DIR": "{data}", "FORMLIT_PORT": "{port}", "FORMLIT_DIST": "{dist}"}
CLEAR_ENV_PREFIX = "FORMLIT_"
DIST = REPO / "frontend" / "dist"
HEALTH_PATH = "/api/health"
PAGES = ["/", "/splash.html"]
SETTLE_MS = 3000
CLS_LIMIT = 0.0
IGNORED_REQUESTS = []

CPU_SLOWDOWN = 4
NETWORK = {"offline": False, "latency": 150, "downloadThroughput": 1_600_000 / 8, "uploadThroughput": 750_000 / 8}

CLS_PROBE = """
window.__cls = 0;
window.__shifts = [];
new PerformanceObserver((list) => {
  for (const e of list.getEntries()) {
    if (e.hadRecentInput) continue;
    window.__cls += e.value;
    const who = (e.sources || []).map((s) => s.node ? `${s.node.nodeName}.${String(s.node.className || '').trim().split(/\\s+/)[0]}` : '?');
    window.__shifts.push(`${Math.round(e.startTime)}ms ${e.value.toExponential(2)} ${who.join(',')}`);
  }
}).observe({ type: 'layout-shift', buffered: true });
"""


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def engine():
    assert (DIST / "index.html").is_file(), f"build the window first: {DIST} has no index.html (npm run build)"
    port = free_port()
    sandbox = Path(tempfile.mkdtemp(prefix=f"{APP_ID}-window-"))
    (sandbox / "data").mkdir()
    (sandbox / "home").mkdir()
    values = {"port": str(port), "data": str(sandbox / "data"), "dist": str(DIST)}
    env = {k: v for k, v in os.environ.items() if not k.startswith(CLEAR_ENV_PREFIX)}
    env.update({k: v.format(**values) for k, v in ENGINE_ENV.items()})
    env["HOME"] = str(sandbox / "home")
    proc = subprocess.Popen([a.format(**values) for a in ENGINE_CMD], cwd=ENGINE_DIR, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline and proc.poll() is None:
        try:
            with urllib.request.urlopen(base + HEALTH_PATH, timeout=2) as r:
                if r.status == 200:
                    break
        except OSError:
            time.sleep(0.25)
    else:
        proc.kill()
        out = proc.communicate(timeout=5)[0].decode("utf-8", "replace")
        raise RuntimeError(f"engine did not answer {HEALTH_PATH}:\n{out[-4000:]}")
    yield base
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
    shutil.rmtree(sandbox, ignore_errors=True)


def ignored(url):
    return any(part in url for part in IGNORED_REQUESTS)


@pytest.mark.parametrize("path", PAGES)
def test_window_loads_throttled_without_shift_errors_or_refusals(engine, path):
    from playwright.sync_api import sync_playwright

    errors, failed = [], []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.add_init_script(CLS_PROBE)
        cdp = page.context.new_cdp_session(page)
        cdp.send("Emulation.setCPUThrottlingRate", {"rate": CPU_SLOWDOWN})
        cdp.send("Network.enable")
        cdp.send("Network.emulateNetworkConditions", NETWORK)
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("requestfailed", lambda r: failed.append(f"{r.url} {r.failure}") if not ignored(r.url) else None)
        page.on("response", lambda r: failed.append(f"{r.url} {r.status}") if r.status >= 400 and not ignored(r.url) else None)
        page.goto(engine + path, wait_until="load", timeout=120_000)
        page.wait_for_load_state("networkidle", timeout=120_000)
        page.wait_for_timeout(SETTLE_MS)
        cls = page.evaluate("window.__cls")
        shifts = page.evaluate("window.__shifts")
        title = page.title()
        browser.close()
    assert title, "the window has a title"
    assert not [f for f in failed if " 403" in f], f"requests refused by the guard: {failed}"
    assert not failed, f"failed requests: {failed}"
    assert not errors, f"console errors: {errors}"
    assert cls <= CLS_LIMIT, f"layout shift {cls}: {shifts}"


def command(base, cid, params):
    req = urllib.request.Request(f"{base}/api/commands/{cid}", data=json.dumps(params).encode(), headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))["result"]


def test_develop_returning_to_the_open_photo_cancels_the_pending_switch(engine, tmp_path):
    """0.51.3: A to B to A while A's edit was still being saved let B's open finish last, so the next edit went to B."""
    from PIL import Image
    from playwright.sync_api import sync_playwright

    paths = []
    for i, shade in enumerate((60, 120, 180)):
        path = tmp_path / f"switch_{i}.jpg"
        Image.new("RGB", (64, 48), (shade, shade, shade)).save(path, "JPEG")
        paths.append(str(path))
    command(engine, "library.import", {"paths": paths, "mode": "add", "wait": True})
    held, opened, updates = [], [], []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})

        def seen(r):
            if r.url.endswith("/api/commands/develop.get"):
                opened.append(json.loads(r.post_data)["id"])
            if r.url.endswith("/api/commands/develop.update"):
                updates.append(json.loads(r.post_data)["ids"])

        page.on("request", seen)
        page.goto(engine + "/", wait_until="load", timeout=120_000)
        page.wait_for_load_state("networkidle", timeout=120_000)
        page.keyboard.press("d")
        page.locator(".fl-fs-head [data-cmd='photo.next']").first.click()
        page.wait_for_function("() => document.querySelectorAll('.fl-sl-track').length > 0", timeout=30_000)
        page.wait_for_load_state("networkidle", timeout=60_000)
        assert opened, "Develop opened no photo"
        first = opened[-1]
        track = page.locator(".fl-sl[data-id='light.exposure'] .fl-sl-track").first
        page.route("**/api/commands/develop.update", lambda route: held.append(route))
        track.focus()
        page.keyboard.press("ArrowRight")
        page.locator(".fl-fs-head [data-cmd='photo.next']").first.click()
        deadline = time.monotonic() + 10
        while not held and time.monotonic() < deadline:
            page.wait_for_timeout(50)
        assert held, "the switch did not save the edit first"
        page.locator(".fl-fs-head [data-cmd='photo.prev']").first.click()
        page.wait_for_timeout(300)
        for route in held:
            route.continue_()
        page.unroute("**/api/commands/develop.update")
        page.wait_for_load_state("networkidle", timeout=60_000)
        page.wait_for_timeout(500)
        before = len(updates)
        track.focus()
        page.keyboard.press("ArrowRight")
        deadline = time.monotonic() + 10
        while len(updates) == before and time.monotonic() < deadline:
            page.wait_for_timeout(50)
        browser.close()
    assert len(updates) > before, "the second edit was never saved"
    assert updates[-1] == [first], f"the edit after returning to photo {first} went to {updates[-1]} (opened: {opened})"


def open_develop(engine, page, tmp_path, name):
    from PIL import Image

    path = tmp_path / f"{name}.jpg"
    Image.new("RGB", (96, 64), (90, 140, 200)).save(path, "JPEG")
    command(engine, "library.import", {"paths": [str(path)], "mode": "add", "wait": True})
    page.goto(engine + "/", wait_until="load", timeout=120_000)
    page.wait_for_load_state("networkidle", timeout=120_000)
    page.keyboard.press("d")
    page.wait_for_function("() => document.querySelectorAll('.fl-sl-track').length > 0", timeout=30_000)
    page.wait_for_load_state("networkidle", timeout=60_000)


def renders_of(page):
    seen = []
    page.on("request", lambda r: seen.append(json.loads(r.post_data or "{}")) if r.url.endswith("/render") and r.method == "POST" else None)
    return seen


def test_alt_drag_on_sharpening_shows_its_view_and_release_restores(engine, tmp_path):
    """Review gap: holding Alt (Option) while dragging Masking showed nothing; it now shows the edge mask, Amount the sharpened luminance."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1400})
        open_develop(engine, page, tmp_path, "alt_sharpen")
        assert "while dragging a Sharpening slider" in page.locator(".fl-sharpen-hint").inner_text()
        seen = renders_of(page)
        for cid, mode in (("detail.sharpenMasking", "mask"), ("detail.sharpenAmount", "amount")):
            track = page.locator(f".fl-sl[data-id='{cid}'] .fl-sl-track").first
            track.scroll_into_view_if_needed()
            box = track.bounding_box()
            y = box["y"] + box["height"] / 2
            page.keyboard.down("Alt")
            page.mouse.move(box["x"] + box["width"] * 0.3, y)
            page.mouse.down()
            page.mouse.move(box["x"] + box["width"] * 0.6, y, steps=4)
            page.locator(".is-sharpen-view").first.wait_for(state="attached", timeout=10_000)
            page.wait_for_timeout(400)
            during = [b for b in seen if (b.get("overlay") or {}).get("sharpen") == mode]
            page.mouse.up()
            page.keyboard.up("Alt")
            page.wait_for_load_state("networkidle", timeout=60_000)
            page.wait_for_timeout(300)
            assert during, f"no render asked for the {mode} view: {seen[-3:]}"
            assert "sharpen" not in (seen[-1].get("overlay") or {}), f"the last render after release still had an overlay: {seen[-1]}"
            assert page.locator(".is-sharpen-view").count() == 0
        browser.close()


def test_missing_ai_model_offers_install_with_its_size(engine, tmp_path):
    """Review gap: Subject, Sky and Objects failed with 'not installed yet, Install it in Preferences'; the mask now offers Install Now, the recommended model first and the small one beside it."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        downloads = []
        page.on("request", lambda r: downloads.append(json.loads(r.post_data)) if r.url.endswith("/api/commands/ai.download") else None)
        open_develop(engine, page, tmp_path, "missing_model")
        page.keyboard.press("Shift+W")
        page.locator("[data-new='sky']").first.click()
        dialog = page.locator(".cv-scrim:not([hidden]) .cv-dialog")
        dialog.wait_for(timeout=30_000)
        assert "Install Now (176 MB)" in dialog.inner_text()
        dialog.get_by_role("button", name="Cancel").click()
        page.locator(".cv-toast", has_text="not installed yet").first.wait_for(timeout=10_000)
        assert not downloads
        page.route("**/api/commands/ai.download", lambda route: route.fulfill(status=500, content_type="application/json", body=json.dumps({"ok": False, "error": "offline in the test"})))
        page.locator("[data-new='subject']").first.click()
        dialog.wait_for(timeout=30_000)
        text = dialog.inner_text()
        assert "Install Now (224 MB)" in text and "BiRefNet" in text
        dialog.get_by_role("button", name="Small and Fast (176 MB)").click()
        page.locator(".cv-toast", has_text="offline in the test").first.wait_for(timeout=10_000)
        page.locator("[data-new='object']").first.click()
        page.wait_for_timeout(300)
        page.mouse.click(720, 450)
        dialog.wait_for(timeout=30_000)
        assert "Small and Fast (155 MB)" in dialog.inner_text()
        dialog.get_by_role("button", name="Install Now (328 MB)").click()
        deadline = time.monotonic() + 10
        while len(downloads) < 2 and time.monotonic() < deadline:
            page.wait_for_timeout(50)
        browser.close()
    assert downloads == [{"model": "subject"}, {"model": "objectsHq"}]


def test_lens_corrections_show_the_bundled_profiles_and_update_them(engine, tmp_path):
    """Lens profiles ship with formlit; Lens Corrections names the database in use and Update Lens Profiles runs the download as an updater."""
    from playwright.sync_api import sync_playwright

    asked = []

    def database(route):
        body = json.loads(route.request.post_data or "{}")
        asked.append(body)
        result = {"task": 987654} if body.get("download") else {"available": True, "lenses": 1, "source": "downloaded", "date": "2026-11-17"}
        route.fulfill(status=200, content_type="application/json", body=json.dumps({"ok": True, "command": "lens.database", "result": result, "revision": 0}))

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1400})
        open_develop(engine, page, tmp_path, "lens_update")
        row = page.locator(".fl-lens-db")
        row.scroll_into_view_if_needed()
        page.wait_for_function("() => /bundled with formlit \\(\\d{4}-\\d\\d-\\d\\d\\)/.test(document.querySelector('.fl-lens-db')?.textContent || '')", timeout=15_000)
        assert row.is_visible()
        page.route("**/api/commands/lens.database", database)
        row.get_by_role("button", name="Update Lens Profiles").click()
        page.wait_for_function("() => /Updating lens profiles/.test(document.querySelector('.fl-lens-db')?.textContent || '')", timeout=10_000)
        prompts = page.locator(".fl-toast-act", has_text="lens profiles").count()
        browser.close()
    assert {"download": True} in asked
    assert prompts == 0


def test_windows_card_drive_is_removable_for_import_and_eject(engine):
    """Review gap: the import dialog counted only kind 'volume' as removable, so a Windows card (kind 'drive') never offered Eject."""
    from playwright.sync_api import sync_playwright

    roots = {"roots": [{"name": "Home", "path": "C:\\Users\\me", "kind": "home"}, {"name": "C:", "path": "C:\\", "kind": "drive", "removable": False, "card": False},
                       {"name": "E:", "path": "E:\\", "kind": "drive", "removable": True, "card": True}], "library": "C:\\Users\\me\\Pictures"}

    def listing(route):
        path = route.request.url.split("path=", 1)[1]
        from urllib.parse import unquote
        route.fulfill(status=200, content_type="application/json", body=json.dumps({"path": unquote(path), "parent": None, "dirs": [], "files": []}))

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.route("**/api/files/roots", lambda route: route.fulfill(status=200, content_type="application/json", body=json.dumps(roots)))
        page.route("**/api/files/list?*", listing)
        page.route("**/api/commands/library.scan", lambda route: route.fulfill(status=200, content_type="application/json", body=json.dumps({"ok": True, "command": "library.scan", "result": {"files": [], "duplicates": 0}, "revision": 0})))
        page.goto(engine + "/", wait_until="load", timeout=120_000)
        page.wait_for_load_state("networkidle", timeout=120_000)
        page.keyboard.press("ControlOrMeta+Shift+I")
        eject = page.locator(".fl-imp-eject")
        eject.wait_for(state="attached", timeout=15_000)
        page.wait_for_function("() => document.querySelector('.fl-imp-row.is-on')?.dataset.path === 'E:\\\\'", timeout=15_000)
        visible = eject.is_visible()
        browser.close()
    assert visible, "Eject after import stayed hidden on a removable Windows drive"


LOCALES17 = REPO / "frontend" / "src" / "i18n" / "locales17"


@pytest.mark.parametrize("lang", ["de", "ja", "ru"])
def test_the_new_develop_strings_show_translated(engine, tmp_path, lang):
    """The Sharpening hint and the lens profile row read in the chosen language (keys17, locales17)."""
    from playwright.sync_api import sync_playwright

    keys = json.loads((LOCALES17.parent / "keys17.json").read_text(encoding="utf-8"))
    tr = json.loads((LOCALES17 / f"{lang}.json").read_text(encoding="utf-8"))
    hints = {tr[str(keys.index(f"Hold {k} while dragging a Sharpening slider to see what it changes; Masking shows the sharpened areas in white."))] for k in ("Alt", "Option")}
    update = tr[str(keys.index("Update Lens Profiles"))]
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.add_init_script(f"localStorage.setItem('formlit_lang', '{lang}')")
        open_develop(engine, page, tmp_path, f"lang_{lang}")
        page.wait_for_timeout(500)
        shown_hint = page.locator(".fl-sharpen-hint").inner_text()
        shown_update = page.locator(".fl-lens-db button").inner_text()
        browser.close()
    assert shown_hint in hints
    assert shown_update == update


def test_every_new_string_has_a_translation_in_each_catalog():
    keys = json.loads((LOCALES17.parent / "keys17.json").read_text(encoding="utf-8"))
    langs = sorted(p.stem for p in LOCALES17.glob("*.json"))
    assert len(langs) == 25
    for lang in langs:
        tr = json.loads((LOCALES17 / f"{lang}.json").read_text(encoding="utf-8"))
        assert sorted(tr) == sorted(str(i) for i in range(len(keys))), lang
        assert all(tr[str(i)].strip() and tr[str(i)] != k for i, k in enumerate(keys)), lang
