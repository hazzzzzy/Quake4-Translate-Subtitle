#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""为官方 Quake4.exe 生成双字节中文运行资产。"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


LEAD_START = 0x80
LEAD_COUNT = 32
TRAIL_START = 0xA0
TRAIL_COUNT = 96
PAGE_COUNT = 32
CAPACITY = PAGE_COUNT * TRAIL_COUNT
FONT_SIZES = (12, 24, 48)
FONTDAT_SIZE = 256 * 36 + 20
ATLAS_SIZE = 1024
SUPERSAMPLE = 2
ASPECT = 0.75
PADDING = 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-q4base", type=Path, required=True)
    parser.add_argument("--output-q4base", type=Path, required=True)
    parser.add_argument("--font", type=Path, required=True)
    return parser.parse_args()


def decode_units(data: bytes):
    index = 3 if data.startswith(b"\xef\xbb\xbf") else 0
    while index < len(data):
        first = data[index]
        if first < 0x80:
            yield bytes((first,)), first
            index += 1
            continue

        width = 0
        if 0xC2 <= first <= 0xDF:
            width = 2
        elif 0xE0 <= first <= 0xEF:
            width = 3
        elif 0xF0 <= first <= 0xF4:
            width = 4
        if width and index + width <= len(data):
            candidate = data[index : index + width]
            try:
                text = candidate.decode("utf-8")
            except UnicodeDecodeError:
                text = ""
            if len(text) == 1:
                yield candidate, ord(text)
                index += width
                continue

        # 原版 GUI 中存在单字节 Latin-1 注册商标符号。
        yield bytes((first,)), first
        index += 1


def runtime_files(source: Path) -> list[Path]:
    return sorted((source / "strings").glob("*.lang")) + sorted(
        (source / "guis").rglob("*.gui")
    )


def collect_characters(files: list[Path]) -> list[int]:
    codepoints = {
        codepoint
        for path in files
        for _, codepoint in decode_units(path.read_bytes())
        if codepoint >= 0x80
    }
    result = sorted(codepoints)
    if len(result) > CAPACITY:
        raise RuntimeError(
            f"字符集 {len(result)} 超过双字节容量 {CAPACITY}"
        )
    return result


def build_mapping(codepoints: list[int]) -> dict[int, bytes]:
    mapping: dict[int, bytes] = {}
    for index, codepoint in enumerate(codepoints):
        page, slot = divmod(index, TRAIL_COUNT)
        mapping[codepoint] = bytes((LEAD_START + page, TRAIL_START + slot))
    return mapping


def transcode(data: bytes, mapping: dict[int, bytes]) -> bytes:
    output = bytearray()
    for raw, codepoint in decode_units(data):
        if codepoint < 0x80:
            output += raw
        else:
            output += mapping[codepoint]
    return bytes(output)


def rasterize(font: ImageFont.FreeTypeFont, character: str, drop: int):
    advance = font.getlength(character)
    ascent, descent = font.getmetrics()
    xskip = max(1, round(advance * ASPECT / SUPERSAMPLE))
    margin = 4
    canvas = Image.new(
        "L",
        (int(advance) + ascent + descent + 2 * margin,
         (ascent + descent) * 2 + 2 * margin),
        0,
    )
    ImageDraw.Draw(canvas).text(
        (margin, margin), character, font=font, fill=255
    )
    ink = canvas.getbbox()
    if ink is None:
        return None, 0, 0, 0, xskip
    left, top_px, right, bottom = ink
    left = margin if left >= margin else left
    if (ascent - (top_px - margin)) % SUPERSAMPLE:
        top_px -= 1
    if (bottom - top_px) % SUPERSAMPLE:
        bottom += 1
    bitmap = canvas.crop((left, top_px, right, bottom))
    bitmap_width = max(
        SUPERSAMPLE,
        round(bitmap.size[0] * ASPECT / SUPERSAMPLE) * SUPERSAMPLE,
    )
    bitmap = bitmap.resize((bitmap_width, bitmap.size[1]), Image.Resampling.LANCZOS)
    if drop:
        padded = Image.new(
            "L", (bitmap_width, bitmap.size[1] + drop * SUPERSAMPLE), 0
        )
        padded.paste(bitmap, (0, drop * SUPERSAMPLE))
        bitmap = padded
    glyph_top = (ascent - (top_px - margin)) // SUPERSAMPLE
    return (
        bitmap,
        bitmap_width // SUPERSAMPLE,
        bitmap.size[1] // SUPERSAMPLE,
        glyph_top,
        xskip,
    )


def write_tga(image: Image.Image, path: Path) -> None:
    width, height = image.size
    header = struct.pack(
        "<BBBHHBHHHHBB", 0, 0, 10, 0, 0, 0, 0, 0,
        width, height, 32, 0x20
    )
    pixels = np.asarray(image, dtype=np.uint8)
    output = bytearray()
    for row in pixels:
        changes = np.flatnonzero(np.diff(row)) + 1
        starts = np.concatenate(([0], changes))
        ends = np.concatenate((changes, [width]))
        for start, end in zip(starts, ends):
            value = int(row[start])
            pixel = bytes((value, value, value, value))
            remaining = int(end - start)
            while remaining:
                count = min(remaining, 128)
                output.append(0x80 | (count - 1))
                output += pixel
                remaining -= count
    path.write_bytes(header + output)


