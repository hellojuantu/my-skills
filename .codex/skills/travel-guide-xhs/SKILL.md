---
name: "travel-guide-xhs"
description: "Use when creating a 旅游攻略, 行程规划, family trip timeline, or travel report that should use Xiaohongshu as the primary route source, then supplement with approved sources such as Mafengwo, Qyer, Dianping, Ctrip, 12306, Amap, and official pages."
---

# Xiaohongshu-First Travel Guide

Use this skill for travel planning work where source quality matters:

- travel guides and itinerary design
- family-friendly or elder-friendly trip timelines
- destination research that must keep Xiaohongshu first
- travel reports that need auditable sources and clean output artifacts

## Non-negotiables

- Xiaohongshu is the primary route source. The main itinerary must come from real user notes, not from secondary travel sites.
- Every final report must include route map images inside the report body. A separate map artifact is not enough.
- Keep the front of the main report visually clean: place one overview map near the front, and place Day 1, Day 2, or segment maps inside the corresponding timeline sections instead of stacking them all up front.
- Final PDF output should use black Songti-style Chinese typography whenever available. Avoid colored body text or decorative typography.
- Do not use bold emphasis in final deliverables. Avoid markdown bold such as `**重点**`, HTML bold tags, or any other visually heavy emphasis. Use headings, spacing, and sentence order to create hierarchy instead.
- Only approved sources may appear in the final report. Before using non-Xiaohongshu sources, read [references/source-policy.md](references/source-policy.md).
- Hard facts such as ticket rules, opening hours, reservations, flights, trains, and hotel policy must be checked against official pages or approved query pages.
- Never purchase, submit payment, or enter credentials on the user's behalf.
- When login, CAPTCHA, SMS verification, or risk-control prompts appear, stop and ask the user to handle them.

## Required inputs

Collect or infer these before drafting:

- destination
- departure city
- dates or trip length
- traveler profile
- budget and hotel preference
- pace preference
- whether Xiaohongshu is already logged in
- any Xiaohongshu share links the user already has

If low-risk details are missing, make a reasonable default and record it in the report. If a missing detail would change the itinerary in a major way, ask the user briefly.

## Workflow

### 1. Preflight

- Read any local planning docs in the workspace first. Treat them as style references, not as substitute facts.
- If the user provided local handbooks, timelines, or route maps, imitate their tone and output shape.
- Read [references/style-guide.md](references/style-guide.md) before writing the final report set.

### 2. Collect Xiaohongshu route material

- Prefer browser automation or browser tools for Xiaohongshu search because search pages are JavaScript-heavy.
- If the user is not logged in, pause and ask them to log in first.
- Start with logged-in Xiaohongshu search using destination plus intent keywords. Read [references/search-playbook.md](references/search-playbook.md) for keyword patterns and filtering rules.
- If search login state drops later, do not assume the whole Xiaohongshu path is blocked. Single-note pages can still remain readable enough for page snapshots, so once you already have note URLs from search results or share links, keep extracting route order and practical tips from those direct note pages before asking the user to log in again.
- Keep real-user itinerary notes only. Filter out ads, merchants, listicles without route order, pure reposts, and generic destination intros.
- If search coverage is thin, process user-provided Xiaohongshu share links as fallback.
- When feasible, keep at least five Xiaohongshu notes for the main route set.

### 3. Add approved supplementary sources

- Use [references/source-policy.md](references/source-policy.md) to decide what may be used and what role each site may play.
- Hotels: query Ctrip first, then official hotel pages. Use Dianping only for stay experience and practical notes.
- Trains: query 12306 first. Ctrip train pages may help read schedules, but 12306 wins on hard facts.
- Flights: query Ctrip first, then airline official pages for baggage and rule checks.
- Food and attraction texture: Mafengwo, Qyer, Dianping, and Ctrip guides may supplement Xiaohongshu.
- Tickets, hours, reservations, airport access, metro rules: official or government pages only.

### 4. Draft the report set

- Use `scripts/report_scaffold.py` or the templates in `assets/` to create the default output set:
  - `主旅行报告.md`
  - `家人版时间线.md`
  - `路线地图-总览.json`
  - `路线地图-Day1.json`
  - `路线地图-Day2.json`
