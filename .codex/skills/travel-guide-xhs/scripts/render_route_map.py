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
LABEL_FONT_SIZE = 18
NUMBER_FONT_SIZE = 19
MARKER_RADIUS = 13
NUMBERED_RADIUS = 16
LABEL_PADDING_X = 12
LABEL_PADDING_Y = 8
LABEL_EDGE_MARGIN = 12
LABEL_BLOCK_MARGIN = 6
LABEL_GAP = 12


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
    return render_map_view(zoom, width, height, left, top)


def render_map_view(zoom: int, width: int, height: int, left: float, top: float) -> tuple[Image.Image, float, float]:
    right = left + width
    bottom = top + height

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


def fit_map_view(
    points: list[tuple[float, float]],
    width: int,
    height: int,
    min_zoom: int,
    max_zoom: int,
    padding: int,
) -> tuple[Image.Image, float, float, int]:
    if not points:
        raise ValueError("fit_map_view requires at least one point")

    inner_width = max(width - padding * 2, 1)
    inner_height = max(height - padding * 2, 1)
    chosen_zoom = min_zoom
    chosen_bounds: tuple[float, float, float, float] | None = None

    for zoom in range(max_zoom, min_zoom - 1, -1):
        world_points = [
            latlon_to_world(*wgs84_to_gcj02(lat, lon), zoom)
            for lat, lon in points
        ]
        xs = [x for x, _ in world_points]
        ys = [y for _, y in world_points]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        span_x = max_x - min_x
        span_y = max_y - min_y
        if span_x <= inner_width and span_y <= inner_height:
            chosen_zoom = zoom
            chosen_bounds = (min_x, max_x, min_y, max_y)
            break

    if chosen_bounds is None:
        world_points = [
            latlon_to_world(*wgs84_to_gcj02(lat, lon), chosen_zoom)
            for lat, lon in points
        ]
        xs = [x for x, _ in world_points]
        ys = [y for _, y in world_points]
        chosen_bounds = (min(xs), max(xs), min(ys), max(ys))

    min_x, max_x, min_y, max_y = chosen_bounds
    span_x = max_x - min_x
    span_y = max_y - min_y
    left = min_x - max((width - span_x) / 2, 0)
    top = min_y - max((height - span_y) / 2, 0)
    image, left, top = render_map_view(chosen_zoom, width, height, left, top)
    return image, left, top, chosen_zoom


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


def measure_label_box(
    label: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
) -> tuple[float, float, float, float]:
    bbox = font.getbbox(label)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    box_w = text_w + LABEL_PADDING_X * 2
    box_h = text_h + LABEL_PADDING_Y * 2
    text_x = LABEL_PADDING_X - bbox[0]
    text_y = LABEL_PADDING_Y - bbox[1]
    return box_w, box_h, text_x, text_y


