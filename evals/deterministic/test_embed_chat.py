"""DETERMINISTIC EVAL -- the chat column alone, for waku.one to frame (spec 008).

The container's half of the embedded chat:

  A. GET /embed/chat serves the dashboard's chat column and nothing else of
     the dashboard, with the allowlist the gateway sent it (or the default).
  B. The `report` event draws a card with "Open report", and a
     `consolidation` event's `kept` lists the facts, in the dashboard's chat
     too -- rendered here from recorded events, in node.
  F. The page posts to window.parent only with the framing page's origin as
     the target, only when that origin is on its allowlist, and never "*".

The gateway's half (codes, cookie, framing headers, the 403s) is in
evals/deterministic/hosted/test_embed.py. CI has no browser; the JavaScript
runs in node against a stub DOM, and skips where node is absent, like
test_static_js_parses.py.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from evals.helpers import ScriptedClient, make_waku
from waku.ops import browser_agent, dashboard

STATIC = Path(__file__).resolve().parents[2] / "waku" / "ops" / "static"
EMBED = (STATIC / "embed.html").read_text(encoding="utf-8")
JS = STATIC / "js"
DEFAULT = "https://www.waku.one https://waku.one https://dev.waku.one"
NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="node not installed")

# A turn that saved a report and kept one fact, as /api/chat/stream sends it.
REPORT = {"kind": "report", "title": "Mem0 competitors, 2026-10-03",
          "memory_id": "mem-7f3a", "scope": "project:Company brain",
          "summary": ["Zep raised $12M.", "Letta ships a hosted tier.",
                      "Supermemory is open source.", "A fourth bullet is never shown."]}
KEPT = {"kind": "consolidation", "new_facts": 1,
        "kept": [{"subject": "mem0", "content": "Mem0 raised a Series A in 2026.",
                  "project": "Company brain", "memory_id": "mem-91c0"}]}
DONE = {"kind": "done", "reply": "Three findings. Report saved.", "tools": [],
        "gate": None, "iterations": 2, "latency_ms": 900, "model": "m",
        "report": {k: v for k, v in REPORT.items() if k != "kind"},
        "consolidation": {k: v for k, v in KEPT.items() if k != "kind"}}


# --- A. the page --------------------------------------------------------------


def test_the_page_is_the_chat_column_and_nothing_else():
    for needed in ('id="dock"', 'id="docklog"', 'id="dmsg"', 'id="dsend"',
                   'id="modelchip"', 'id="teletoggle"', "newChat()",
                   "toggleSessMenu(event)", "toggleTele()", "toggleModelMenu(event)"):
        assert needed in EMBED, needed
    for absent in ('id="nav"', "<main", 'id="view"', "#compare", "#judgment",
                   "#settings", "#database", 'id="mic"', 'id="dock-close"'):
        assert absent not in EMBED, f"{absent} is the dashboard's, not the chat's"


def test_the_page_loads_the_chat_scripts_and_no_view():
    scripts = re.findall(r'<script src="/static/js/([a-z]+\.js)"></script>', EMBED)
    assert scripts == ["util.js", "theme.js", "ui.js", "render.js", "dock.js", "embed.js"]
    assert not re.search(r"<script>", EMBED), "no inline script: the page runs only its files"
    for ref in re.findall(r'(?:src|href)="(/static/[^"]+)"', EMBED):
        assert (STATIC / ref[len("/static/"):]).is_file(), ref


def test_the_page_carries_the_allowlist_it_was_served_with():
    assert 'data-embed-origins="@@EMBED_ORIGINS@@"' in EMBED
    page = dashboard.embed_page(None).decode()
    assert f'data-embed-origins="{DEFAULT}"' in page
    told = dashboard.embed_page("https://dev.waku.one http://localhost:3000").decode()
    assert 'data-embed-origins="https://dev.waku.one http://localhost:3000"' in told
    forged = dashboard.embed_page('https://dev.waku.one "><script>x</script> *').decode()
    assert 'data-embed-origins="https://dev.waku.one"' in forged
    assert "<script>x" not in forged


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("WAKU_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(browser_agent, "_dashboard_session", "s-20261003-091500")
    app = make_waku(tmp_path / "home", client=ScriptedClient([]))
    app.conn.execute("INSERT INTO chat_log (role, content, session_id, source) "
                     "VALUES ('user', 'who competes with mem0?', 's-20261003-091500', 'dashboard')")
    app.conn.commit()
    return app


@pytest.fixture
def server(home):
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), dashboard.Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


def _get(url: str, headers: dict | None = None) -> tuple[str, bytes]:
    request = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(request, timeout=10) as response:
        return response.headers.get("Content-Type"), response.read()


def test_localhost_serves_the_embed_page(server):
    kind, body = _get(server + "/embed/chat")
    assert kind.startswith("text/html")
    assert f'data-embed-origins="{DEFAULT}"'.encode() in body
    _, told = _get(server + "/embed/chat", {"X-Waku-Embed-Origins": "https://dev.waku.one"})
    assert b'data-embed-origins="https://dev.waku.one"' in told


def test_the_header_state_is_the_chats_and_no_more(server):
    """The embed reads this instead of /api/data, which an embed session is
    refused: the conversations, the current one, the model and the pins."""
    _, body = _get(server + "/api/session?action=state")
    state = json.loads(body)
    assert set(state) == {"ok", "sessions", "current_session", "settings"}
    assert state["current_session"] == "s-20261003-091500"
    assert [s["id"] for s in state["sessions"]] == ["s-20261003-091500"]
    assert set(state["settings"]) == {"provider", "model", "small_model", "pinned",
                                      "disabled_providers"}


# --- B and F, run in node ----------------------------------------------------------

# A stub DOM just wide enough for the chat's scripts to load and run: nothing
# here renders, the tests read the HTML strings the renderers return.
_STUB = r"""
const vm = require("vm");
const fs = require("fs");
const posts = [];
const ctx = {console, URL, TextEncoder, TextDecoder, setTimeout, clearTimeout,
             setInterval, clearInterval, JSON, Promise, Set, Date, Math};
