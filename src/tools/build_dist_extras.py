# -*- coding: utf-8 -*-
"""从玩家自己的原版 Quake 4 数据现场补齐版权敏感物：

  1. fonts/chinese/strogg_* 与 r_strogg 基础页          — 从 pak001 提取并生成宽表
  2. guis/hud.gui                                       — HUD 中文排版补丁
  3. guis/hud_strogg.gui + wristcomm_strogg.gui          — 改造后 HUD 中文排版
  4. guis/common/strogg/health_station*.gui               — 生命补给器文本
  5. guis/common/exitlevel.gui                            — 改造前撤离屏文字对齐
  6. guis/maps/medlabs/med1_textchange.gui               — 神经细胞植入转译动画中文化
  7. guis/movers/strogg/activate_lift*.gui               — 电梯面板文字对齐
  8. guis/monitors/strogg 等状态面板                    — 转译后四字短语居中
  9. zzz_vo_chinese_alias.pk4（含 sound/vo_chinese/*）  — 中文语音路径别名（英文原声）

这些资产因涉及 Raven Software / id Software 版权，不能随汉化补丁一起分发；
玩家运行本脚本从自己合法拥有的原版数据里现场生成到 savedata 树，
不修改玩家的原版游戏目录、不复制原始音频到别处，仅在 zip 内改路径。

用法（Windows）：
  python build_dist_extras.py --game-dir "C:\\Program Files (x86)\\Steam\\steamapps\\common\\Quake 4"

或由 dist\\postinstall.cmd 自动调用（会读取「启动汉化版.cmd」里的 GAME_DIR）。
"""
import argparse
import io
import os
import shutil
import struct
import sys
import zipfile
from pathlib import Path
from typing import Callable


FONTDAT_BASE_SIZE = 256 * 36 + 20
FONTDAT_MAGIC = 0x69647466
FONTDAT_VERSION = 0x00010001
R_STROGG_DROP_DELTA = {12: 1, 24: 1, 48: 2}


# ---- med1_textchange.gui 补丁：按 windowDef 名字定位，避免行号/上下文歧义 ----
# 可读侧（r_strogg 字体格）字母 → 中文；不用到的格 text 置空；rect x 平移让中文居中。
# 依据：docs/localization-guide.md § Strogg 转译动画机制
MEDLAB_EDITS = {
    "t_ar1":  {"x": 80,  "text": "神"},
    "t_ar2":  {"x": 126, "text": "经"},
    "t_ar3":  {"x": 172, "text": "细"},
    "t_ar4":  {"x": 218, "text": "胞"},
    "t_ar5":  {"text": ""},
    "t_ar6":  {"text": ""},
    "t_ar7":  {"text": ""},
    "t_ar8":  {"text": ""},
    "t_ar9":  {"text": ""},
    "t_ar10": {"x": 400, "text": "已"},
    "t_ar11": {"x": 446, "text": "植"},
    "t_ar12": {"x": 492, "text": "入"},
    "t_ar13": {"text": ""},
    "t_ar14": {"text": ""},
    "t_ar15": {"text": ""},
    "t_ar16": {"text": ""},
    "t_ar17": {"text": ""},
    "t_ar18": {"text": ""},
    "t_sr1":  {"x": 120, "text": "实"},
    "t_sr2":  {"x": 166, "text": "验"},
    "t_sr3":  {"x": 212, "text": "体"},
    "t_sr4":  {"text": ""},
    "t_sr5":  {"text": ""},
    "t_sr6":  {"text": ""},
    "t_sr7":  {"text": ""},
}


