# -*- coding: utf-8 -*-
"""Quake 4 中文宽字库导出器（替代引擎 exportFont）。

引擎 exportFont 的三个缺陷（2026-07-17 诊断，字符间隙忽宽忽窄的根因）：
1. FT 紧贴位图丢弃左侧 bearing，且引擎绘制端（PaintChar）从不读 pitch/bearing，
   字形笔画全部左贴字元格 → 空白堆右侧，"目 标"式伪空格；
2. 位图宽度按 4 像素对齐量化 → 空隙台阶跳变；
3. xSkip = advance + 1 手加字距 → 整体偏松。

本导出器的对策：
- bearing 烘进位图（位图含左侧留白列，宽 = bearing + ink）；
- xSkip = 真实 advance（四舍五入）；
- 基础段（ASCII/Latin-1）通常由同一 TTF 自渲染（bearing 烘焙 + 真
  advance）；纯数字 HUD 使用的 chain/r_strogg 以及 marine（武器弹药 +
  终端面板数字）则保留原版基础段，中文宽字表仍用思源黑体；
- 标点修形：U+2014 —— 拉伸至满格宽（两个连排不断线）、U+2014/U+2026
  垂直居中到 CJK 视觉中线（雅黑原生贴底线，中文排版难看）；
- 宽表只收 charcode >= 256（引擎 GLYPH_END=255 以下永远走基础段）；
- 真 48 号（引擎按槽位取 glyphScale=48/48=1，旧"48=24 复制"实际导致
  大字号文本减半，一并修正）；48 号用 UI 字符集（对白不会以大字号渲染）。
- 宽高比预压缩（2026-07-17 用户反馈"字体过于拉伸，宽大于高"）：引擎 GUI
  按 640×480 虚拟坐标绘制，AdjustCoords 横向 ×(屏宽/640)、纵向 ×(屏高/480)，
  16:9 下横向多拉伸 4/3（DeviceContext.cpp）——方块汉字被拉扁宽。字形位图
  与 xSkip 按 ASPECT=0.75 预压缩，屏显恢复设计比例（ASCII 同步压缩保证
  混排节奏一致）。仅对 16:9 分辨率正确，换非 16:9 屏需改 ASPECT 重导。
- 体积优化（2026-07-17）：TGA 用 RLE(type 10) 压缩（引擎 LoadTGA 支持，
  含 0x20 顶向下翻转）；同源家族共享贴图——同 (ttf,索引) 的家族只有第一个
  真渲染，其余复制 fontdat（宽表 shaderName 只存"1_24.tga"后缀，家族前缀
  是引擎运行时用 fontName 拼的，故字节全同）+ 生成 .mtr 材质别名把
  fonts/chinese/<别名家族>_*.tga 的 map 指到本尊贴图（FindMaterial 显式
  decl 优先于隐式生成，模板照抄 idMaterial::SetDefaultText），
  显存/磁盘均只留一份。

fontdat 布局（引擎 tr_font.cpp RegisterFont/_RAVEN + R_Font_ParseWideFont）：
  基础段 256 × 9 float（imageWidth,imageHeight,xSkip,pitch,top,s,t,s2,t2）
  + 5 float 头（pointSize,maxWidth,maxHeight,差值,0）
  + 宽表：magic u32(0x69647466) version u32(0x00010001) numFiles i32 width i32 height i32
    numIndexes i32, indexes[n] i32, numGlyphs i32,
    每字形 9 float + shaderName char[32]（如 "1_24.tga"，
    引擎拼成 fonts/chinese/<家族>_1_24.tga 找材质）
TGA：32 位未压缩 BGRA，描述子 0x20（自顶向下），白色 + alpha 覆盖度。
"""
import io
import os
import struct
import sys
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

