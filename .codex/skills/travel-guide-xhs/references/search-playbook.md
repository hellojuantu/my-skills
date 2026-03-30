# Xiaohongshu Search Playbook

## Search order

1. Use logged-in Xiaohongshu search first.
2. If coverage is thin, open user-provided Xiaohongshu share links.
3. If login breaks, CAPTCHA appears, or risk-control blocks progress, stop and ask the user to handle it.

## Default keyword patterns

Start broad, then narrow:

- `{destination} 两日游`
- `{destination} 周末 行程`
- `{destination} 攻略`
- `{destination} citywalk`
- `{destination} 亲子`
- `{destination} 长辈`

Then add route anchors:

- `西湖 灵隐 雷峰塔`
- `机场 酒店 路线`
- `高铁 酒店 景点`

## What to keep

Prefer notes that include at least one of these:

- Day 1 / Day 2 / 时间线
- clear route order
- how long they stayed at each spot
- why they chose one sequence over another
- practical transport or queue advice
- first-person experience and specific details

## What to filter out

Reject or de-prioritize notes that are mostly:

- hotel or merchant ads
- group-buy or package pages
- repost collages without a route
- generic "must visit" lists
- polished brand copy with no lived experience
- notes that only talk about one attraction without trip structure

## Coverage target

When feasible, keep at least five Xiaohongshu notes for the route backbone.

If the destination is niche:

- keep the best Xiaohongshu notes you can find
- supplement carefully with approved UGC and official/query sources
- explicitly say when Xiaohongshu coverage is thin

## Extraction checklist

For each note you keep, capture:

- title
- link
- author handle if visible
- publish date if visible
- why it was selected
- extracted route order
- extracted tips or constraints

## Logged-in browsing reminders

- Expect Xiaohongshu search and note pages to be dynamic.
- Prefer browser tools or Playwright-style automation over raw HTTP for search.
- Share links can often be opened directly even when search is inconsistent.