def patch_mainmenu_gui(data: bytes) -> bytes:
    """mainmenu.gui 补丁：三按钮 rect y+4 + credits 段职位汉化（2026-07-18）。

    - 设置页 set_sys_t_auto/adv/b9 三按钮文字 rect y+4 让 CJK 视觉与容器中线对齐
    - credits 段（line 8543-17150）内 text 字段直接是英文硬编码不走 #str_id，
      共 36 条职位翻译（用完整 text 引号包裹匹配避免 "Motion Capture" 误伤
      "Motion Capture Lead" 等超集）；人名/工作室名不译

    按 bytes 处理：原版 mainmenu.gui 含非 UTF-8 字符（® 0xAE）；rect 数值全 ASCII。
    菜单 gui 不参与存档序列化，与 hud.gui r4 存档兼容约束无关。
    """
    edits = [
        (b"rect\t262,231,328,18", b"rect\t262,235,328,18"),  # set_sys_t_auto
        (b"rect\t262,262,328,18", b"rect\t262,266,328,18"),  # set_sys_t_adv
        (b"rect\t262,366,328,18", b"rect\t262,370,328,18"),  # set_sys_t_b9
    ]
    for old, new in edits:
        assert data.count(old) == 1, f"mainmenu.gui 找不到唯一匹配：{old!r}"
        data = data.replace(old, new)

    # credits 段职位汉化（长串在前避免子串误伤；例 Motion Capture Lead 先于 Motion Capture）
    credits_edits = [
        ("Additional Internal Quality Assurance", "追加内部品保"),
        ("Voice Over Recording, Editing and Post", "配音录制、剪辑与后期"),
        ("Fred Hooper - Assistant Art Lead", "Fred Hooper - 副美术组长"),
        ("Michael Pleva - Assistant Animation Lead", "Michael Pleva - 副动画组长"),
        ("Squirrel Eiserloh - Ritual code", "Squirrel Eiserloh - Ritual 代码"),
        ("Director of Product Development", "产品开发总监"),
        ("Casting and Voice Direction", "选角与配音指导"),
        ("Dan Hay - Cinematic Consultant", "Dan Hay - 过场顾问"),
        ("Theme for Quake4 Composed by", "Quake 4 主题曲作曲"),
        ("Theme for Quake4 Produced by", "Quake 4 主题曲制作"),
        ("Todd Rose - Ritual levels", "Todd Rose - Ritual 关卡"),
        ("Eric Fowler - Ritual code", "Eric Fowler - Ritual 代码"),
        ("Additional Motion Capture", "追加动作捕捉"),
        ("Internal Quality Assurance", "内部品保"),
        ("QUAKE II Xbox Programming", "QUAKE II Xbox 编程"),
        ("Carlo Vogelsang - Creative", "Carlo Vogelsang - 创意"),
        ("Additional Programming", "追加编程"),
        ("Production Coordinator", "制作协调"),
        ("Motion Capture Lead", "动作捕捉组长"),
        ("Art/Animation Lead", "美术/动画组长"),
        ("Additional Animation", "追加动画"),
        ("Executive Producer", "执行制作人"),
        ("Associate Producer", "副制作人"),
        ("Bidwell, Announcer", "Bidwell（播音员）"),
        ("Computer, Pilot VO", "电脑/飞行员配音"),
        ("Programming Leads", "编程组长"),
        ("Studio Head", "工作室负责人"),
        ("Line Producer", "现场制作人"),
        ("Motion Capture", "动作捕捉"),
        ("Additional Art", "追加美术"),
        ("Special Thanks", "特别鸣谢"),
        ("Level Design", "关卡设计"),
        ("Sound Design", "音效设计"),
        ("Design Lead", "设计组长"),
        ("Audio Leads", "音频组长"),
        ("Project Lead", "项目主管"),
    ]
    for en, zh in credits_edits:
        old_b = f'text\t"{en}"'.encode("ascii")
        new_b = f'text\t"{zh}"'.encode("utf-8")
        if old_b in data:
            data = data.replace(old_b, new_b)
    return data


def patch_hud_gui(text: str) -> str:
    """HUD 中文排版补丁。

    底稿必须是 pak021；除用户明确要求的无线电 shear/textalign 外，只改数值，
    避免破坏 GUI 存档状态的顺序结构。
    """
    radio_old = (
        'windowDef t_radio1\r\n\t\t{\r\n\t\t\trect\t545,6,81,12\r\n'
        '\t\t\tvisible\t1\r\n\t\t\tforecolor\t1,1,1,1\r\n'
        '\t\t\ttext\t"#str_200272"\r\n\t\t\ttextscale\t0.2'
    )
    radio_new = (
        'windowDef t_radio1\r\n\t\t{\r\n\t\t\trect\t552,3,72,22\r\n'
        '\t\t\tshear\t0,-.22\r\n\t\t\ttextalign\t1\r\n'
        '\t\t\tvisible\t1\r\n\t\t\tforecolor\t1,1,1,1\r\n'
        '\t\t\ttext\t"#str_200272"\r\n\t\t\ttextscale\t0.45'
    )
    assert text.count(radio_old) == 1, "hud.gui 找不到唯一的 t_radio1 原版块"
    text = text.replace(radio_old, radio_new)

    edits = [
        ("rect\t545,13,81,12", "rect\t556,999,72,14"),  # t_radio2 隐藏
        ("rect\t0,42,640,40",  "rect\t0,48,640,40"),   # ws_name 切枪武器名下移
        # 关卡末尾大门 EXIT 标签重定向 str_200013 -> str_200379 (撤离，避免误伤主菜单)
        ('text\t"#str_200013"', 'text\t"#str_200379"'),  # p_exit_text
        ("rect\t0,64,640,20", "rect\t0,110,640,20"),  # quicksave_msg
    ]
    for old, new in edits:
        assert text.count(old) == 1, f"hud.gui 找不到唯一匹配：{old!r}"
        text = text.replace(old, new)

    bracket_old = (
        'text\t"#str_200277"\r\n\t\t\tfont\t"fonts/marine"\r\n'
        '\t\t\ttextalign\t1\r\n'
        '\t\t\tforecolor\t0.686,0.870,0.564,"brackets::alpha"\r\n'
        '\t\t\ttextscale\t.25'
    )
    bracket_new = bracket_old[:-3] + '.4'
    assert text.count(bracket_old) == 1, "hud.gui 找不到唯一的 bracket_text 原版块"
    return text.replace(bracket_old, bracket_new)