REPOSITORY = Path(__file__).resolve().parents[2]
Q4BASE = Path(r"D:\Quake 4\q4base")
OUT_DIR = REPOSITORY / "savedata" / "q4base" / "fonts" / "chinese"
MTR_PATH = REPOSITORY / "savedata" / "q4base" / "materials" / "zzz_chinese_font_alias.mtr"
TRANS = REPOSITORY / "src" / "translations"
ENG_CACHE = REPOSITORY / "assets" / "english_fonts"

MAGIC = 0x69647466
VERSION = 0x00010001
PAGE = 2048
PAD = 1
# 超采样倍率（2026-07-17 用户拍板全档 2x）：位图按 2 倍分辨率渲染进贴图，
# 度量按名义字号写，引擎双线性过滤缩小采样=抗锯齿。解决"源分辨率<屏显尺寸
# 被放大出锯齿"（名牌/HUD/医疗站/字幕全档受益）；2x 下 AA 渲染灰阶均匀，
# 无 12px 直渲时的发虚参差问题。
SS = 2
# 宽高比预压缩：引擎 GUI 虚拟 640×480 拉伸到实机分辨率，16:9 下横向多拉
# 4/3 倍；字形宽度与 xSkip 预乘 (640/480)/(1920/1080)=0.75 抵消。
# 换非 16:9 分辨率玩需按 (4/3)/(屏宽/屏高) 改此值重导。
ASPECT = 0.75

# 字体沿革：msyhbd 粗体 12 号粘连（否）→ msyh 常规（r4 基线）→
# 2026-07-17 实机 A/B（雅黑/思源Md/HarmonyOS Md/MiSans Md，tmp\font_ab_compare.png）
# 用户拍板思源黑体 Medium：字幕小字厚实清晰、OFL 开源可随补丁分发
UI_TTF = r"D:\PROJECT\quake4-translate-subtitle\assets\fonts\SourceHanSansSC-Medium.otf"
# ORIGINAL = 直通原版外星字形（2026-07-17 用户拍板）：strogg 家族恢复 pak001
# 原版符号字体（改造前终端"看不懂"氛围），并合成宽表把 CJK 稳定伪随机映射到
# 原版符号——混用 str（外星装饰窗+可读窗共用一条译文，24/27 个）的中文在装饰
# 窗自动"外星化"，无需回退译文或解耦 gui。r_strogg（改造后可读侧）的 CJK
# 宽字表使用思源黑体 Medium，ASCII/数字基础段保留原版 r_strogg 字形。
ORIGINAL = ("<original>", -1)
FAMILIES = {
    # 家族: (ttf 路径, ttc 索引)；ORIGINAL=直通原版
    "chain":    (UI_TTF, 0),
    "marine":   (UI_TTF, 0),
    "lowpixel": (UI_TTF, 0),
    "profont":  (UI_TTF, 0),
    "strogg":   ORIGINAL,
    "r_strogg": (UI_TTF, 0),
}
SIZES = (12, 24, 48)


def extract_english():
    """从 pak001 提取原版英文 fontdat 到工程缓存（仅作 5 float 头参考，不再拼接）"""
    ENG_CACHE.mkdir(parents=True, exist_ok=True)
    zf = zipfile.ZipFile(Q4BASE / "pak001.pk4")
    for fam in FAMILIES:
        for size in SIZES:
            name = f"fonts/english/{fam}_{size}.fontdat"
            dst = ENG_CACHE / f"{fam}_{size}.fontdat"
            if not dst.exists():
                dst.write_bytes(zf.read(name))
    zf.close()


def tsv_chars(paths):
    chars = set()
    for p in paths:
        for line in p.read_text(encoding="utf-8-sig").splitlines()[1:]:
            cols = line.split("\t")
            for c in cols[2:5]:  # 中文列（radio 表中文在第 5 列，主表在第 3 列，都覆盖）
                chars.update(c)
    return {c for c in chars if ord(c) >= 256}


