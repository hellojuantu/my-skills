#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import sys
from collections.abc import Callable
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont
from requests import RequestException


TILE_SIZE = 256
TILE_URL = "https://webrd01.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=2&style=8&x={x}&y={y}&z={z}"
PI = math.pi
A = 6378245.0
EE = 0.00669342162296594323
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "travel-guide-xhs-map-renderer"})
TILE_TIMEOUT_SECONDS = 12
TILE_RETRY_COUNT = 3
FONT_CANDIDATES = [
    ("/System/Library/Fonts/Supplemental/Songti.ttc", 6),
    ("/System/Library/Fonts/Supplemental/Songti.ttc", 3),
    ("/System/Library/Fonts/Hiragino Sans GB.ttc", 0),
    ("/System/Library/Fonts/PingFang.ttc", 0),
    ("/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc", 0),
    ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 0),
    ("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc", 0),
]


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate, font_index in FONT_CANDIDATES:
        path = Path(candidate)
        if path.exists():
            return ImageFont.truetype(str(path), size, index=font_index)
    return ImageFont.load_default()


def out_of_china(lat: float, lon: float) -> bool:
    return not (73.66 < lon < 135.05 and 3.86 < lat < 53.55)


def transform_lat(x: float, y: float) -> float:
    ret = (
        -100.0
        + 2.0 * x
        + 3.0 * y
        + 0.2 * y * y
        + 0.1 * x * y
        + 0.2 * math.sqrt(abs(x))
    )
    ret += (
        (20.0 * math.sin(6.0 * x * PI) + 20.0 * math.sin(2.0 * x * PI))
        * 2.0
        / 3.0
    )
    ret += (
        (20.0 * math.sin(y * PI) + 40.0 * math.sin(y / 3.0 * PI))
        * 2.0
        / 3.0
    )
    ret += (
        (160.0 * math.sin(y / 12.0 * PI) + 320 * math.sin(y * PI / 30.0))
        * 2.0
        / 3.0
    )
    return ret


def transform_lon(x: float, y: float) -> float:
    ret = (
        300.0
        + x
        + 2.0 * y
        + 0.1 * x * x
        + 0.1 * x * y
        + 0.1 * math.sqrt(abs(x))
    )
    ret += (
        (20.0 * math.sin(6.0 * x * PI) + 20.0 * math.sin(2.0 * x * PI))
        * 2.0
        / 3.0
    )
    ret += (
        (20.0 * math.sin(x * PI) + 40.0 * math.sin(x / 3.0 * PI))
        * 2.0
        / 3.0
    )
    ret += (
        (150.0 * math.sin(x / 12.0 * PI) + 300.0 * math.sin(x / 30.0 * PI))
        * 2.0
        / 3.0
    )
    return ret


def wgs84_to_gcj02(lat: float, lon: float) -> tuple[float, float]:
    if out_of_china(lat, lon):
        return lat, lon
    dlat = transform_lat(lon - 105.0, lat - 35.0)
    dlon = transform_lon(lon - 105.0, lat - 35.0)
    radlat = lat / 180.0 * PI
    magic = math.sin(radlat)
    magic = 1 - EE * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / (((A * (1 - EE)) / (magic * sqrtmagic)) * PI)
    dlon = (dlon * 180.0) / ((A / sqrtmagic * math.cos(radlat)) * PI)
    return lat + dlat, lon + dlon


def latlon_to_world(lat: float, lon: float, zoom: int) -> tuple[float, float]:
    scale = TILE_SIZE * (2**zoom)
    x = (lon + 180.0) / 360.0 * scale
    lat_rad = math.radians(lat)
    y = (
        (1.0 - math.log(math.tan(lat_rad) + (1 / math.cos(lat_rad))) / math.pi)
        / 2.0
        * scale
    )
    return x, y


