"""treg: live external data in every Waku Agent, not only the hosted ones.

treg is an MCP server at https://treg.to/mcp/ with thousands of endpoints
behind it: search results, company and people data, social profiles, ads,
web pages. A hosted Waku Agent reaches it through the platform's relay
(hosted/core/provision.py writes that entry; spec 004 E). On your own machine
it is your own treg account, signed in once in your browser, and treg bills
that account directly.

`waku connect treg` (or `/connect treg` in the dashboard chat) adds the server
to WAKU_HOME/mcp.json next to any servers already there, then opens treg's
sign-in page, exactly as `waku connect waku-memory` does for Waku Memory. Its
tools then load like any MCP server's, named `treg_*`.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

NAME = "treg"
URL = "https://treg.to/mcp/"
DOCS = "https://treg.to"
WHAT = "Live data for research: search, companies, people, social, ads and the web."


def _has_mcp() -> bool:
    return importlib.util.find_spec("mcp") is not None


def _same_url(spec: dict) -> bool:
    return spec.get("url", "").rstrip("/") == URL.rstrip("/")


def _servers(home: Path) -> list[dict]:
    config = home / "mcp.json"
    if not config.exists():
        return []
    servers = json.loads(config.read_text(encoding="utf-8")).get("servers", [])
    return [s for s in servers if isinstance(s, dict)]


def add_server(home: Path) -> tuple[str, dict]:
    """Make sure mcp.json names treg, and say what that took.

    Returns (status, server spec). Status is "added", "present" (already
    there, under any name) or "conflict" (a server named treg points
    somewhere else on purpose -- a hosted container's relay is one -- so it is
    left alone).
    """
    config = home / "mcp.json"
    data = json.loads(config.read_text(encoding="utf-8")) if config.exists() else {}
    servers = data.setdefault("servers", [])

    for spec in servers:
        if _same_url(spec):
            return "present", spec
    for spec in servers:
        if spec.get("name") == NAME:
            return "conflict", spec

    spec = {"name": NAME, "url": URL, "oauth": True}
    servers.append(spec)
    home.mkdir(parents=True, exist_ok=True)
    config.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return "added", spec


def state(home: Path) -> tuple[str, str]:
    """Where treg stands: "connected", "not_signed_in" or "not_added", and a
    detail line. Files only, so the Connections page can ask on every poll
    and never opens a browser.

    The server is the one at URL, or the one named treg wherever it points:
    a hosted container's relay entry carries the platform token in auth_env,
    and that is connected.
    """
    try:
        servers = _servers(home)
    except (OSError, ValueError, AttributeError):
        return "not_added", f"{home / 'mcp.json'} is not valid JSON"
    spec = (next((s for s in servers if _same_url(s)), None)
            or next((s for s in servers if s.get("name") == NAME), None))
    if spec is None:
        return "not_added", ""
    if spec.get("auth_env"):
        return "connected", f"using the key in ${spec['auth_env']}"
    if not spec.get("oauth"):
        return "connected", ""
    if not _has_mcp():
        return "not_signed_in", "needs the mcp extra: pip install 'waku-agent[mcp]'"

    from waku.tools.mcp_cli import _auth_file, _identity

    token = _auth_file(home, spec["name"])
    if not token.exists():
        return "not_signed_in", ""
    return "connected", f"as {_identity(token)}"


def card(home: Path) -> dict:
    """treg's card on the dashboard's Connections page."""
    where, detail = state(home)
    return {"key": NAME, "name": "treg", "group": "Search & Observability",
            "what": WHAT, "state": where, "detail": detail}


def status(home: Path) -> str:
    """One line for `waku connections`."""
    where, detail = state(home)
    line = {"connected": "connected", "not_signed_in": "configured · not signed in",
            "not_added": "not connected"}[where]
    if detail:
        line += f" · {detail}"
    if where != "connected":
        line += " · run: waku connect treg"
    return line


def connect(home: Path) -> str:
    if not _has_mcp():
        return ("treg connects over MCP, which needs an extra: "
                "pip install 'waku-agent[mcp]' (in a checkout: pip install -e '.[mcp]'). "
                "Then run this again.")

    added, spec = add_server(home)
    name, config = spec["name"], home / "mcp.json"
    if added == "conflict":
        return (f"'{name}' in {config} already points at {spec.get('url')}, not {URL}. "
                "Change it there if you meant your own treg account.")

    done = f"Added treg to {config}. " if added == "added" else ""
    if spec.get("auth_env"):
        return (f"{done}treg is set up as '{name}', using the key in "
                f"${spec['auth_env']}. Restart Waku to load its tools.")

    from waku.tools.mcp_cli import _auth_file, _identity, sign_in

    token = _auth_file(home, name)
    if token.exists() and added == "present":
        return (f"treg is already connected as {_identity(token)}. "
                f"To switch accounts: waku mcp login {name}.")

    ok, message = sign_in(home, name)
    if not ok:
        return f"{done}{message.strip()} Help: {DOCS}"
    return (f"{done}Connected to treg as {_identity(token)}. "
            f"Restart Waku to load its tools (treg_*). treg bills your own account.")