def build_charsets():
    """全量字符集（12/24 号）与 UI 字符集（48 号），均只含 >=256"""
    gb = set()
    for hi in range(0xA1, 0xF8):
        for lo in range(0xA1, 0xFF):
            try:
                ch = bytes((hi, lo)).decode("gb2312")
                if ord(ch) >= 256:
                    gb.add(ch)
            except UnicodeDecodeError:
                pass
    full = gb | tsv_chars([
        TRANS / "ui_code.tsv", TRANS / "ui_guis.tsv", TRANS / "ui_maps.tsv",
        TRANS / "ui_mappack.tsv", TRANS / "dialogue_lips.tsv",
        TRANS / "radio_chatter.tsv", TRANS / "ai_vo_gap.tsv",
    ])
    ui = tsv_chars([
        TRANS / "ui_code.tsv", TRANS / "ui_guis.tsv", TRANS / "ui_maps.tsv",
        TRANS / "ui_mappack.tsv",
    ])
    # 全角标点保底（两套都要）
    punct = set("，。！？、；：……——“”‘’（）《》【】·￥")
    return sorted(full | punct), sorted(ui | punct)


def rasterize(font, ch, drop=0):
    """返回 (2x bitmap 或 None, w名义, h名义, top名义, xSkip名义)；bearing 烘进位图。

    drop（名义 px）：在位图顶部烘入透明行、top 度量不变 → 墨迹相对基线整体
    下移 drop 像素。用于 CJK 视觉对中（2026-07-18 用户反馈：汉字无降部且
    墨迷顶得高，在为拉丁字母设计的窗格里普遍偏上——地名/载入中/设置行/
    切枪武器名等）。只对宽表字形（charcode>=256）使用，ASCII 不动。

    font 必须按 size*SS 加载。位图保持 2x 分辨率进图集；度量除以 SS 写名义值
    （引擎按 int 读度量，故裁剪边界对齐 SS 倍数，避免 ±0.5px 基线抖动）。
    2x 下用灰度 AA 渲染（灰阶均匀，无 12px 直渲的发虚参差；引擎双线性
    缩小采样完成最终抗锯齿）。历史教训：1x 灰度 AA 发虚参差、1x 单色放大
    锯齿，均被用户否决。
    """
    try:
        adv = font.getlength(ch)
    except Exception:
        return None, 0, 0, 0, 0
    ascent, descent = font.getmetrics()
    xskip = max(1, round(adv * ASPECT / SS))  # 步进随宽高比预压缩
    P = 4  # 画布留边
    cw = int(adv) + ascent + descent + 2 * P
    chh = (ascent + descent) * 2 + 2 * P
    canvas = Image.new("L", (cw, chh), 0)
    d = ImageDraw.Draw(canvas)
    d.text((P, P), ch, font=font, fill=255)  # (P,P)=左-ascender 原点
    ink = canvas.getbbox()
    if ink is None:
        return None, 0, 0, 0, xskip  # 空白字形（全角空格等）
    ix0, iy0, ix1, iy1 = ink
    x_from = P if ix0 >= P else ix0  # 正 bearing 烘进位图；负 bearing 从墨迹起裁
    # 边界对齐 SS：top 与宽高的名义值必须是整数
    if (ascent - (iy0 - P)) % SS:
        iy0 -= 1
    if (iy1 - iy0) % SS:
        iy1 += 1
    bmp = canvas.crop((x_from, iy0, ix1, iy1))
    # 宽度按 ASPECT 预压缩（含烘进的 bearing，等比缩放），并取整为 SS 倍数
    bw = max(SS, round(bmp.size[0] * ASPECT / SS) * SS)
    bmp = bmp.resize((bw, bmp.size[1]), Image.LANCZOS)
    if drop > 0:  # 顶部烘入透明行：墨迹相对基线下移 drop 名义 px
        padded = Image.new("L", (bw, bmp.size[1] + drop * SS), 0)
        padded.paste(bmp, (0, drop * SS))
        bmp = padded
    top = (ascent - (iy0 - P)) // SS
    return bmp, bw // SS, bmp.size[1] // SS, top, xskip