def patch_hud_strogg_gui(text: str) -> str:
    """改造后 HUD：无线电单行排版，并同步保存提示位置。"""
    radio_old = (
        'windowDef t_radio1\r\n\t\t{\r\n\t\t\trect\t546,9,81,12\r\n'
        '\t\t\tvisible\t1\r\n\t\t\tforecolor\t1,1,1,1\r\n'
        '\t\t\ttext\t"#str_200272"\r\n\t\t\ttextscale\t0.16'
    )
    radio_new = (
        'windowDef t_radio1\r\n\t\t{\r\n\t\t\trect\t552,3,72,22\r\n'
        '\t\t\tshear\t0,.22\r\n\t\t\ttextalign\t1\r\n'
        '\t\t\tvisible\t1\r\n\t\t\tforecolor\t1,1,1,1\r\n'
        '\t\t\ttext\t"#str_200272"\r\n\t\t\ttextscale\t0.45'
    )
    assert text.count(radio_old) == 1, \
        "hud_strogg.gui 找不到唯一的 t_radio1 原版块"
    text = text.replace(radio_old, radio_new)

    edits = [
        ("rect\t547,17,81,12", "rect\t556,999,72,14"),
        ("rect\t0,64,640,20", "rect\t0,110,640,20"),
    ]
    for old, new in edits:
        assert text.count(old) == 1, \
            f"hud_strogg.gui 找不到唯一匹配：{old!r}"
        text = text.replace(old, new)
    return text


def patch_health_station_gui(text: str) -> str:
    """只在生命补给器内把通用“站点”改为上下文明确的“补给站”。"""
    old = 'text\t"#str_200871"'
    new = 'text\t"补给站"'
    assert text.count(old) == 1, "health_station.gui 找不到唯一的站点文本"
    return text.replace(old, new)


def patch_window_property(text: str, window: str, prop: str,
                          old_value: str, new_value: str) -> str:
    """在唯一 windowDef 的直属属性中做一次精确替换。"""
    lines = text.splitlines(keepends=True)
    window_hits = 0
    property_hits = 0
    for i, line in enumerate(lines):
        if line.strip() != f"windowDef {window}":
            continue
        window_hits += 1
        j = i + 1
        while j < len(lines) and lines[j].strip() != "}":
            stripped = lines[j].strip()
            if stripped.startswith(f"{prop}\t"):
                expected = f"{prop}\t{old_value}"
                assert stripped == expected, \
                    f"{window}.{prop} 当前值异常：{stripped!r}"
                prefix = lines[j][: lines[j].index(prop)]
                eol = "\r\n" if lines[j].endswith("\r\n") else "\n"
                lines[j] = f"{prefix}{prop}\t{new_value}{eol}"
                property_hits += 1
            j += 1
    assert window_hits == 1, f"windowDef {window} 匹配数异常：{window_hits}"
    assert property_hits == 1, \
        f"{window}.{prop} 匹配数异常：{property_hits}"
    return "".join(lines)


def patch_health_station_strogg_gui(text: str) -> str:
    """改造前补给器保留原英文词长，并校正三行 Strogg 文字基线。"""
    rect_edits = [
        ("r_text1", "272,90,347,48", "272,85,347,48"),
        ("r_text2", "272,130,347,48", "272,125,347,48"),
        ("r_text3", "272,170,347,48", "272,165,347,48"),
    ]
    for window_name, old_rect, new_rect in rect_edits:
        text = patch_window_property(
            text, window_name, "rect", old_rect, new_rect)

    edits = [
        ("r_text1", '"#str_200960"', '"stroyent"'),
        ("r_text2", '"#str_200961"', '"health"'),
        ("r_text3", '"#str_200871"', '"station"'),
    ]
    for window, old, new in edits:
        text = patch_window_property(text, window, "text", old, new)
    return text


def patch_exitlevel_gui(text: str) -> str:
    """改造前撤离屏保留完整 EXIT，并与可读窗口共用纵向中心。"""
    text = patch_window_property(
        text, "t_exit", "rect", "0,291,640,165", "0,270,640,165")
    return patch_window_property(
        text, "t_exit", "text", '"#str_200379"', '"exit"')


