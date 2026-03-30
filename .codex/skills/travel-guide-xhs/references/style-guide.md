# Style Guide

This skill should mirror the user's preferred travel-planning style.

## Core style signals

- classic route choices beat novelty for first visits
- smooth movement beats aggressive point-count packing
- comfort, recovery time, and legibility matter
- separate executor detail from family-facing timeline when helpful

## Main report style

The main report should feel like an execution handbook:

- explain why the route is arranged this way
- keep a realistic pace
- include fallback plans for rain, queues, and return-time changes
- add operational reminders when they reduce failure risk
- keep the opening pages clean and readable
- show only the overview map near the front, then let day maps appear inside the matching day sections
- use paper-style footnote citations such as `[^1]` instead of bracketed source tags
- when outputting PDF, footnote markers should support click-to-jump into the final footnote section

## Family timeline style

The family-facing version should:

- be shorter and calmer
- emphasize time, transport, and plain-language explanations
- avoid internal planning clutter
- keep citations light, but when sources are shown use the same footnote style

## Map and visual style

- every final report should include at least one route overview map
- for multi-day or non-trivial movement, add day maps when the route would otherwise be hard to picture
- use simple numbered stops or labeled markers
- highlight transfer nodes such as stations, airports, ferry piers, or parking anchors when they affect execution
- keep title and subtitle practical, not promotional
- do not stack Day 1 and Day 2 maps at the front of the report

## Typography and color

- final PDF output should default to Songti-style Chinese typography when the environment supports it
- prefer Songti regular or light faces, never black/heavy Songti faces
- body text, headings, table text, captions, and footnotes should all stay black
- prefer a restrained, print-like look over colored dashboard styling
- do not use bold emphasis; hierarchy should come from headings, spacing, and ordering instead
- do not render inline code as gray boxes in final travel PDFs; keep it visually consistent with normal body text
- any clickable element in the PDF, including footnote markers and source links, should render in blue without underlines
- in the final `来源脚注` section, markers such as `[1]` should stay on the text baseline at normal reading size, not as superscripts

## What to avoid

- avoid stuffing too many attractions into one day
- avoid abstract "best of" summaries with no route logic
- avoid source dumping without curation
- avoid noisy opening pages with too many maps or repeated source labels