def write_tga(img, path):
    """32 位 RLE（type 10）BGRA、自顶向下（描述子 0x20），白色 + alpha。

    引擎 LoadTGA 支持 type 10 且按 0x20 位翻转（Image_files.cpp）。字体页
    大片黑底，逐行等值区段全部编成 RLE 包（单像素段 5 字节与 raw 相同，
    不做 raw 批量，实现简单），实测缩 5-10 倍。
    """
    w, h = img.size
    header = struct.pack("<BBBHHBHHHHBB", 0, 0, 10, 0, 0, 0, 0, 0, w, h, 32, 0x20)
    a = np.asarray(img, dtype=np.uint8)  # L 模式，h×w
    out = bytearray()
    for row in a:
        change = np.flatnonzero(np.diff(row)) + 1
        starts = np.concatenate(([0], change))
        ends = np.concatenate((change, [w]))
        for s, e in zip(starts, ends):
            v = int(row[s])
            px = bytes((v, v, v, v))  # BGRA 四通道同值
            n = e - s
            while n > 0:
                c = min(n, 128)
                out.append(0x80 | (c - 1))
                out += px
                n -= c
    path.write_bytes(header + bytes(out))


BASE_PAGE = {12: 512, 24: 1024, 48: 2048}  # 2x 位图，基础页相应翻倍


def adjust_punct(cp, bmp, w, h, top, xskip, ref_center):
    """——(U+2014) 拉伸满格防断线；—/… 垂直居中到 CJK 视觉中线（名义度量）"""
    if cp == 0x2014 and bmp is not None:
        bmp = bmp.resize((xskip * SS, bmp.size[1]), Image.LANCZOS)
        w = xskip
    if cp in (0x2014, 0x2026) and bmp is not None and ref_center is not None:
        top = round(ref_center + h / 2.0)
    return bmp, w, top