def patch_sys_offline_gui(text: str) -> str:
    """把“系统 / 现已离线”放回原可读文本区域的视觉中心。"""
    text = patch_window_property(
        text, "system_r", "rect", "186,169,275,63", "276,169,222,63")
    text = patch_window_property(
        text, "offline_r", "rect", "121,223,403,87", "202,223,322,87")
    return patch_window_property(
        text, "offline_r", "text", '"#str_200402"', '"#str_200778"')


def patch_static4_gui(text: str) -> str:
    """居中 static4 的“系统 / 现已离线”可读分支。"""
    text = patch_window_property(
        text, "system_r", "rect", "169,302,305,77", "276,302,247,77")
    text = patch_window_property(
        text, "offline_r", "rect", "78,347,489,102", "206,355,361,102")
    text = patch_window_property(
        text, "offline_r", "textscale", "2", "1.6")
    return patch_window_property(
        text, "offline_r", "text", '"#str_200402"', '"#str_200778"')


def patch_directional_offline_gui(text: str) -> str:
    """保留轨道面板错层构图，分别居中两行四字状态。"""
    text = patch_window_property(
        text, "top_text", "rect", "202,40,410,180", "261,40,351,180")
    text = patch_window_property(
        text, "btm_text", "rect", "97,133,507,239", "199,133,405,239")
    return patch_window_property(
        text, "btm_text", "text", '"#str_200402"', '"#str_200778"')


def patch_warn_electrical_gui(text: str) -> str:
    """让电气警告的两个交替窗口显示相同文案和位置。"""
    text = patch_window_property(
        text, "warning", "rect", "104,329,431,73", "218,332,317,73")
    text = patch_window_property(
        text, "warning", "text", '"#str_200370"', '"#str_390000"')
    text = patch_window_property(
        text, "warning", "textscale", "1.6", "1.4")
    text = patch_window_property(
        text, "highvoltage", "rect", "58,341,515,54", "218,332,317,73")
    text = patch_window_property(
        text, "highvoltage", "text", '"#str_200372"', '"#str_390000"')
    return patch_window_property(
        text, "highvoltage", "textscale", "1.2", "1.4")


def patch_lift_gui(text: str) -> str:
    """校正 Strogg 与中文 r_strogg 两种状态的字号和中心。"""
    edits = [
        ("rect\t124,30,395,74", "rect\t150,17,395,74", 1),
        ("rect\t130,100,391,60", "rect\t155,87,391,60", 1),
        ("rect\t130,29,390,60", "rect\t155,18,390,60", 1),
        ("rect\t124,90,395,74", "rect\t155,79,395,74", 1),
        ("rect\t90,14,457,86", "rect\t273,31,457,86", 1),
        ("textscale\t1.6", "textscale\t1.3", 1),
        ("rect\t92,82,468,67", "rect\t237,101,468,67", 1),
        ("rect\t92,24,468,67", "rect\t237,34,468,67", 1),
        ("textscale\t1.2", "textscale\t0.9", 2),
        ("rect\t92,74,468,70", "rect\t267,94,468,70", 1),
        ("textscale\t1.38", "textscale\t1.0", 1),
    ]
    for old, new, expected in edits:
        assert text.count(old) == expected, \
            f"activate_lift.gui 匹配数异常：{old!r}，期望 {expected}"
        text = text.replace(old, new)

    strogg_texts = [
        ("t_activate", '"#str_200477"', '"activate"'),
        ("t_liftsys", '"#str_200382"', '"lift system"'),
        ("t_liftsys2", '"#str_200382"', '"lift system"'),
        ("t_intrans", '"#str_200550"', '"in transit"'),
    ]
    for window, old, new in strogg_texts:
        text = patch_window_property(text, window, "text", old, new)
    return text


def patch_medlab_gui(text: str) -> str:
    """按 windowDef 名字定位（t_ar1..18 / t_sr1..7），替换 rect x 与 text 字段。"""
    lines = text.splitlines(keepends=True)
    i = 0
    applied = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if stripped.startswith("windowDef "):
            name = stripped.split()[1]
            if name in MEDLAB_EDITS:
                edit = MEDLAB_EDITS[name]
                j = i + 1
                while j < len(lines) and lines[j].strip() != "}":
                    ln = lines[j]
                    ls = ln.strip()
                    if "x" in edit and ls.startswith("rect\t"):
                        # rect	18,351,50,59 → 保留缩进/前缀，只换 x
                        prefix = ln[: ln.index("rect")]
                        parts = ls.split()[1].split(",")
                        parts[0] = str(edit["x"])
                        eol = ln[-2:] if ln.endswith("\r\n") else ln[-1:]
                        lines[j] = f'{prefix}rect\t{",".join(parts)}{eol}'
                    if "text" in edit and ls.startswith("text\t\""):
                        prefix = ln[: ln.index("text")]
                        eol = ln[-2:] if ln.endswith("\r\n") else ln[-1:]
                        lines[j] = f'{prefix}text\t"{edit["text"]}"{eol}'
                    j += 1
                applied += 1
                i = j
        i += 1
    assert applied == len(MEDLAB_EDITS), \
        f"medlab 补丁未完全应用：{applied}/{len(MEDLAB_EDITS)}"
    return "".join(lines)


