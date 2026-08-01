# -*- coding: utf-8 -*-
"""微调 marine 字体里数字(0-9)字形的位置，修正武器 viewmodel 弹药计数偏移。

背景：marine 恢复原版基础段后，枪身弹药数字(方正粗体)位置与原思源不同——
偏上且偏左。实测 weapon ammo GUI 的 rect 改动不生效，但 fontdat 里数字字形的
top/xSkip 是 PaintChar 直接读取的，改它就能移动数字(2026-08-01 实证)。

每次都基于 pak 原版数字度量 + V/H 重新计算，避免多次运行累积偏移。
需先跑 export_font.py 生成含 CJK 宽表的 marine fontdat，再跑本脚本叠加数字偏移。
"""
import struct
import zipfile
from pathlib import Path

V = -4.0   # top：与 export_font 集成值同步(下移)
H = -15.0  # xSkip 偏移(相对原版)：负=右移；-15 为实机标定的水平居中量

REPO = Path(__file__).resolve().parents[2]
Q4BASE = Path(r"D:\Quake 4\q4base")
TARGETS = [
    REPO / "savedata" / "q4base" / "fonts" / "chinese",
    Path(r"D:/Quake 4/Quake4-Chinese/savedata/q4base/fonts/chinese"),
]

z = zipfile.ZipFile(Q4BASE / "pak001.pk4")
for size in (12, 24, 48):
    eng = z.read(f"fonts/english/marine_{size}.fontdat")  # 原版基础段(无宽表)
    for base in TARGETS:
        p = base / f"marine_{size}.fontdat"
        if not p.exists():
            print(f"跳过(不存在): {p}")
            continue
        d = bytearray(p.read_bytes())  # savedata 版(含CJK宽表)
        for idx in range(48, 58):  # 数字 0-9
            off = idx * 36
            orig = struct.unpack_from("<9f", eng, off)  # pak 原版数字度量
            cur = list(struct.unpack_from("<9f", d, off))
            cur[4] = orig[4] + V   # top = 原版 + V
            cur[2] = orig[2] + H   # xSkip = 原版 + H
            struct.pack_into("<9f", d, off, *cur)
        p.write_bytes(d)
    print(f"marine_{size}: V={V:+g} H={H:+g} (基于pak原版)")

print(f"\n部署完成 (V={V} H={H})。重启游戏看效果。")
print("微调(改完重跑本脚本，不累积)：上移多→V更大；下移→V更负；左移→H更负；右移→H更大")