def export(fam, size, chars):
    ttf, idx = FAMILIES[fam]
    font = ImageFont.truetype(ttf, size * SS, index=idx)  # 按超采样倍率加载
    eng_dat = (ENG_CACHE / f"{fam}_{size}.fontdat").read_bytes()
    assert len(eng_dat) == 256 * 36 + 20, f"英文 fontdat 尺寸异常 {fam}_{size}"
    # 原版数字方案：普通 HUD 的 chain、改造后 HUD 的 r_strogg、以及 marine
    # 家族（武器 viewmodel 弹药计数 + MCC 终端/医疗面板的数字编号）都保留
    # 各自原版 fontdat + tga 基础段，宽表仍保留思源中文。marine 单独纳入是
    # 为了让枪身弹药与军事终端的数字恢复原版方正字形（2026-08-01 用户反馈）。
    use_original_base = fam in ("chain", "r_strogg", "marine")

    # 字体 cmap（子集字体缺字直接跳过，引擎回退 '?'）
    try:
        from fontTools.ttLib import TTFont
        tt = TTFont(ttf, fontNumber=idx, lazy=True)
        cmap = set(tt.getBestCmap())
        tt.close()
    except Exception:
        cmap = None
    usable = [c for c in chars if cmap is None or ord(c) in cmap]

    # CJK 视觉下沉量（名义 px）：普通家族 12→1、24→2、48→4。r_strogg
    # 用在不可交互的 Strogg 面板时原版窗口基线更低，使用一半下沉量
    # 12→0、24→1、48→2，避免第三行压住面板下边线。
    drop = round(size / 24) if fam == "r_strogg" \
        else max(1, round(size / 12))
    # CJK 视觉中线参考（'中'），用于 ——/…… 垂直居中（名义度量，同 drop）
    bmp_ref, _, h_ref, top_ref, _ = rasterize(font, "中", drop)
    ref_center = (top_ref - h_ref / 2.0) if bmp_ref is not None else None

    # ASCII 基础段视觉对齐 CJK（2026-07-18 用户反馈：MCC 着陆场 里 MCC 顶部
    # 偏上）：正解=全档 ascii_drop = drop_cjk（12→1、24→2、48→4 名义 px）——
    # 用户观察的偏差是 M **视觉中线**低于 CJK 视觉中线（度量重推：
    # marine_24 rect(y=11,h=20)/textscale=0.36 → M 位图中线 = rect 顶+8.64，
    # 着 墨迹中线 = rect 顶+10.08 ≈ rect 中线 10，M 偏上 1.44 虚拟 px ≈ 3.2 屏 px）；
    # 因 CJK drop 让 CJK 视觉在 rect 里居中，ASCII 不 drop 就相对偏上。
    # ASCII 同幅下沉可让 M/O/A/数字 视觉中线也接近 rect 中线，与 CJK 齐平。
    # HUD 数字用 chain_24/marine_12，加 drop=1/2 视觉下沉 2-3 屏幕 px，
    # 需 patch_hud.py 补偿数字窗口 y-drop/h+drop 保裕度（如仍裁切）。
    ascii_drop = drop

    # ---- 基础段（0..255 同字体自渲染，独立单页）----
    if use_original_base:
        # 原版基础段：直接解析 eng_dat 的 256 条记录（每条 9float=36B），
        # 跳过自渲染、稍后拷贝原版 tga 而不是保存 base_img
        base_rec = []
        for i in range(256):
            r = struct.unpack_from("<9f", eng_dat, i * 36)
            # (imageWidth, imageHeight, xSkip, pitch, top, s, t, s2, t2)
            base_rec.append((int(r[0]), int(r[1]), int(r[2]), int(r[4]),
                             r[5], r[6], r[7], r[8]))
        base_img = None
    else:
        bp = BASE_PAGE[size]
        base_img = Image.new("L", (bp, bp), 0)
        base_rec = [(0, 0, 0, 0, 0.0, 0.0, 0.0, 0.0)] * 256  # w,h,xskip,top,s,t,s2,t2
        cx = cy = row_h = 0
        # 只渲染 ASCII：引擎存在按字节绘制的老路径（启动屏等），Latin-1 高位
        # 字形会把 UTF-8 字节显形成乱码（2026-07-17 用户反馈），高位留空=隐形
        for i in range(32, 127):
            ch = chr(i)
            if cmap is not None and i not in cmap:
                continue
            bmp, w, h, top, xskip = rasterize(font, ch, ascii_drop)
            if bmp is None:
                if xskip > 1:
                    base_rec[i] = (0, 0, xskip, 0, 0.0, 0.0, 0.0, 0.0)
                continue
            bw, bh = bmp.size  # 2x 像素尺寸（图集占位/UV 用）
            if cx + bw + PAD > bp:
                cx = 0
                cy += row_h + PAD
                row_h = 0
            if cy + bh + PAD > bp:
                break  # 基础页满（不应发生）
            base_img.paste(bmp, (cx, cy))
            base_rec[i] = (w, h, xskip, top, cx / bp, cy / bp, (cx + bw) / bp, (cy + bh) / bp)
            cx += bw + PAD
            row_h = max(row_h, bh)

    # ---- 宽表（>=256）----
    pages = []
    records = []        # (charcode, w, h, xskip, top, page, px, py)
    cx = cy = row_h = 0
    cur = None
    for ch in usable:
        bmp, w, h, top, xskip = rasterize(font, ch, drop)
        bmp, w, top = adjust_punct(ord(ch), bmp, w, h, top, xskip, ref_center)
        if bmp is None:
            if xskip > 1:  # 空白但占宽（全角空格）：无位图记录
                records.append((ord(ch), 0, 0, xskip, 0, -1, 0, 0))
            continue
        bw, bh = bmp.size  # 2x 像素尺寸
        if cur is None:
            cur = Image.new("L", (PAGE, PAGE), 0)
            pages.append(cur)
            cx = cy = row_h = 0
        if cx + bw + PAD > PAGE:
            cx = 0
            cy += row_h + PAD
            row_h = 0
        if cy + bh + PAD > PAGE:
            cur = Image.new("L", (PAGE, PAGE), 0)
            pages.append(cur)
            cx = cy = row_h = 0
        cur.paste(bmp, (cx, cy))
        records.append((ord(ch), w, h, xskip, top, len(pages) - 1, cx, cy))
        cx += bw + PAD
        row_h = max(row_h, bh)

    # ---- 写 fontdat ----
    base_tops = [r[3] for r in base_rec]
    buf = io.BytesIO()
    if use_original_base:
        # 原版基础段：256×36 记录（度量/UV 一律原版，数字/字母保持原版视觉）
        buf.write(eng_dat[:256 * 36])
        # 头（5float）：chain/r_strogg 主要显数字，沿用原版头（patch_hud 已据此
        # 调好 HUD 数字位置）；marine 大量用于中文文本，原版 maxHeight(~15) 远小于
        # 思源宽表字形(~23)，纯原版头会让中文基线偏高/行高塌缩，故取
        # max(原版maxHeight, 宽表maxTop) 维持原思源 marine 的行高（2026-08-01）。
        wide_tops = [r[4] for r in records if r[5] >= 0]
        _pts, _mw, _mh, _d, _ = struct.unpack_from("<5f", eng_dat, 256 * 36)
        if fam == "marine" and wide_tops:
            _mh = max(_mh, max(wide_tops))
            buf.write(struct.pack("<5f", _pts, _mw, _mh, _mw - _mh, 0.0))
        else:
            buf.write(eng_dat[256 * 36 : 256 * 36 + 20])
    else:
        for (w, h, xskip, top, s, t, s2, t2) in base_rec:
            buf.write(struct.pack("<9f", w, h, xskip, w, top, s, t, s2, t2))
        max_xskip = max(r[2] for r in base_rec)
        buf.write(struct.pack("<5f", size, max_xskip, max(base_tops),
                              max_xskip - max(base_tops), 0.0))
    buf.write(struct.pack("<IIiii", MAGIC, VERSION, len(pages), PAGE, PAGE))
    max_code = max(r[0] for r in records)
    num_idx = max_code + 1
    indexes = [-1] * num_idx
    idx_pos = buf.tell()
    buf.write(struct.pack("<i", num_idx))
    buf.write(b"\x00" * (num_idx * 4))          # 占位，稍后回填
    buf.write(struct.pack("<i", len(records)))
    for gi, (code, w, h, xskip, top, page, px, py) in enumerate(records):
        indexes[code] = gi
        if page >= 0:
            s, t = px / PAGE, py / PAGE
            s2, t2 = (px + w * SS) / PAGE, (py + h * SS) / PAGE  # UV 覆盖 2x 区域
            shader = f"{page + 1}_{size}.tga"
        else:
            s = t = s2 = t2 = 0.0
            shader = f"1_{size}.tga"            # 空白字形：任意有效页
        buf.write(struct.pack("<9f", w, h, xskip, w, top, s, t, s2, t2))
        buf.write(shader.encode("ascii").ljust(32, b"\x00"))
    data = bytearray(buf.getvalue())
    struct.pack_into(f"<{num_idx}i", data, idx_pos + 4, *indexes)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for stale in OUT_DIR.glob(f"{fam}_*_{size}.tga"):  # 页数可能变少，清旧页
        stale.unlink()
    (OUT_DIR / f"{fam}_{size}.fontdat").write_bytes(data)
    tgas = [f"{fam}_{size}.tga"]
    if use_original_base:
        # 拷原版基础段 tga（pak001 里）—— 数字/字母保持原版视觉
        with zipfile.ZipFile(Q4BASE / "pak001.pk4") as zf:
            (OUT_DIR / tgas[0]).write_bytes(zf.read(f"fonts/english/{fam}_{size}.tga"))
    else:
        write_tga(base_img, OUT_DIR / tgas[0])          # 基础段单页（自渲染）
    for i, page in enumerate(pages):
        tgas.append(f"{fam}_{i + 1}_{size}.tga")
        write_tga(page, OUT_DIR / tgas[-1])

    tops = [r[4] for r in records if r[5] >= 0]
    print(f"{fam}_{size}: 宽表 {len(records)} 字形 {len(pages)} 页  "
          f"top max={max(tops)} base top max={max(base_tops):.0f}")
    return tgas


