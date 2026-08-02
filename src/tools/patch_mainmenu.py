# -*- coding: utf-8 -*-
"""生成 mainmenu.gui 中文适配覆盖版（松散写入 savedata\\q4base\\guis\\mainmenu.gui）。

补丁逻辑的单一真相源是 build_dist_extras.patch_mainmenu_gui（三按钮 rect、
credits 段职位汉化、分辨率/比例选择器 idTech4A++ 适配）。安装器 postinstall
也调用同一函数现场从正版 pak 生成 mainmenu.gui。本脚本仅供开发时单独重新
生成 savedata 的 mainmenu.gui 之用，保持与分发链路一致。
"""
import sys
import zipfile
from pathlib import Path

SRC_PAK = Path(r"D:\Quake 4\q4base\pak021.pk4")
DST = Path(r"D:\PROJECT\quake4-translate-subtitle\savedata\q4base\guis\mainmenu.gui")


def main() -> int:
    sys.path.insert(0, str(Path(__file__).parent))
    from build_dist_extras import patch_mainmenu_gui
    with zipfile.ZipFile(SRC_PAK) as zf:
        data = zf.read("guis/mainmenu.gui")
    data = patch_mainmenu_gui(data)
    DST.parent.mkdir(parents=True, exist_ok=True)
    DST.write_bytes(data)
    print(f"写入 {DST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