def write_page_font(
    output: Path,
    source_font: Path,
    codepoints: list[int],
    page: int,
    size: int,
) -> tuple[int, int]:
    font = ImageFont.truetype(str(source_font), size * SUPERSAMPLE)
    drop = max(1, round(size / 12))
    image = Image.new("L", (ATLAS_SIZE, ATLAS_SIZE), 0)
    records = [(0, 0, 0, 0, 0.0, 0.0, 0.0, 0.0)] * 256
    x = y = row_height = 0
    written = 0
    first = page * TRAIL_COUNT
    for slot, codepoint in enumerate(codepoints[first : first + TRAIL_COUNT]):
        bitmap, width, height, top, xskip = rasterize(
            font, chr(codepoint), drop
        )
        glyph = TRAIL_START + slot
        if bitmap is None:
            records[glyph] = (0, 0, xskip, 0, 0.0, 0.0, 0.0, 0.0)
            continue
        bitmap_width, bitmap_height = bitmap.size
        if x + bitmap_width + PADDING > ATLAS_SIZE:
            x = 0
            y += row_height + PADDING
            row_height = 0
        if y + bitmap_height + PADDING > ATLAS_SIZE:
            raise RuntimeError(f"字体页溢出：page={page} size={size}")
        image.paste(bitmap, (x, y))
        records[glyph] = (
            width,
            height,
            xskip,
            top,
            x / ATLAS_SIZE,
            y / ATLAS_SIZE,
            (x + bitmap_width) / ATLAS_SIZE,
            (y + bitmap_height) / ATLAS_SIZE,
        )
        x += bitmap_width + PADDING
        row_height = max(row_height, bitmap_height)
        written += 1

    buffer = bytearray()
    for width, height, xskip, top, s, t, s2, t2 in records:
        buffer += struct.pack(
            "<9f", width, height, xskip, width, top, s, t, s2, t2
        )
    advances = [record[2] for record in records]
    tops = [record[3] for record in records]
    max_advance = max(advances, default=round(size * ASPECT))
    max_top = max(tops, default=size)
    buffer += struct.pack(
        "<5f", size, max_advance, max_top, max_advance - max_top, 0.0
    )
    stem = f"q4cn_p{page:02d}_{size}"
    (output / f"{stem}.fontdat").write_bytes(buffer)
    write_tga(image, output / f"{stem}.tga")
    return written, len(buffer)


def patch_base_font(data: bytes, size: int, advance: int, top: int) -> bytes:
    if len(data) < FONTDAT_SIZE:
        raise RuntimeError(f"fontdat 尺寸异常：{len(data)}")
    result = bytearray(data[:FONTDAT_SIZE])
    zero = struct.pack("<9f", *([0.0] * 9))
    metric = struct.pack(
        "<9f", 0.0, float(size), float(advance), 0.0, float(top),
        0.0, 0.0, 0.0, 0.0
    )
    for glyph in range(LEAD_START, LEAD_START + LEAD_COUNT):
        result[glyph * 36 : (glyph + 1) * 36] = zero
    for glyph in range(TRAIL_START, TRAIL_START + TRAIL_COUNT):
        result[glyph * 36 : (glyph + 1) * 36] = metric
    return bytes(result)


def copy_base_fonts(source: Path, output: Path, source_font: Path) -> None:
    families: set[tuple[str, int]] = set()
    for path in source.glob("*.fontdat"):
        stem, separator, size_text = path.stem.rpartition("_")
        if not separator or not size_text.isdigit():
            continue
        size = int(size_text)
        if size not in FONT_SIZES:
            continue
        families.add((stem, size))

    for family, size in sorted(families):
        font = ImageFont.truetype(str(source_font), size * SUPERSAMPLE)
        _, _, _, top, advance = rasterize(
            font, "中", max(1, round(size / 12))
        )
        source_dat = source / f"{family}_{size}.fontdat"
        output_dat = output / source_dat.name
        output_dat.write_bytes(
            patch_base_font(source_dat.read_bytes(), size, advance, top)
        )
        source_tga = source / f"{family}_{size}.tga"
        if source_tga.is_file():
            (output / source_tga.name).write_bytes(source_tga.read_bytes())


def main() -> int:
    args = parse_args()
    source = args.source_q4base.resolve()
    output = args.output_q4base.resolve()
    source_font = args.font.resolve()
    files = runtime_files(source)
    codepoints = collect_characters(files)
    mapping = build_mapping(codepoints)

    for path in files:
        relative = path.relative_to(source)
        destination = output / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(transcode(path.read_bytes(), mapping))

    font_output = output / "fonts" / "chinese"
    font_output.mkdir(parents=True, exist_ok=True)
    copy_base_fonts(source / "fonts" / "chinese", font_output, source_font)
    for page in range(PAGE_COUNT):
        for size in FONT_SIZES:
            write_page_font(font_output, source_font, codepoints, page, size)

    material_source = source / "materials" / "zzz_chinese_font_alias.mtr"
    if material_source.is_file():
        material_output = output / "materials" / material_source.name
        material_output.parent.mkdir(parents=True, exist_ok=True)
        material_output.write_bytes(material_source.read_bytes())

    rows = ["index\tlead\ttrail\tcodepoint\tcharacter"]
    for index, codepoint in enumerate(codepoints):
        encoded = mapping[codepoint]
        rows.append(
            f"{index}\t0x{encoded[0]:02X}\t0x{encoded[1]:02X}\t"
            f"U+{codepoint:04X}\t{chr(codepoint)}"
        )
    mapping_path = output.parent / "q4cn-official-mapping.tsv"
    mapping_path.write_text("\n".join(rows) + "\n", encoding="utf-8-sig")
    print(f"运行文件：{len(files)}")
    print(f"映射字符：{len(codepoints)}/{CAPACITY}")
    print(f"字体页：{PAGE_COUNT} x {len(FONT_SIZES)}")
    print(f"输出目录：{output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