def passthrough_original(fam, size, chars):
    """直通原版外星字体：base 段原样拷贝，附加合成宽表——全量中文字符稳定
    伪随机映射到原版可见字母/数字符号（同一字每次同一符号，避免闪烁），
    shaderName 指回 base 单页贴图。中文文本经此字体渲染即显示为外星符号。"""
    zf = zipfile.ZipFile(Q4BASE / "pak001.pk4")
    dat = zf.read(f"fonts/english/{fam}_{size}.fontdat")
    tga = zf.read(f"fonts/english/{fam}_{size}.tga")
    zf.close()
    assert len(dat) == 256 * 36 + 20, f"原版 fontdat 尺寸异常 {fam}_{size}"

    # 候选符号 = 原版 a-z/A-Z/0-9 中有位图的字形记录
    pool = []
    for i in (*range(97, 123), *range(65, 91), *range(48, 58)):
        rec = struct.unpack_from("<9f", dat, i * 36)
        if rec[0] > 0 and rec[1] > 0:
            pool.append(rec)
    assert pool, "原版字体无可用符号字形"

    buf = io.BytesIO()
    buf.write(dat)                                   # base 256×9f + 5f 原样
    buf.write(struct.pack("<IIiii", MAGIC, VERSION, 1, 0, 0))
    codes = sorted(ord(c) for c in chars)
    num_idx = codes[-1] + 1
    buf.write(struct.pack("<i", num_idx))
    indexes = [-1] * num_idx
    for gi, cp in enumerate(codes):
        indexes[cp] = gi
    buf.write(struct.pack(f"<{num_idx}i", *indexes))
    buf.write(struct.pack("<i", len(codes)))
    shader = f"{size}.tga".encode("ascii").ljust(32, b"\x00")
    for cp in codes:
        rec = pool[(cp * 2654435761) % len(pool)]    # Knuth 乘散列，稳定映射
        buf.write(struct.pack("<9f", *rec))
        buf.write(shader)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for stale in OUT_DIR.glob(f"{fam}_*_{size}.tga"):
        stale.unlink()
    (OUT_DIR / f"{fam}_{size}.fontdat").write_bytes(buf.getvalue())
    (OUT_DIR / f"{fam}_{size}.tga").write_bytes(tga)  # 原版贴图原样
    print(f"{fam}_{size}: 直通原版 + CJK 符号宽表 {len(codes)} 映射（{len(pool)} 个符号池）")
    return [f"{fam}_{size}.tga"]