def fetch_tile(z: int, x: int, y: int) -> Image.Image:
    max_tile = 2**z
    x %= max_tile
    y = max(0, min(y, max_tile - 1))
    last_error: Exception | None = None
    for _ in range(TILE_RETRY_COUNT):
        try:
            response = SESSION.get(
                TILE_URL.format(z=z, x=x, y=y),
                timeout=TILE_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            return Image.open(BytesIO(response.content)).convert("RGBA")
        except (RequestException, OSError) as exc:
            last_error = exc
    raise RuntimeError(f"failed to fetch tile z={z} x={x} y={y}") from last_error


def render_map(center: tuple[float, float], zoom: int, width: int, height: int) -> tuple[Image.Image, float, float]:
    center_gcj = wgs84_to_gcj02(center[0], center[1])
    center_x, center_y = latlon_to_world(center_gcj[0], center_gcj[1], zoom)
    left = center_x - width / 2
    top = center_y - height / 2
    right = center_x + width / 2
    bottom = center_y + height / 2

    tile_x0 = int(math.floor(left / TILE_SIZE))
    tile_y0 = int(math.floor(top / TILE_SIZE))
    tile_x1 = int(math.floor(right / TILE_SIZE))
    tile_y1 = int(math.floor(bottom / TILE_SIZE))

    canvas = Image.new("RGBA", (width, height), "white")
    for tx in range(tile_x0, tile_x1 + 1):
        for ty in range(tile_y0, tile_y1 + 1):
            tile = fetch_tile(zoom, tx, ty)
            px = int(tx * TILE_SIZE - left)
            py = int(ty * TILE_SIZE - top)
            canvas.alpha_composite(tile, (px, py))
    return canvas, left, top


def point_px(lat: float, lon: float, zoom: int, left: float, top: float) -> tuple[float, float]:
    lat_gcj, lon_gcj = wgs84_to_gcj02(lat, lon)
    x, y = latlon_to_world(lat_gcj, lon_gcj, zoom)
    return x - left, y - top


def build_schematic_projector(
    points: list[tuple[float, float]],
    width: int,
    height: int,
    padding: int = 88,
) -> tuple[Callable[[float, float], tuple[float, float]], tuple[float, float, float, float]]:
    lats = [lat for lat, _ in points]
    lons = [lon for _, lon in points]
    min_lat = min(lats)
    max_lat = max(lats)
    min_lon = min(lons)
    max_lon = max(lons)

    lat_span = max(max_lat - min_lat, 0.03)
    lon_span = max(max_lon - min_lon, 0.03)
    min_lat -= lat_span * 0.18
    max_lat += lat_span * 0.18
    min_lon -= lon_span * 0.18
    max_lon += lon_span * 0.18

    viewport_ratio = max((width - padding * 2) / max(height - padding * 2, 1), 0.1)
    data_lat_span = max(max_lat - min_lat, 0.03)
    data_lon_span = max(max_lon - min_lon, 0.03)
    data_ratio = data_lon_span / data_lat_span

    if data_ratio > viewport_ratio:
        desired_lat_span = data_lon_span / viewport_ratio
        extra = max(desired_lat_span - data_lat_span, 0) / 2
        min_lat -= extra
        max_lat += extra
    else:
        desired_lon_span = data_lat_span * viewport_ratio
        extra = max(desired_lon_span - data_lon_span, 0) / 2
        min_lon -= extra
        max_lon += extra

    lon_denominator = max(max_lon - min_lon, 0.03)
    lat_denominator = max(max_lat - min_lat, 0.03)

    def project(lat: float, lon: float) -> tuple[float, float]:
        x = padding + (lon - min_lon) / lon_denominator * (width - padding * 2)
        y = height - padding - (lat - min_lat) / lat_denominator * (height - padding * 2)
        return x, y

    return project, (min_lat, max_lat, min_lon, max_lon)


def render_schematic_canvas(width: int, height: int) -> Image.Image:
    image = Image.new("RGBA", (width, height), "#f5f0e7")
    draw = ImageDraw.Draw(image)
    grid_color = "#e3dacd"
    for x in range(0, width, 120):
        draw.line((x, 0, x, height), fill=grid_color, width=1)
    for y in range(0, height, 120):
        draw.line((0, y, width, y), fill=grid_color, width=1)

    draw.rounded_rectangle(
        (12, 12, width - 12, height - 12),
        radius=28,
        outline="#d2c5b2",
        width=2,
    )
    chip_font = load_font(18)
    note_font = load_font(18)
    draw.rounded_rectangle(
        (width - 190, 18, width - 20, 58),
        radius=16,
        fill="#fff9f1",
        outline="#c9b293",
        width=2,
    )
    draw.text((width - 168, 29), "路线示意图", font=chip_font, fill="#7a5b35")
    draw.text((24, height - 42), "用于行程理解，非精确导航", font=note_font, fill="#8a7d70")
    return image


def draw_polyline(draw: ImageDraw.ImageDraw, points: list[tuple[float, float]], color: str, width: int = 6) -> None:
    if len(points) >= 2:
        draw.line(points, fill=color, width=width, joint="curve")


def draw_marker(
    draw: ImageDraw.ImageDraw,
    x: float,
    y: float,
    label: str,
    color: str,
    label_dx: int = 12,
    label_dy: int = -45,
) -> None:
    font = load_font(20)
    r = 13
    draw.ellipse((x - r, y - r, x + r, y + r), fill=color, outline="white", width=4)
    draw.ellipse((x - 4, y - 4, x + 4, y + 4), fill="white")
    box_w = draw.textlength(label, font=font) + 22
    box_h = 34
    bx = x + label_dx
    by = y + label_dy
    draw.rounded_rectangle((bx, by, bx + box_w, by + box_h), radius=10, fill="white", outline=color, width=2)
    draw.text((bx + 11, by + 6), label, font=font, fill="#213247")


def draw_numbered_stop(
    draw: ImageDraw.ImageDraw,
    x: float,
    y: float,
    number: int,
    label: str,
    color: str,
    label_dx: int = 12,
    label_dy: int = -46,
) -> None:
    font = load_font(20)
    num_font = load_font(20)
    r = 15
    draw.ellipse((x - r, y - r, x + r, y + r), fill=color, outline="white", width=4)
    number_text = str(number)
    bbox = draw.textbbox((0, 0), number_text, font=num_font)
    num_w = bbox[2] - bbox[0]
    num_h = bbox[3] - bbox[1]
    draw.text((x - num_w / 2, y - num_h / 2 - 1), number_text, font=num_font, fill="white")
    box_w = draw.textlength(label, font=font) + 24
    box_h = 36
    bx = max(x + label_dx, 12)
    by = max(y + label_dy, 12)
    draw.rounded_rectangle((bx, by, bx + box_w, by + box_h), radius=10, fill="white", outline=color, width=2)
    draw.text((bx + 12, by + 6), label, font=font, fill="#213247")


def add_header(image: Image.Image, title: str, subtitle: str) -> Image.Image:
    canvas = Image.new("RGBA", (image.width, image.height + 110), "#f6f3ed")
    canvas.alpha_composite(image, (0, 110))
    draw = ImageDraw.Draw(canvas)
    title_font = load_font(32)
    sub_font = load_font(18)
    draw.text((32, 24), title, font=title_font, fill="#223247")
    if subtitle:
        draw.text((32, 66), subtitle, font=sub_font, fill="#5d667a")
    return canvas


def example_spec() -> dict[str, object]:
    return {
        "title": "周六路线图",
        "subtitle": "住湖滨附近最顺，上午上船，下午再去雷峰塔。",
        "center": [30.2478, 120.1445],
        "zoom": 14,
        "width": 1320,
        "height": 860,
        "route_color": "#d35d3f",
        "route_width": 5,
        "route": [
            [30.2545411, 120.1574853],
            [30.2408160, 120.1404964],
            [30.2338837, 120.1450125]
        ],
        "stops": [
            {
                "kind": "numbered",
                "number": 1,
                "label": "二公园码头",
                "coord": [30.2545411, 120.1574853],
                "color": "#2d7be0",
                "label_dx": 14,
                "label_dy": -18
            },
            {
                "kind": "numbered",
                "number": 2,
                "label": "三潭印月",
                "coord": [30.2408160, 120.1404964],
                "color": "#2d7be0"
            },
            {
                "kind": "marker",
                "label": "雷峰塔",
                "coord": [30.2338837, 120.1450125],
                "color": "#d35d3f",
                "label_dx": 14,
                "label_dy": 10
            }
        ],
        "output": "output/map-shots/example-route-map.png"
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render a route map from a JSON spec.")
    parser.add_argument("--spec", help="Path to the JSON spec file.")
    parser.add_argument("--output", help="Optional output path override.")
    parser.add_argument(
        "--print-example",
        action="store_true",
        help="Print an example JSON spec and exit.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.print_example:
        print(json.dumps(example_spec(), ensure_ascii=False, indent=2))
        return 0

    if not args.spec:
        parser.error("--spec is required unless --print-example is used.")

    spec_path = Path(args.spec).expanduser().resolve()
    spec = json.loads(spec_path.read_text(encoding="utf-8"))

    title = str(spec.get("title", "路线图"))
    subtitle = str(spec.get("subtitle", ""))
    center = tuple(spec["center"])
    zoom = int(spec.get("zoom", 12))
    width = int(spec.get("width", 1320))
    height = int(spec.get("height", 860))
    route_color = str(spec.get("route_color", "#d35d3f"))
    route_width = int(spec.get("route_width", 5))

    route_coords = [
        (float(lat), float(lon))
        for lat, lon in spec.get("route", [])
    ]
    stops = spec.get("stops", [])
    reference_points = [(float(center[0]), float(center[1])), *route_coords]
    reference_points.extend(
        (float(stop["coord"][0]), float(stop["coord"][1]))
        for stop in stops
    )

    subtitle_suffix = ""
    try:
        image, left, top = render_map((float(center[0]), float(center[1])), zoom, width, height)

        def projector(lat: float, lon: float) -> tuple[float, float]:
            return point_px(float(lat), float(lon), zoom, left, top)

    except Exception as exc:
        print(f"[render_route_map] tile render failed: {exc}", file=sys.stderr)
        image = render_schematic_canvas(width, height)
        projector, _ = build_schematic_projector(reference_points, width, height)
        subtitle_suffix = " 已自动切换为路线示意图。"

    draw = ImageDraw.Draw(image)

    route_points = [
        projector(float(lat), float(lon))
        for lat, lon in route_coords
    ]
    draw_polyline(draw, route_points, route_color, route_width)

    for stop in stops:
        lat, lon = stop["coord"]
        x, y = projector(float(lat), float(lon))
        kind = stop.get("kind", "marker")
        label_dx = int(stop.get("label_dx", 12))
        label_dy = int(stop.get("label_dy", -45 if kind == "marker" else -46))
        if kind == "numbered":
            draw_numbered_stop(
                draw,
                x,
                y,
                int(stop["number"]),
                str(stop["label"]),
                str(stop.get("color", "#2d7be0")),
                label_dx=label_dx,
                label_dy=label_dy,
            )
        else:
            draw_marker(
                draw,
                x,
                y,
                str(stop["label"]),
                str(stop.get("color", "#2d7be0")),
                label_dx=label_dx,
                label_dy=label_dy,
            )

    output = Path(args.output or spec["output"]).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    final_subtitle = f"{subtitle}{subtitle_suffix}".strip()
    final_image = add_header(image, title, final_subtitle)
    final_image.save(output)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