def write_utf8(dst: Path, text: str) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(text.encode("utf-8"))


def parse_wide_fontdat(data: bytes) -> tuple[int, tuple[int, ...], int, int]:
    """返回宽表页高、索引表、字形数和第一条字形记录偏移。"""
    if len(data) < FONTDAT_BASE_SIZE + 24:
        raise RuntimeError("中文参考 fontdat 缺少宽字符扩展段")
    magic, version, _num_files, _width, height = struct.unpack_from(
        "<IIiii", data, FONTDAT_BASE_SIZE)
    if magic != FONTDAT_MAGIC or version != FONTDAT_VERSION:
        raise RuntimeError("中文参考 fontdat 的宽字符扩展头异常")
    offset = FONTDAT_BASE_SIZE + 20
    num_indexes = struct.unpack_from("<i", data, offset)[0]
    offset += 4
    indexes_size = num_indexes * 4
    if num_indexes <= 0 or offset + indexes_size + 4 > len(data):
        raise RuntimeError("中文参考 fontdat 的索引表异常")
    indexes = struct.unpack_from(f"<{num_indexes}i", data, offset)
    offset += indexes_size
    num_glyphs = struct.unpack_from("<i", data, offset)[0]
    offset += 4
    if num_glyphs < 0 or offset + num_glyphs * 68 > len(data):
        raise RuntimeError("中文参考 fontdat 的字形表异常")
    return height, indexes, num_glyphs, offset


def extend_strogg_fontdat(original: bytes, codes: list[int], size: int) -> bytes:
    """在原版 Strogg 基础段后追加把中文稳定映射为外星符号的宽表。"""
    if len(original) != FONTDAT_BASE_SIZE:
        raise RuntimeError(f"原版 strogg_{size}.fontdat 尺寸异常")
    pool = []
    for code in (*range(97, 123), *range(65, 91), *range(48, 58)):
        record = struct.unpack_from("<9f", original, code * 36)
        if record[0] > 0 and record[1] > 0:
            pool.append(record)
    if not pool:
        raise RuntimeError(f"原版 strogg_{size}.fontdat 没有可用符号")

    codes = sorted(set(codes))
    if not codes:
        raise RuntimeError("中文参考 fontdat 没有宽字符")
    output = io.BytesIO()
    output.write(original)
    output.write(struct.pack(
        "<IIiii", FONTDAT_MAGIC, FONTDAT_VERSION, 1, 0, 0))
    num_indexes = codes[-1] + 1
    output.write(struct.pack("<i", num_indexes))
    indexes = [-1] * num_indexes
    for glyph_index, code in enumerate(codes):
        indexes[code] = glyph_index
    output.write(struct.pack(f"<{num_indexes}i", *indexes))
    output.write(struct.pack("<i", len(codes)))
    shader = f"{size}.tga".encode("ascii").ljust(32, b"\x00")
    for code in codes:
        output.write(struct.pack("<9f", *pool[(code * 2654435761) % len(pool)]))
        output.write(shader)
    return output.getvalue()


def build_readable_strogg_fontdat(
    original: bytes,
    chinese_reference: bytes,
    size: int,
) -> bytes:
    """组合原版 r_strogg 基础段与可复用 marine 图集的中文宽表。"""
    if len(original) != FONTDAT_BASE_SIZE:
        raise RuntimeError(f"原版 r_strogg_{size}.fontdat 尺寸异常")
    result = bytearray(original + chinese_reference[FONTDAT_BASE_SIZE:])
    page_height, _indexes, num_glyphs, glyph_offset = parse_wide_fontdat(result)
    if page_height <= 0:
        raise RuntimeError(f"r_strogg_{size} 中文参考图集高度异常")
    drop_delta = R_STROGG_DROP_DELTA[size]
    for index in range(num_glyphs):
        offset = glyph_offset + index * 68
        values = list(struct.unpack_from("<9f", result, offset))
        if values[0] > 0 and values[1] >= drop_delta:
            values[1] -= drop_delta
            values[6] += drop_delta * 2 / page_height
            struct.pack_into("<9f", result, offset, *values)
    return bytes(result)