def alias_family(fam, cfam, size, canon_tgas, mtr_out):
    """同源家族不重复渲染：fontdat 复制本尊（宽表 shaderName 只存后缀，
    字节全同），旧贴图删除，材质别名 decl 把引擎拼出的材质名 map 到本尊贴图"""
    (OUT_DIR / f"{fam}_{size}.fontdat").write_bytes(
        (OUT_DIR / f"{cfam}_{size}.fontdat").read_bytes())
    for stale in OUT_DIR.glob(f"{fam}_{size}.tga"):
        stale.unlink()
    for stale in OUT_DIR.glob(f"{fam}_*_{size}.tga"):
        stale.unlink()
    for tga in canon_tgas:
        mtr_out.append(font_decl(f"{fam}{tga[len(cfam):]}", tga))



def font_decl(name_tga, map_tga):
    """字体页显式材质：模板同引擎隐式生成，外加两个 stage 关键字——
    nopicmip（allowPicmip 即 GetDownsize 的 allowDownSize，挡 image_downSize
    把 2048 字体页压到 256：菜单文字糊团，2026-07-17 用户实机反馈+复现确认）
    + forceHighQuality（TD_HIGH_QUALITY，挡纹理压缩的 alpha 伪影）。
    注意 image_forceDownSize 1 可无视 nopicmip，启动器已补 +set 0。"""
    return (f"fonts/chinese/{name_tga}\n"
            "{\n\t{\n\t\tblend blend\n\t\tcolored\n"
            f"\t\tmap \"fonts/chinese/{map_tga}\"\n\t\tclamp\n"
            "\t\tnopicmip\n\t\tforceHighQuality\n\t}\n}\n")


