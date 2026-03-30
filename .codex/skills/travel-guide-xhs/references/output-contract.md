# Output Contract

Default deliverables:

- `主旅行报告.md`
- `家人版时间线.md`
- `路线地图-总览.json`
- `路线地图-Day1.json`
- `路线地图-Day2.json`
- route map images, required: at least 1 overview map and usually 2 to 3 total for multi-day trips
- optional PDF

## Main report sections

Keep this order unless the user asks otherwise:

1. 这份报告怎么用
2. 推荐路线与原因
3. 路线总览图
4. 小红书主来源摘要
5. 补充来源摘要
6. 逐日时间线
7. 酒店 / 高铁 / 机票 / 餐饮建议
8. 官方校验信息
9. 变化场景与兜底
10. 来源脚注

## Family timeline sections

Keep it lighter than the main report:

1. 行程总览
2. 总览路线图
3. 分日时间线
4. 提醒
5. 来源脚注

## Required reporting behavior

- The main route must clearly read as Xiaohongshu-first.
- Use paper-style footnote citations such as `[^1]`, `[^2]`, and `[^3]` in the body, tables, and key decision points.
- Collect full source definitions in a final `来源脚注` section. Do not use bracketed source tags such as `[小红书]` as the final citation style.
- In PDFs, footnote markers should be clickable and jump to the matching footnote entry whenever the renderer supports internal links.
- In PDFs, clickable elements such as footnote markers and source links should render in blue without underlines so users can recognize them without adding visual noise.
- At least one route overview map image must appear in the main report body, not only as a side artifact.
- For 2-plus-day trips or routes with non-trivial transfers, include an overview map plus day maps or clearly segmented route maps.
- Keep the front of the report clean: show the overview map near the front, but place Day 1 and Day 2 maps inside the matching timeline subsections instead of putting every map in one early block.
- Supplemental UGC must be labeled as supplemental.
- Hard facts must show official or approved query validation.
- If validation is incomplete, mark the report as `未完成校验`.
- If the route map is missing, the report is incomplete and should not be treated as ready.
- If the report contains links, run the whitelist audit before delivery.

## Tone and shape

- Prefer clear, practical prose over research-paper style writing.
- Keep typography print-like and restrained. Default PDF styling should be black Songti-style Chinese text when available.
- Use tables for time-based schedules.
- Keep family-facing output short, clear, and easy to forward.
- Keep executor-facing output richer, with decisions, caveats, and fallback branches.
- Avoid heavy detail dumps on the opening pages. The first pages should stay clean and decision-oriented.