def patch_readable_strogg_materials(material_path: Path) -> None:
    """r_strogg 基础页使用现场提取的原版贴图，宽表页继续复用 marine。"""
    text = material_path.read_text(encoding="utf-8")
    for size in (12, 24, 48):
        header = f"fonts/chinese/r_strogg_{size}.tga"
        old = (
            f'{header}\n{{\n\t{{\n\t\tblend blend\n\t\tcolored\n'
            f'\t\tmap "fonts/chinese/marine_{size}.tga"'
        )
        new = old.replace(
            f'map "fonts/chinese/marine_{size}.tga"',
            f'map "fonts/chinese/r_strogg_{size}.tga"',
        )
        old_count = text.count(old)
        new_count = text.count(new)
        if old_count == 1 and new_count == 0:
            text = text.replace(old, new)
        elif old_count == 0 and new_count == 1:
            continue
        else:
            raise RuntimeError(f"字体材质中 {header} 的基础页别名匹配数异常")
    material_path.write_text(text, encoding="utf-8")


def extract_strogg_fonts(pak001: Path, out_fonts: Path) -> None:
    """现场生成装饰 Strogg 与改造后可读 Strogg 字体。"""
    expected = {
        f"fonts/english/{family}_{size}.{extension}"
        for family in ("strogg", "r_strogg")
        for size in (12, 24, 48)
        for extension in ("fontdat", "tga")
    }
    with zipfile.ZipFile(pak001) as zf:
        available = set(zf.namelist())
        missing = sorted(expected - available)
        if missing:
            raise RuntimeError(
                f"{pak001.name} 缺少 Strogg 字体文件：" + "、".join(missing)
            )
        marine_references = {
            size: (out_fonts / f"marine_{size}.fontdat").read_bytes()
            for size in (12, 24, 48)
        }
        readable_references = {
            size: (out_fonts / f"r_strogg_{size}.fontdat").read_bytes()
            for size in (12, 24, 48)
        }
        _height, indexes, _glyphs, _offset = parse_wide_fontdat(
            marine_references[12])
        full_codes = [
            code for code, glyph_index in enumerate(indexes)
            if glyph_index >= 0
        ]
        full_codes.append(0xFFFD)
        for size in (12, 24, 48):
            _height, marine_indexes, _glyphs, _offset = parse_wide_fontdat(
                marine_references[size])
            _height, readable_indexes, _glyphs, _offset = parse_wide_fontdat(
                readable_references[size])
            missing_codes = [
                code for code, glyph_index in enumerate(readable_indexes)
                if glyph_index >= 0 and (
                    code >= len(marine_indexes) or marine_indexes[code] < 0)
            ]
            if missing_codes:
                preview = "、".join(
                    f"U+{code:04X}" for code in missing_codes[:8])
                raise RuntimeError(
                    f"marine_{size}.fontdat 缺少 r_strogg 字符：{preview}")
        out_fonts.mkdir(parents=True, exist_ok=True)
        for size in (12, 24, 48):
            strogg_base = zf.read(f"fonts/english/strogg_{size}.fontdat")
            (out_fonts / f"strogg_{size}.fontdat").write_bytes(
                extend_strogg_fontdat(strogg_base, full_codes, size))
            (out_fonts / f"strogg_{size}.tga").write_bytes(
                zf.read(f"fonts/english/strogg_{size}.tga"))

            readable_base = zf.read(f"fonts/english/r_strogg_{size}.fontdat")
            (out_fonts / f"r_strogg_{size}.fontdat").write_bytes(
                build_readable_strogg_fontdat(
                    readable_base, marine_references[size], size))
            (out_fonts / f"r_strogg_{size}.tga").write_bytes(
                zf.read(f"fonts/english/r_strogg_{size}.tga"))


