---
name: research-report
description: Research report on companies, competitors, markets or products: research a company, compare competitors, market landscape, funding, pricing, launches.
---

Write a report when the person asks you to research companies, competitors,
markets, products or people. Anything else gets a normal answer.

## The reply

Two or three plain sentences saying what you found, then the report, starting
with the marker on a line of its own (once per reply). Waku saves the report to
Waku Memory and the chat keeps only your sentences, so they must stand alone.

## House language

- Plain sentences. Every number has its unit and a date ("$24 a month, 2026-09").
- Every claim traces to an entry in Sources. No source, no claim.
- Say what you looked for and did not find in Gaps.
- No adjective a reader cannot check: not "leading", "fast", "best".
- A vendor's claim about itself is reported as its claim ("Kestrel says"), never as fact.

## The format: waku-report v1 (frozen; waku.one renders it)

Line 1 is `<!-- waku-report v1 -->`, line 2 is `# <title>`. Then these sections,
in this order, each optional except Summary and Sources: `## Summary` (three
bullets at most), `## Findings` (a Markdown table), `## Comparison`,
`## Numbers`, `## Timeline`, `## Gaps`, `## Sources`.

Visual parts are fenced blocks, only these five, with exactly these shapes. The
fence's language names the component; the body is JSON (no comments, no trailing commas):

- `waku-metrics`: `[{"label": str, "value": str, "note": str?}]`, 2 to 6 tiles
- `waku-chart`: `{"type": "bar"|"line", "title": str, "unit": str?, "series": [{"label": str, "value": number}]}`. One series; a bar chart is sorted largest first.
- `waku-compare`: `{"columns": [str], "rows": [{"name": str, "cells": [str|bool|null]}]}`. One cell per column; `true`/`false`/`null` mean yes/no/unknown.
- `waku-timeline`: `[{"date": "YYYY-MM-DD"|"YYYY-MM", "event": str, "subject": str?}]`, newest first
- `waku-sources`: `[{"title": str, "url": str?, "via": str?, "cost_usd": number?}]`. `via` names the tool that found it, such as `treg:treg.web.search`.

## Example (fictional companies: copy the shape, never the facts)

````markdown
Three companies sell hosted memory to agent builders. Birchline has raised the most, $41M, and Kestrel is the only one with a free tier; none publishes accuracy numbers.

<!-- waku-report v1 -->
# Agent memory vendors, 2026-10-03

## Summary
- Three vendors sell hosted memory for AI agents: Birchline, Kestrel and Tamsin.
- Birchline has raised the most, $41M in two rounds (2025-03 and 2026-09).
- None of the three publishes recall accuracy or retention numbers.

## Findings
| Company | Product | Price (2026-10) | Source |
|---|---|---|---|
| Birchline | Birchline Cloud | $49 a month | Birchline pricing |
| Kestrel | Kestrel Memory | free to 10,000 memories, then $19 a month | Kestrel pricing |
| Tamsin | Tamsin API | not published | none |

## Comparison
```waku-compare
{"columns": ["Free tier", "MCP server", "Self-host"], "rows": [{"name": "Birchline", "cells": [false, true, null]}, {"name": "Kestrel", "cells": [true, true, false]}, {"name": "Tamsin", "cells": [false, null, true]}]}
```

## Numbers
```waku-metrics
[{"label": "Vendors", "value": "3"}, {"label": "Most raised", "value": "$41M", "note": "Birchline, 2026-09"}, {"label": "Cheapest paid plan", "value": "$19 a month", "note": "Kestrel"}]
```
```waku-chart
{"type": "bar", "title": "Total funding raised", "unit": "USD M", "series": [{"label": "Birchline", "value": 41}, {"label": "Kestrel", "value": 12}, {"label": "Tamsin", "value": 3.5}]}
```

## Timeline
```waku-timeline
[{"date": "2026-09-12", "event": "Series A, $35M", "subject": "Birchline"}, {"date": "2026-06", "event": "Launched an MCP server", "subject": "Kestrel"}, {"date": "2025-11-03", "event": "Public beta", "subject": "Tamsin"}]
```

## Gaps
- Tamsin publishes no price; its pricing page asks for a sales call.
- No vendor publishes recall accuracy or retention numbers.

## Sources
```waku-sources
[{"title": "Birchline pricing", "url": "https://birchline.example/pricing", "via": "treg:treg.web.search", "cost_usd": 0.002}, {"title": "Kestrel pricing", "url": "https://kestrel.example/pricing", "via": "treg:treg.web.fetch"}, {"title": "Funding rounds, Birchline, Kestrel and Tamsin", "url": "https://funding.example/agent-memory"}]
```
````