def rects_intersect(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    return not (a[2] <= b[0] or a[0] >= b[2] or a[3] <= b[1] or a[1] >= b[3])


def clamp_label_box(
    bx: float,
    by: float,
    box_w: float,
    box_h: float,
    width: int,
    height: int,
) -> tuple[float, float]:
    max_x = max(width - box_w - LABEL_EDGE_MARGIN, LABEL_EDGE_MARGIN)
    max_y = max(height - box_h - LABEL_EDGE_MARGIN, LABEL_EDGE_MARGIN)
    return (
        min(max(bx, LABEL_EDGE_MARGIN), max_x),
        min(max(by, LABEL_EDGE_MARGIN), max_y),
    )


def label_candidates(
    x: float,
    y: float,
    box_w: float,
    box_h: float,
    preferred_dx: int,
    preferred_dy: int,
    radius: int,
) -> list[tuple[float, float]]:
    gap = radius + LABEL_GAP
    candidates = [
        (x + preferred_dx, y + preferred_dy),
        (x + gap, y - box_h - gap),
        (x + gap, y + gap),
        (x - box_w - gap, y - box_h - gap),
        (x - box_w - gap, y + gap),
        (x + gap, y - box_h / 2),
        (x - box_w - gap, y - box_h / 2),
        (x - box_w / 2, y - box_h - gap),
        (x - box_w / 2, y + gap),
    ]
    unique: list[tuple[float, float]] = []
    seen: set[tuple[int, int]] = set()
    for bx, by in candidates:
        key = (int(round(bx)), int(round(by)))
        if key in seen:
            continue
        seen.add(key)
        unique.append((bx, by))
    return unique


def choose_label_box(
    x: float,
    y: float,
    box_w: float,
    box_h: float,
    preferred_dx: int,
    preferred_dy: int,
    radius: int,
    width: int,
    height: int,
    blocked_rects: list[tuple[float, float, float, float]],
) -> tuple[float, float]:
    preferred_bx = x + preferred_dx
    preferred_by = y + preferred_dy
    best_position: tuple[float, float] | None = None
    best_score: float | None = None

    for candidate_bx, candidate_by in label_candidates(
        x,
        y,
        box_w,
        box_h,
        preferred_dx,
        preferred_dy,
        radius,
    ):
        bx, by = clamp_label_box(candidate_bx, candidate_by, box_w, box_h, width, height)
        rect = (bx, by, bx + box_w, by + box_h)
        overlap_count = sum(1 for blocked in blocked_rects if rects_intersect(rect, blocked))
        shift = abs(bx - preferred_bx) + abs(by - preferred_by)
        clamp_shift = abs(bx - candidate_bx) + abs(by - candidate_by)
        score = overlap_count * 1_000_000 + clamp_shift * 500 + shift
        if best_score is None or score < best_score:
            best_score = score
            best_position = (bx, by)

    if best_position is None:
        return clamp_label_box(preferred_bx, preferred_by, box_w, box_h, width, height)
    return best_position


def draw_label_box(
    draw: ImageDraw.ImageDraw,
    bx: float,
    by: float,
    box_w: float,
    box_h: float,
    label: str,
    color: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    text_x: float,
    text_y: float,
) -> None:
    draw.rounded_rectangle(
        (bx, by, bx + box_w, by + box_h),
        radius=10,
        fill="white",
        outline=color,
        width=2,
    )
    draw.text((bx + text_x, by + text_y), label, font=font, fill="#213247")


def draw_marker_badge(
    draw: ImageDraw.ImageDraw,
    x: float,
    y: float,
    color: str,
) -> None:
    draw.ellipse(
        (x - MARKER_RADIUS, y - MARKER_RADIUS, x + MARKER_RADIUS, y + MARKER_RADIUS),
        fill=color,
        outline="white",
        width=4,
    )
    draw.ellipse((x - 4, y - 4, x + 4, y + 4), fill="white")


def draw_number_badge(
    draw: ImageDraw.ImageDraw,
    x: float,
    y: float,
    number: int,
    color: str,
) -> None:
    num_font = load_font(NUMBER_FONT_SIZE)
    draw.ellipse(
        (x - NUMBERED_RADIUS, y - NUMBERED_RADIUS, x + NUMBERED_RADIUS, y + NUMBERED_RADIUS),
        fill=color,
        outline="white",
        width=4,
    )
    number_text = str(number)
    bbox = num_font.getbbox(number_text)
    text_x = x - (bbox[0] + bbox[2]) / 2
    text_y = y - (bbox[1] + bbox[3]) / 2
    draw.text((text_x, text_y), number_text, font=num_font, fill="white")


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
        "fit_bounds": True,
        "fit_padding": 112,
        "max_zoom": 15,
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
    center = tuple(spec.get("center", (0.0, 0.0)))
    zoom = int(spec.get("zoom", 12))
    width = int(spec.get("width", 1320))
    height = int(spec.get("height", 860))
    route_color = str(spec.get("route_color", "#d35d3f"))
    route_width = int(spec.get("route_width", 5))
    fit_bounds = bool(spec.get("fit_bounds", False))
    fit_padding = int(spec.get("fit_padding", 112))
    min_zoom = int(spec.get("min_zoom", 6))
    max_zoom = int(spec.get("max_zoom", 16))

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
        if fit_bounds and reference_points:
            image, left, top, zoom = fit_map_view(
                reference_points,
                width,
                height,
                min_zoom=min_zoom,
                max_zoom=max_zoom,
                padding=fit_padding,
            )
        else:
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

    label_font = load_font(LABEL_FONT_SIZE)
    prepared_stops: list[dict[str, object]] = []
    for stop in stops:
        lat, lon = stop["coord"]
        x, y = projector(float(lat), float(lon))
        kind = stop.get("kind", "marker")
        label_dx = int(stop.get("label_dx", 12))
        label_dy = int(stop.get("label_dy", -45 if kind == "marker" else -46))
        radius = NUMBERED_RADIUS if kind == "numbered" else MARKER_RADIUS
        box_w, box_h, text_x, text_y = measure_label_box(str(stop["label"]), label_font)
        prepared_stops.append(
            {
                "stop": stop,
                "x": x,
                "y": y,
                "kind": kind,
                "radius": radius,
                "label_dx": label_dx,
                "label_dy": label_dy,
                "box_w": box_w,
                "box_h": box_h,
                "text_x": text_x,
                "text_y": text_y,
            }
        )

    blocked_rects = [
        (
            stop["x"] - stop["radius"] - LABEL_BLOCK_MARGIN,
            stop["y"] - stop["radius"] - LABEL_BLOCK_MARGIN,
            stop["x"] + stop["radius"] + LABEL_BLOCK_MARGIN,
            stop["y"] + stop["radius"] + LABEL_BLOCK_MARGIN,
        )
        for stop in prepared_stops
    ]

    for stop in prepared_stops:
        bx, by = choose_label_box(
            float(stop["x"]),
            float(stop["y"]),
            float(stop["box_w"]),
            float(stop["box_h"]),
            int(stop["label_dx"]),
            int(stop["label_dy"]),
            int(stop["radius"]),
            width,
            height,
            blocked_rects,
        )
        stop["label_bx"] = bx
        stop["label_by"] = by
        blocked_rects.append(
            (
                bx - LABEL_BLOCK_MARGIN,
                by - LABEL_BLOCK_MARGIN,
                bx + float(stop["box_w"]) + LABEL_BLOCK_MARGIN,
                by + float(stop["box_h"]) + LABEL_BLOCK_MARGIN,
            )
        )

    for stop in prepared_stops:
        stop_data = stop["stop"]
        x = float(stop["x"])
        y = float(stop["y"])
        color = str(stop_data.get("color", "#2d7be0"))
        if stop["kind"] == "numbered":
            draw_number_badge(draw, x, y, int(stop_data["number"]), color)
        else:
            draw_marker_badge(draw, x, y, color)
        draw_label_box(
            draw,
            float(stop["label_bx"]),
            float(stop["label_by"]),
            float(stop["box_w"]),
            float(stop["box_h"]),
            str(stop_data["label"]),
            color,
            label_font,
            float(stop["text_x"]),
            float(stop["text_y"]),
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