- Read [references/output-contract.md](references/output-contract.md) before filling them in.
- Every important statement should carry a paper-style footnote marker such as `[^1]` or `[^2]`. Collect the full source definitions in a final `来源脚注` section.
- In final PDFs, footnote markers should be clickable and jump to the matching footnote entry.
- Do not use bracketed source tags like `[小红书]` as the final citation style in deliverables.
- Insert route maps directly into the report markdown, not only as side artifacts. In the main report, keep only the overview map near the front; move day maps into the corresponding day timeline blocks.
- Make the main report decision-rich and execution-friendly.
- Make the family timeline simple, chronological, and easy to forward.

### 5. Produce route maps and PDF

- Use `scripts/render_route_map.py` with a small JSON spec to generate at least one route overview map before delivery.
- Route maps should default to a tight-enough crop for the actual movement. If the map feels too zoomed out, switch to bounds fitting or raise the zoom until the route reads at a glance instead of floating in empty space.
- If an overview map must cover a long intercity hop plus a dense local cluster, do not force every scenic stop onto that same wide-area map. Collapse the local cluster into a regional marker or add a local inset, then keep exact scenic positions in the day or segment map.
- For 2-plus-day trips or routes with airport, railway, metro, or self-drive transfers, also generate day maps or segment maps whenever the movement would not be obvious from text alone.
- Day maps belong inside the matching Day 1, Day 2, or segment timeline section, not grouped at the top of the report.
- Labels must not cover each other or hide key stops. If the first render stacks labels on top of each other, rerender with adjusted placement until each stop name is readable.
- Numbered stop badges must look centered inside their circles. If the digits look low or off-center, fix the rendering before delivery.
- If the report contains map files but does not visibly embed or link them from the markdown body, treat the report as incomplete.
- Use `scripts/build_trip_pdf.py` to turn the finished markdown report into a polished PDF with optional preview PNGs. The default PDF look should be black Songti-style Chinese text with restrained, print-like styling.

### 6. Audit before delivery

- Run `scripts/audit_sources.py --input <report.md> --require-domain xiaohongshu.com`.
- If you need an official hotel, airline, scenic-spot, airport, or metro domain that is not in the base whitelist, confirm it is official and pass it with `--allow-domain`.
- If the route map is missing, or the report does not clearly show the route visually, fix that before final delivery.
- If the audit fails, fix the source set before final delivery.
- If hard facts could not be verified with approved official/query sources, mark the output as `未完成校验`.

## User handoffs

The user must handle these steps whenever they appear:

- Xiaohongshu login, CAPTCHA, SMS verification, and risk-control prompts
- 12306 login and ticket purchase
- Ctrip login, member-only prices, and booking
- hotel or airline account login and booking
- Dianping login walls for deeper review browsing

## Bundled files

- [references/source-policy.md](references/source-policy.md): source tiers, whitelist, and allowed usage
- [references/search-playbook.md](references/search-playbook.md): Xiaohongshu keyword patterns and filtering heuristics
- [references/output-contract.md](references/output-contract.md): required deliverables and section contract
- [references/style-guide.md](references/style-guide.md): tone and formatting rules derived from the user's existing materials
- `config/source_whitelist.json`: machine-readable whitelist for audits
- `scripts/report_scaffold.py`: create the default markdown output set
- `scripts/audit_sources.py`: whitelist audit for report links
- `scripts/render_route_map.py`: render numbered route maps from a JSON spec
- `scripts/build_trip_pdf.py`: turn markdown into PDF and preview PNGs

## Practical notes

- Prefer concise, high-signal summaries of source material instead of long excerpts.
- Keep route advice realistic: classic, smooth, and not overpacked.
- Separate executor-facing detail from family-facing timeline whenever the user would benefit from both.
- If the textual route feels clear but the geography still is not obvious at a glance, bias toward adding more map coverage, not less.
- Keep the opening pages tidy. The front should answer "what is the route" and "why this route" before it dives into dense per-day detail.