def build_vo_alias_pk4(
    voice_paks: list[Path],
    out_pk4: Path,
    progress: Callable[[int, int], None] | None = None,
) -> int:
    """把英文语音改为中文语言路径并合并到一个 pk4。

    按文件名顺序合并 zpak_english*.pk4；后续补丁包中的同名条目覆盖基础包。
    """
    entries: dict[
        str,
        tuple[Path, str, int, tuple[int, int, int, int, int, int], int],
    ] = {}
    for voice_pak in voice_paks:
        with zipfile.ZipFile(voice_pak) as src:
            for info in src.infolist():
                if not info.filename.startswith("sound/vo_english/") or info.is_dir():
                    continue
                target = info.filename.replace(
                    "sound/vo_english/", "sound/vo_chinese/", 1)
                entries[target] = (
                    voice_pak,
                    info.filename,
                    info.compress_type,
                    info.date_time,
                    info.file_size,
                )

    if not entries:
        raise RuntimeError("zpak_english*.pk4 中没有找到英文语音文件")

    sources: dict[Path, zipfile.ZipFile] = {}
    total_bytes = sum(source_info[4] for source_info in entries.values())
    completed_bytes = 0
    reported_percent = -1
    try:
        with zipfile.ZipFile(out_pk4, "w", zipfile.ZIP_DEFLATED) as dst:
            for target, source_info in entries.items():
                source_path, source_name, compress_type, date_time, file_size = source_info
                source = sources.setdefault(source_path, zipfile.ZipFile(source_path))
                new_info = zipfile.ZipInfo(target)
                new_info.compress_type = compress_type
                new_info.date_time = date_time
                dst.writestr(new_info, source.read(source_name))
                completed_bytes += file_size
                percent = completed_bytes * 100 // max(total_bytes, 1)
                if progress is not None and percent != reported_percent:
                    progress(completed_bytes, total_bytes)
                    reported_percent = percent
    finally:
        for source in sources.values():
            source.close()
    return len(entries)


def extract_and_patch(pak: Path, entry: str, patch_fn, out_file: Path) -> None:
    with zipfile.ZipFile(pak) as zf:
        raw = zf.read(entry).decode("utf-8")
    write_utf8(out_file, patch_fn(raw))


