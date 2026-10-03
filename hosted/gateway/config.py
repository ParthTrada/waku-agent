"""Every value config/gateway.env carries, and nothing else.

PINNED IN BOTH DIRECTIONS, the way hosted/spawner/template.ENV_NAMES is:
config_from_env raises on a missing required name, and
test_gateway.py::test_the_example_file_and_the_config_agree asserts that
hosted/deploy/gateway.env.example names exactly these and no others. Without
the second half a misspelling in F1's install.sh is silent -- the operator
sets a value and the gateway ignores it.

THE SUPABASE VALUES ARE PUBLIC. The JWKS holds one ES256 public key and the
publishable key is meant for a browser. The gateway holds no Supabase secret
at all, which is why config/gateway.env can be read by the gateway's user
without that being a hole: there is nothing in it that is not already on the
wire to every visitor.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

# The live project's audience. It is NOT "authenticated": that is the `role`
# claim. See hosted/gateway/identity.py's docstring.
DEFAULT_AUDIENCE = "https://api.waku.one/mcp"

REQUIRED_ENV_NAMES = (
    "WAKU_APEX_HOST",
    "WAKU_GATEWAY_BIND",
    "WAKU_GATEWAY_PORT",
    "WAKU_CONTROL_DB",
    "WAKU_SPAWNER_SOCKET",
    "WAKU_GATEWAY_SOCKET",
    "WAKU_PROXY_SOCKET",
    "WAKU_ADMIN_SOCKET",
    "WAKU_MAX_RUNNING",
    "WAKU_SUPABASE_URL",
    "WAKU_SUPABASE_ISSUER",
    "WAKU_SUPABASE_JWKS_URL",
    "WAKU_SUPABASE_AUDIENCE",
    "WAKU_SUPABASE_PUBLISHABLE_KEY",
    # Read by hosted.core.quota.plans_from_env, which has its own defaults (30
    # and 120) -- and REQUIRED anyway. An earlier draft made these two
    # optional on the reasoning that the code works without them. That is the
    # reasoning REQUIRED_ENV_NAMES exists to refuse: `WAKU_FRE_TURNS_PER_HOUR`
    # in install.sh would set nothing, raise nothing, and silently run the
    # whole VM on the default. The example-file pin catches a name missing
    # from the file; only this catches a name misspelt in the file.
    "WAKU_FREE_TURNS_PER_HOUR",
    "WAKU_BYOK_TURNS_PER_HOUR",
    # Spec 008 D: the pages allowed to frame the agent's chat. In
    # MAY_BE_ABSENT below.
    "WAKU_EMBED_ORIGINS",
)

# WRITTEN BY install.sh, PINNED LIKE THE REST, AND STILL ALLOWED TO BE ABSENT,
# on the proxy's precedent for its treg names (hosted/proxy/config.py).
# upgrade.sh never writes config/, so a gateway.env written before spec 008
# has no WAKU_EMBED_ORIGINS line, and a gateway that refused to start without
# it would take every tenant down on the upgrade that added the embedded chat.
# Absent or empty, the allowlist is DEFAULT_EMBED_ORIGINS.
MAY_BE_ABSENT = frozenset({"WAKU_EMBED_ORIGINS"})

# waku.one's three hosts. http://localhost:3000, for developing waku.one's own
# page against a real gateway, is never in the default: an operator who wants
# it writes the whole list, that origin included.
DEFAULT_EMBED_ORIGINS = ("https://www.waku.one", "https://waku.one",
                         "https://dev.waku.one")

# ONE ORIGIN, AND NOTHING THAT IS NOT AN ORIGIN. Every value lands verbatim in
# a Content-Security-Policy header and in a postMessage target, so a path, a
# wildcard, a quote or a semicolon is refused at startup rather than becoming
# a second directive. https for any host; plain http only for loopback, which
# is what a developer's own waku.one runs on.
_EMBED_ORIGIN = re.compile(
    r"https://[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+(?::[0-9]{1,5})?"
    r"|http://(?:localhost|127\.0\.0\.1)(?::[0-9]{1,5})?")


def embed_origins_from(raw: str | None) -> tuple[str, ...]:
    """WAKU_EMBED_ORIGINS as a tuple of origins, or the default when it is
    absent or empty. Separated by spaces, the way a CSP source list is, or by
    commas; a value that is not one exact origin raises."""
    values = tuple(v for v in re.split(r"[\s,]+", (raw or "").strip()) if v)
    if not values:
        return DEFAULT_EMBED_ORIGINS
    bad = [v for v in values if not _EMBED_ORIGIN.fullmatch(v)]
    if bad:
        raise ValueError(
            f"WAKU_EMBED_ORIGINS holds {bad}, which are not origins. Write each "
            "as https://host (or http://localhost:<port>), lowercase, with no "
            "path, separated by spaces.")
    return values


@dataclass(frozen=True)
class GatewayConfig:
    apex_host: str
    bind_host: str
    port: int
    control_db: Path
    spawner_socket: Path
    gateway_socket: Path
    proxy_socket: Path
    admin_socket: Path
    max_running: int
    supabase_url: str
    supabase_issuer: str
    supabase_jwks_url: str
    supabase_audience: str
    supabase_publishable_key: str
    # Defaulted so every place that builds a GatewayConfig by hand -- the
    # tests, the Docker tier -- gets the documented allowlist without naming it.
    embed_origins: tuple[str, ...] = DEFAULT_EMBED_ORIGINS


def config_from_env(env: Mapping[str, str]) -> GatewayConfig:
    missing = [name for name in REQUIRED_ENV_NAMES
               if name not in MAY_BE_ABSENT and not env.get(name)]
    if missing:
        raise ValueError(
            f"config/gateway.env is missing {missing}. install.sh writes this "
            "file; every name in config.REQUIRED_ENV_NAMES must be in it.")
    return GatewayConfig(
        apex_host=env["WAKU_APEX_HOST"].strip().lower(),
        bind_host=env["WAKU_GATEWAY_BIND"],
        port=int(env["WAKU_GATEWAY_PORT"]),
        control_db=Path(env["WAKU_CONTROL_DB"]),
        spawner_socket=Path(env["WAKU_SPAWNER_SOCKET"]),
        gateway_socket=Path(env["WAKU_GATEWAY_SOCKET"]),
        proxy_socket=Path(env["WAKU_PROXY_SOCKET"]),
        admin_socket=Path(env["WAKU_ADMIN_SOCKET"]),
        max_running=int(env["WAKU_MAX_RUNNING"]),
        supabase_url=env["WAKU_SUPABASE_URL"].rstrip("/"),
        supabase_issuer=env["WAKU_SUPABASE_ISSUER"].rstrip("/"),
        supabase_jwks_url=env["WAKU_SUPABASE_JWKS_URL"],
        supabase_audience=env["WAKU_SUPABASE_AUDIENCE"],
        supabase_publishable_key=env["WAKU_SUPABASE_PUBLISHABLE_KEY"],
        embed_origins=embed_origins_from(env.get("WAKU_EMBED_ORIGINS")),
    )
