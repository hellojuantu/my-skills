# Source Policy

This skill uses a three-layer source model.

## A. Primary route source

- `xiaohongshu.com`
- Use for: route skeleton, real user itineraries, pace, sequencing, photo spots, and lived experience.
- Rule: the main itinerary must be grounded here first.

## B. Supplemental UGC

- 马蜂窝
- 穷游
- 点评评论
- 携程攻略

Use these only to supplement:

- food texture and queue notes
- hotel stay feedback
- practical tips and common pitfalls
- small details that enrich, but do not replace, the Xiaohongshu route

## C. Query and official sources

- 12306
- 携程酒店 / 携程机票 / 携程火车票
- 高德地图
- official hotel, airline, scenic-spot, airport, metro, and government pages

Use these for hard facts:

- hotel room type, check-in policy, breakfast, and price band
- train schedules and seat classes
- flight timing and fare bands
- ticketing rules, opening hours, reservation rules
- coordinates, route geometry, and airport/metro access

## Allowed domains

Base whitelist lives in `config/source_whitelist.json`.

Always allowed by default:

- `xiaohongshu.com`
- `mafengwo.cn`
- `mafengwo.com`
- `qyer.com`
- `dianping.com`
- `ctrip.com`
- `12306.cn`
- `amap.com`
- `autonavi.com`
- `*.gov.cn`

## Extra official domains

Some official sites cannot be pre-enumerated in a static list, for example:

- hotel brand domains
- airline domains
- scenic spot official sites
- airport or metro domains outside `gov.cn`

When you use one of these:

1. confirm it is actually official
2. keep its role limited to official validation
3. pass it to `scripts/audit_sources.py` with `--allow-domain`

## Citation style

Use paper-style footnote markers in the report body:

- `[^1]`
- `[^2]`
- `[^3]`

At the end of the report, collect full source definitions in a `来源脚注` section, for example:

- `[^1]: 小红书｜《标题》｜[原文](https://...)`
- `[^2]: 携程机票｜查询页｜[原文](https://...)`
- `[^3]: 官方｜景区开放时间页｜[原文](https://...)`

Do not use bracketed source tags such as `[小红书]` or `[官方]` as the final citation style in deliverables.

## Never do this

- Do not let Mafengwo, Qyer, Dianping, or Ctrip guides replace the Xiaohongshu route skeleton.
- Do not rely on UGC alone for ticketing, opening hours, reservation rules, flights, trains, or hotel policy.
- Do not use unapproved travel blogs, SEO listicles, or random repost sites in the final report.