def build_assets(
    game_dir: Path,
    out: Path,
    skip_vo: bool = False,
    progress: Callable[[float, str], None] | None = None,
) -> int:
    """从玩家的原版 pak 现场生成不可随补丁分发的运行资产。"""
    game_dir = Path(game_dir)
    q4base = game_dir / "q4base"
    pak001 = q4base / "pak001.pk4"
    pak014 = q4base / "pak014.pk4"
    pak021 = q4base / "pak021.pk4"
    for p in (pak001, pak014, pak021):
        if not p.exists():
            print(f"[错误] 找不到 {p}", file=sys.stderr)
            print("请检查 --game-dir 是否指向 Quake 4 安装目录 (1.4.2 补丁必需)。")
            return 1

    voice_paks = sorted(q4base.glob("zpak_english*.pk4"))
    if not skip_vo and not (q4base / "zpak_english.pk4").is_file():
        print(f"[错误] 找不到 {q4base / 'zpak_english.pk4'}", file=sys.stderr)
        print("请确认已安装 Quake 4 英文语音数据。", file=sys.stderr)
        return 1

    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    small_step = 0
    small_step_total = 17

    def advance(message: str) -> None:
        nonlocal small_step
        small_step += 1
        if progress is not None:
            progress(0.2 * small_step / small_step_total, message)

    print("[1/4] 提取 Strogg 外星文字体（pak001 → fonts/chinese/strogg_*）...", flush=True)
    extract_strogg_fonts(pak001, out / "fonts" / "chinese")
    patch_readable_strogg_materials(
        out / "materials" / "zzz_chinese_font_alias.mtr")
    advance("已提取 Strogg 字体")

    print("[2/4] 补丁 hud.gui（pak021 → guis/hud.gui，中文排版）...", flush=True)
    extract_and_patch(pak021, "guis/hud.gui",
                      patch_hud_gui, out / "guis" / "hud.gui")
    advance("已生成 HUD")

    print("[2b] 补丁 mainmenu.gui（pak021 → guis/mainmenu.gui，设置页 3 按钮 rect y+4）...", flush=True)
    with zipfile.ZipFile(pak021) as zf:
        mm = zf.read("guis/mainmenu.gui")
    mm_out = out / "guis" / "mainmenu.gui"
    mm_out.parent.mkdir(parents=True, exist_ok=True)
    mm_out.write_bytes(patch_mainmenu_gui(mm))
    advance("已生成主菜单")

    print("[2c] 补丁 wristcomm.gui（pak001 → guis/wristcomm.gui，quicksave_msg y=64→110）...", flush=True)
    with zipfile.ZipFile(pak001) as zf:
        wc = zf.read("guis/wristcomm.gui")
    old = b"rect\t0,64,640,20"
    assert wc.count(old) == 1, "wristcomm.gui 找不到唯一的 quicksave_msg"
    wc = wc.replace(old, b"rect\t0,110,640,20")
    (out / "guis" / "wristcomm.gui").write_bytes(wc)
    advance("已生成腕表界面")

    print("[2d] 补丁改造后 HUD 与腕表...", flush=True)
    extract_and_patch(pak014, "guis/hud_strogg.gui",
                      patch_hud_strogg_gui, out / "guis" / "hud_strogg.gui")
    with zipfile.ZipFile(pak001) as zf:
        wc_strogg = zf.read("guis/wristcomm_strogg.gui")
    old = b"rect\t0,64,640,20"
    assert wc_strogg.count(old) == 1, \
        "wristcomm_strogg.gui 找不到唯一的 quicksave_msg"
    wc_strogg = wc_strogg.replace(old, b"rect\t0,110,640,20")
    (out / "guis" / "wristcomm_strogg.gui").write_bytes(wc_strogg)
    advance("已生成改造后 HUD")

    print("[2e] 补丁 health_station.gui（Stroyent 生命补给站）...", flush=True)
    extract_and_patch(pak001, "guis/common/strogg/health_station.gui",
                      patch_health_station_gui,
                      out / "guis" / "common" / "strogg" / "health_station.gui")
    advance("已生成生命补给器界面")

    print("[2f] 补丁 health_station_s.gui（改造前完整 Strogg 字母）...", flush=True)
    extract_and_patch(pak001, "guis/common/strogg/health_station_s.gui",
                      patch_health_station_strogg_gui,
                      out / "guis" / "common" / "strogg" / "health_station_s.gui")
    advance("已生成改造前生命补给器界面")

    print("[2g] 补丁 exitlevel.gui（改造前 EXIT 纵向居中）...", flush=True)
    extract_and_patch(pak001, "guis/common/exitlevel.gui",
                      patch_exitlevel_gui,
                      out / "guis" / "common" / "exitlevel.gui")
    advance("已生成撤离界面")

    print("[3/4] 补丁 med1_textchange.gui（pak001 → 神经细胞植入转译动画中文化）...", flush=True)
    extract_and_patch(pak001, "guis/maps/medlabs/med1_textchange.gui",
                      patch_medlab_gui,
                      out / "guis" / "maps" / "medlabs" / "med1_textchange.gui")
    advance("已生成转译动画")

    print("[3b] 补丁 activate_lift.gui（pak001 → Strogg 文字对齐）...", flush=True)
    extract_and_patch(pak001, "guis/movers/strogg/activate_lift.gui",
                      patch_lift_gui,
                      out / "guis" / "movers" / "strogg" / "activate_lift.gui")
    advance("已生成电梯面板")

    lift_variants = [
        (pak014, "activate_lift_blue.gui"),
        (pak001, "activate_lift_once.gui"),
        (pak001, "activate_lift_once_blue.gui"),
    ]
    for pak, name in lift_variants:
        print(f"[3c] 补丁 {name}（Strogg 文字对齐）...", flush=True)
        extract_and_patch(pak, f"guis/movers/strogg/{name}",
                          patch_lift_gui,
                          out / "guis" / "movers" / "strogg" / name)
        advance(f"已生成 {name}")

    status_panels = [
        ("guis/monitors/strogg/sys_offline.gui", patch_sys_offline_gui),
        ("guis/monitors/strogg/static4.gui", patch_static4_gui),
        ("guis/monitors/strogg/tram/directional_offline.gui",
         patch_directional_offline_gui),
        ("guis/common/strogg/warn_electrical.gui",
         patch_warn_electrical_gui),
    ]
    for entry, patch_fn in status_panels:
        print(f"[3d] 补丁 {entry}（四字状态居中）...", flush=True)
        extract_and_patch(pak001, entry, patch_fn, out / entry)
        advance(f"已生成 {Path(entry).name}")

    if skip_vo:
        print("[4/4] 已跳过语音别名 pk4（--skip-vo）")
    else:
        pk4 = out / "zzz_vo_chinese_alias.pk4"
        print(f"[4/4] 生成中文语音路径别名 pk4（zpak_english*.pk4 → vo_chinese, {pk4.name}，约需 1-3 分钟）...", flush=True)
        def voice_progress(done: int, total: int) -> None:
            if progress is not None:
                progress(0.2 + 0.8 * done / max(total, 1), "正在生成语音别名")

        n = build_vo_alias_pk4(voice_paks, pk4, voice_progress)
        print(f"      OK：{n} 个音频文件已别名到 sound/vo_chinese/")

    print()
    print("全部补齐物已就位。")
    if progress is not None:
        progress(1.0, "补齐资源生成完成")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="补齐 Quake 4 汉化版权敏感资产")
    ap.add_argument("--game-dir", required=True,
                    help="原版 Quake 4 安装目录（包含 q4base 子目录）")
    ap.add_argument("--out", required=True,
                    help="补齐物输出根（一般 = dist\\savedata\\q4base）")
    ap.add_argument("--skip-vo", action="store_true",
                    help="跳过语音别名 pk4（调试用；正常玩家务必生成）")
    args = ap.parse_args()
    return build_assets(Path(args.game_dir), Path(args.out), args.skip_vo)


if __name__ == "__main__":
    sys.exit(main())