ctx.window = ctx;
ctx.parent = SETUP.framed ? {postMessage: (m, o) => posts.push({message: m, origin: o})} : ctx;
ctx.document = {referrer: SETUP.referrer,
  body: {dataset: {embedOrigins: SETUP.origins}, classList: {contains: () => true,
         toggle(){}}},
  getElementById: () => null, querySelectorAll: () => [],
  documentElement: {dataset: {}}};
ctx.localStorage = {getItem: () => null, setItem(){}};
ctx.MutationObserver = class { observe(){} };
const sse = evs => evs.map(e => "data: " + JSON.stringify(e) + "\n\n").join("");
ctx.fetch = async (url) => {
  if (String(url).startsWith("/api/session?action=state"))
    return {ok: SETUP.state === 200, status: SETUP.state,
            headers: {get: () => "application/json"},
            json: async () => ({sessions: [], settings: {}, current_session: null})};
  const bytes = new TextEncoder().encode(sse(SETUP.events));
  let sent = false;
  return {ok: true, status: 200, headers: {get: () => "text/event-stream"},
          body: {getReader: () => ({read: async () => sent ? {done: true}
                   : (sent = true, {value: bytes, done: false})})}};
};
vm.createContext(ctx);
for (const f of SETUP.files) vm.runInContext(fs.readFileSync(f, "utf8"), ctx, {filename: f});
"""


def _node(setup: dict, body: str) -> dict:
    program = f"const SETUP = {json.dumps(setup)};\n{_STUB}\n(async () => {{\n{body}\n}})();"
    out = subprocess.run([NODE, "-e", program], capture_output=True, text=True,  # noqa: S603
                         timeout=30, check=False)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])


def _files(*names: str) -> list[str]:
    return [str(JS / name) for name in names]


CHAT_FILES = _files("util.js", "ui.js", "render.js")


@needs_node
def test_the_report_card_renders_from_a_recorded_report_event():
    got = _node({"files": CHAT_FILES, "referrer": "", "origins": DEFAULT, "framed": False,
                 "events": [], "state": 200}, f"""
    const pending = {{role: "waku", pending: true, stream: ""}};
    for (const ev of {json.dumps([REPORT, KEPT, DONE])})
      vm.runInContext("applyStreamEvent", ctx)(pending, ev);
    const card = vm.runInContext("chatTurnCard", ctx)(pending);
    const reopened = vm.runInContext("chatTurnCard", ctx)(vm.runInContext("histItem", ctx)(
      {{role: "assistant", content: "Report saved.", meta: {{report: {json.dumps(DONE["report"])}}}}}));
    console.log(JSON.stringify({{card, reopened}}));""")
    card = got["card"]
    assert "Mem0 competitors, 2026-10-03" in card
    for bullet in REPORT["summary"][:3]:
        assert bullet in card
    assert REPORT["summary"][3] not in card, "three bullets at most"
    assert 'href="https://www.waku.one/memories/mem-7f3a"' in card and ">Open report</a>" in card
    assert "Kept in memory" in card and "Mem0 raised a Series A in 2026." in card
    assert 'href="https://www.waku.one/memories/mem-91c0"' in card
    assert "Open report" in got["reopened"], "a reopened thread draws the card from its meta"


@needs_node
def test_framed_the_report_opens_on_the_site_that_framed_it():
    got = _node({"files": CHAT_FILES, "referrer": "", "origins": DEFAULT, "framed": False,
                 "events": [], "state": 200}, f"""
    vm.runInContext("var embedParentOrigin = () => 'https://dev.waku.one';", ctx);
    const card = vm.runInContext("reportCard", ctx)({json.dumps(DONE["report"])});
    console.log(JSON.stringify({{card}}));""")
    assert 'href="https://dev.waku.one/memories/mem-7f3a"' in got["card"]


@needs_node
def test_the_report_card_escapes_what_the_model_wrote():
    got = _node({"files": CHAT_FILES, "referrer": "", "origins": DEFAULT, "framed": False,
                 "events": [], "state": 200}, """
    const card = vm.runInContext("reportCard", ctx)({title: '<img src=x onerror=alert(1)>',
      memory_id: '"><script>', summary: ['<b>x</b>']});
    console.log(JSON.stringify({card}));""")
    assert "<img" not in got["card"] and "<script>" not in got["card"] and "<b>x" not in got["card"]


def _embed_run(referrer: str, framed: bool, *, state: int = 200) -> list[dict]:
    """Load the embed page's scripts (dock.js and theme.js stubbed: they only
    touch the DOM), send one message, and answer what was posted."""
    setup = {"files": CHAT_FILES, "referrer": referrer, "origins": DEFAULT,
             "framed": framed, "events": [REPORT, KEPT, DONE], "state": state}
    return _node(setup, f"""
    vm.runInContext(`
      function applyTheme(){{}} function currentTheme(){{ return "system"; }}
      function syncModelChip(){{}} function applyTele(){{}}
      async function loadThreadInto(){{ return null; }}`, ctx);
    vm.runInContext(fs.readFileSync({json.dumps(str(JS / "embed.js"))}, "utf8"), ctx);
    await new Promise(r => setTimeout(r, 0));
    await vm.runInContext("sendChat", ctx)({{value: "who competes with mem0?",
      tagName: "TEXTAREA_STUB", focus(){{}}}});
    console.log(JSON.stringify(posts));""")


@needs_node
def test_a_framed_chat_tells_its_allowlisted_parent_and_no_one_else():
    posts = _embed_run("https://dev.waku.one/agent?tab=chat", framed=True)
    assert posts == [
        {"message": {"source": "waku-agent", "type": "report-saved",
                     "memory_id": "mem-7f3a", "title": "Mem0 competitors, 2026-10-03"},
         "origin": "https://dev.waku.one"},
        {"message": {"source": "waku-agent", "type": "turn-done", "credits_changed": True},
         "origin": "https://dev.waku.one"},
    ]


@needs_node
@pytest.mark.parametrize(("referrer", "framed"), [
    ("https://evil.example/", True),
    ("https://dev.waku.one.evil.example/", True),
    ("", True),
    ("https://dev.waku.one/agent", False),
], ids=["foreign-parent", "lookalike", "no-referrer", "not-framed"])
def test_nothing_is_posted_to_a_parent_off_the_allowlist(referrer, framed):
    assert _embed_run(referrer, framed) == []


@needs_node
def test_an_ended_session_is_told_once():
    posts = _embed_run("https://www.waku.one/", framed=True, state=401)
    expired = [p for p in posts if p["message"]["type"] == "session-expired"]
    assert expired == [{"message": {"source": "waku-agent", "type": "session-expired"},
                        "origin": "https://www.waku.one"}]


def test_no_script_posts_to_star():
    """Spec 008 F: postMessage never uses "*". Every call in the chat's
    scripts and in the gateway's signed-out page names its target."""
    sources = {p.name: p.read_text(encoding="utf-8") for p in JS.glob("*.js")}
    hosted = Path(__file__).resolve().parents[2] / "hosted" / "gateway" / "embed.py"
    if hosted.is_file():
        sources["embed.py"] = hosted.read_text(encoding="utf-8")
    calls = {name: re.findall(r"postMessage\(([^;]*)\)", src) for name, src in sources.items()}
    assert calls.get("embed.js"), "embed.js no longer posts at all; this guard protects nothing"
    for name, found in calls.items():
        for call in found:
            assert not re.search(r"""['"`]\*['"`]""", call), f"{name}: postMessage({call})"