def main():
    # 可选参数 --ui-ttf <路径> [--ui-index N]：覆盖四套 UI 家族的字体
    # （字体 A/B 实验用；Strogg 两套装饰体不受影响）
    if "--ui-ttf" in sys.argv:
        ttf = sys.argv[sys.argv.index("--ui-ttf") + 1]
        idx = int(sys.argv[sys.argv.index("--ui-index") + 1]) if "--ui-index" in sys.argv else 0
        for fam in ("chain", "marine", "lowpixel", "profont"):
            FAMILIES[fam] = (ttf, idx)
        print(f"UI 家族字体覆盖: {ttf} (index={idx})")
    extract_english()
    full, ui = build_charsets()
    print(f"全量字符集 {len(full)}，UI 字符集 {len(ui)}")
    canon = {}          # (ttf,idx) -> 本尊家族（首个出现者）
    written = {}        # (本尊家族, size) -> 贴图名列表
    mtr = ["// 自动生成（export_font.py）：同源字体家族共享贴图的材质别名\n"
           "// 引擎按 fontName 拼材质名（fonts/chinese/<家族>_<页>.tga），\n"
           "// 显式 decl 优先于隐式生成，map 指向本尊家族贴图 → 显存/磁盘只留一份\n\n"]
    for fam, key in FAMILIES.items():
        if key == ORIGINAL:
            for size in SIZES:
                for tga in passthrough_original(fam, size, full):  # 全档全量：装饰窗任意字号
                    mtr.append(font_decl(tga, tga))
            continue
        # chain/r_strogg/marine 独立 canonical：三者的 ASCII/数字基础段分别
        # 使用原版字形，CJK 宽字表仍按思源黑体生成，不能与其它家族整份
        # fontdat 互拷。marine 必须独立，否则会作为 (UI_TTF,0) 本尊把原版
        # 基础段传染给 lowpixel/profont（字幕 lowpixel 要保持思源自渲染）。
        canon_key = (f"{fam}_solo",) \
            if fam in ("chain", "r_strogg", "marine") else key
        cfam = canon.setdefault(canon_key, fam)
        for size in SIZES:
            if fam == cfam:
                written[(cfam, size)] = export(fam, size, ui if size == 48 else full)
                for tga in written[(cfam, size)]:
                    mtr.append(font_decl(tga, tga))
            else:
                alias_family(fam, cfam, size, written[(cfam, size)], mtr)
        if fam != cfam:
            print(f"{fam}: 同源 {cfam}，复用其贴图（fontdat 复制 + 材质别名）")
    MTR_PATH.parent.mkdir(parents=True, exist_ok=True)
    MTR_PATH.write_text("".join(mtr), encoding="utf-8")
    print(f"材质别名 {MTR_PATH.name}: {sum(s.count('map ') for s in mtr)} 条")


if __name__ == "__main__":
    main()
