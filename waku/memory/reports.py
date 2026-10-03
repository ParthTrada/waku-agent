"""Research reports — a reply that holds one is saved to Waku Memory whole.

Spec 007. The research-report skill (skills/research-report/) teaches the
format, waku-report v1: one Markdown document whose first line is MARKER.
This module is the writer's half of that contract, and it does three things
once a turn has been answered:

  1. finds the report in the reply (MARKER on a line of its own),
  2. sends it to Waku Memory as one `semantic` memory, in the Company brain
     project when it is company or market research and `global` otherwise,
  3. hands back a short chat reply and a `report` event for the chat's card.

With no Waku Memory connected, or when the send fails, the reply is left
whole and there is no event: the report is never in neither place. Like
consolidation, this module never sees the transport; app.py passes the same
`remember` callable spec 006 built, so a fake stands in for it in the evals.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field

import anthropic

from waku.memory.consolidation import COMPANY_PROJECT

MARKER = "<!-- waku-report v1 -->"

# Waku Memory's kind for a report: waku.one files `semantic` under Knowledge,
# and a report is the thing another agent should recall whole.
KIND = "semantic"

SCOPE_PROMPT = """\
A research report's title and summary follow. Answer true when it is research
about a company or market (companies, competitors, products, prices, funding,
launches), and false when it is about the user's own life.

Reply with ONLY this JSON: {{"company_research": true}} or {{"company_research": false}}

Title: {title}
Summary:
{summary}"""

log = logging.getLogger(__name__)


@dataclass
class Report:
    preface: str          # what the reply said before the marker
    body: str             # the report itself, from the marker to the end
    title: str
    summary: list[str] = field(default_factory=list)


def find(reply: str) -> Report | None:
    """The report in `reply`, or None when no line of it is exactly MARKER."""
    lines = (reply or "").splitlines()
    start = next((i for i, line in enumerate(lines) if line.strip() == MARKER), None)
    if start is None:
        return None
    rest = lines[start + 1:]
    title = next((line[2:].strip() for line in rest if line.startswith("# ")), "")
    summary, inside = [], False
    for line in rest:
        if line.startswith("## "):
            inside = line[3:].strip().lower() == "summary"
        elif inside and line.lstrip().startswith(("- ", "* ")):
            summary.append(line.lstrip()[2:].strip())
    return Report(preface="\n".join(lines[:start]).strip(),
                  body="\n".join(lines[start:]).strip() + "\n",
                  title=title or "Research report", summary=summary)


def chat_reply(report: Report) -> str:
    """What the chat keeps: the sentences before the marker, or the Summary's
    bullets when the model wrote none, then where the rest went."""
    lead = report.preface or " ".join(
        b if b.endswith((".", "!", "?")) else b + "." for b in report.summary[:3])
    saved = f"Report saved: {report.title}."
    return f"{lead}\n\n{saved}" if lead else saved


def is_company_research(client: anthropic.Anthropic, small_model: str, report: Report) -> bool:
    """Spec 006's company_research flag, asked of one report. A model may
    answer "true" as a string; anything else, an error included, is personal,
    so a report is never filed into the shared project by mistake."""
    prompt = SCOPE_PROMPT.format(title=report.title,
                                 summary="\n".join(f"- {b}" for b in report.summary))
    try:
        response = client.messages.create(
            model=small_model,
            # room for a reasoning model's thinking block before the JSON,
            # the same reason as the retrieval gate's budget
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(b.text for b in response.content if b.type == "text")
        answer = json.loads(text[text.index("{"):text.rindex("}") + 1])
    except Exception:
        return False
    return str(answer.get("company_research")).lower() == "true"


def save(reply: str, remember: Callable | None,
         company_research: Callable[[Report], bool]) -> tuple[str, dict | None]:
    """(the chat reply, the `report` event). The reply comes back unchanged,
    with no event, when it holds no report, when Waku Memory is not connected
    (`remember` is None) and when the send failed. A failure is logged and
    never raised: the turn has already been answered."""
    report = find(reply)
    if report is None or remember is None:
        return reply, None
    scope = f"project:{COMPANY_PROJECT}" if company_research(report) else "global"
    try:
        memory_id = remember(report.body, scope, kind=KIND)
    except Exception as exc:
        log.warning("Waku Memory did not take the report %r (%s); "
                    "it stays in the reply", report.title, exc)
        return reply, None
    return chat_reply(report), {"title": report.title, "memory_id": memory_id,
                                "scope": scope, "summary": report.summary}
