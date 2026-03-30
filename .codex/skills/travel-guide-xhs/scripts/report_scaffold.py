#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
ASSETS_DIR = SKILL_DIR / "assets"


def render_template(template_path: Path, values: dict[str, str]) -> str:
    return template_path.read_text(encoding="utf-8").format(**values)


def write_text(path: Path, content: str, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"{path} already exists. Use --force to overwrite it.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def build_map_spec(
    title: str,
    subtitle: str,
    output_path: str,
    start_label: str,
    end_label: str,
) -> str:
    spec = {
        "title": title,
        "subtitle": subtitle,
        "center": [0.0, 0.0],
        "zoom": 12,
        "width": 1320,
        "height": 860,
        "route_color": "#d35d3f",
        "route_width": 5,
        "route": [
            [0.0, 0.0],
            [0.0, 0.0],
        ],
        "stops": [
            {
                "kind": "numbered",
                "number": 1,
                "label": start_label,
                "coord": [0.0, 0.0],
                "color": "#2d7be0",
            },
            {
                "kind": "numbered",
                "number": 2,
                "label": end_label,
                "coord": [0.0, 0.0],
                "color": "#2d7be0",
            },
        ],
        "output": output_path,
    }
    return json.dumps(spec, ensure_ascii=False, indent=2) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create the default markdown scaffold for the Xiaohongshu-first travel guide skill."
    )
    parser.add_argument("--title", required=True, help="Main trip report title.")
    parser.add_argument("--destination", required=True, help="Trip destination.")
    parser.add_argument(
        "--days",
        default="待定",
        help="Trip length or a short day-count label, for example '2 天 1 晚'.",
    )
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Directory where the markdown files should be created.",
    )
    parser.add_argument(
        "--report-name",
        default="主旅行报告.md",
        help="Filename for the main report markdown.",
    )
    parser.add_argument(
        "--family-name",
        default="家人版时间线.md",
        help="Filename for the family timeline markdown.",
    )
    parser.add_argument(
        "--map-spec-name",
        default=None,
        help="Deprecated alias for the overview route map JSON spec filename.",
    )
    parser.add_argument(
        "--overview-map-spec-name",
        default="路线地图-总览.json",
        help="Filename for the overview route map JSON spec scaffold.",
    )
    parser.add_argument(
        "--day1-map-spec-name",
        default="路线地图-Day1.json",
        help="Filename for the Day 1 route map JSON spec scaffold.",
    )
    parser.add_argument(
        "--day2-map-spec-name",
        default="路线地图-Day2.json",
        help="Filename for the Day 2 route map JSON spec scaffold.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    output_dir = Path(args.output_dir).expanduser().resolve()
    report_stem = Path(args.report_name).stem
    overview_map_spec_name = args.map_spec_name or args.overview_map_spec_name

    overview_map_output = f"output/map-shots/{report_stem}-route-overview.png"
    day1_map_output = f"output/map-shots/{report_stem}-route-day1.png"
    day2_map_output = f"output/map-shots/{report_stem}-route-day2.png"

    values = {
        "title": args.title,
        "destination": args.destination,
        "days": args.days,
        "today": date.today().isoformat(),
        "report_stem": report_stem,
        "overview_map_spec_name": overview_map_spec_name,
        "day1_map_spec_name": args.day1_map_spec_name,
        "day2_map_spec_name": args.day2_map_spec_name,
        "overview_map_output": overview_map_output,
        "day1_map_output": day1_map_output,
        "day2_map_output": day2_map_output,
    }

    report = render_template(ASSETS_DIR / "main_report_template.md", values)
    family = render_template(ASSETS_DIR / "family_timeline_template.md", values)
    overview_map_spec = build_map_spec(
        title=f"{args.destination}路线总览图",
        subtitle="放整体移动关系，前页只保留这一张总览图。",
        output_path=overview_map_output,
        start_label="起点",
        end_label="终点",
    )
    day1_map_spec = build_map_spec(
        title=f"{args.destination} Day 1 路线图",
        subtitle="把 Day 1 的关键转场和停靠点填进去，再插入 Day 1 时间线小节。",
        output_path=day1_map_output,
        start_label="Day 1 起点",
        end_label="Day 1 终点",
    )
    day2_map_spec = build_map_spec(
        title=f"{args.destination} Day 2 路线图",
        subtitle="把 Day 2 的关键转场和停靠点填进去，再插入 Day 2 时间线小节。",
        output_path=day2_map_output,
        start_label="Day 2 起点",
        end_label="Day 2 终点",
    )

    report_path = output_dir / args.report_name
    family_path = output_dir / args.family_name
    overview_map_spec_path = output_dir / overview_map_spec_name
    day1_map_spec_path = output_dir / args.day1_map_spec_name
    day2_map_spec_path = output_dir / args.day2_map_spec_name

    write_text(report_path, report, args.force)
    write_text(family_path, family, args.force)
    write_text(overview_map_spec_path, overview_map_spec, args.force)
    write_text(day1_map_spec_path, day1_map_spec, args.force)
    write_text(day2_map_spec_path, day2_map_spec, args.force)

    print(report_path)
    print(family_path)
    print(overview_map_spec_path)
    print(day1_map_spec_path)
    print(day2_map_spec_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
