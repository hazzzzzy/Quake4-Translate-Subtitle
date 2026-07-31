# -*- coding: utf-8 -*-
"""从翻译主表生成 chinese_*.lang 并部署到引擎 savedata。

来源：translations/ui_code.tsv, ui_guis.tsv, ui_maps.tsv, ui_mappack.tsv,
      dialogue_lips.tsv；radio_chatter.tsv（无线电台词，并入 chinese_lips.lang，
      str_380000 起为自建 id，与自建 lipsync decl 配套，见 gen_radio_decls.py）
规则：zh 非空（status=done/review）用 zh，否则回退英文原文；
      输出 UTF-8 with BOM（引擎硬性要求）。
"""
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
TRANS = REPOSITORY / "src" / "translations"
OUT = REPOSITORY / "savedata" / "q4base" / "strings"
OUT.mkdir(parents=True, exist_ok=True)

TABLES = {
    "ui_code.tsv": "chinese_code.lang",
    "ui_guis.tsv": "chinese_guis.lang",
    "ui_maps.tsv": "chinese_maps.lang",
    "ui_mappack.tsv": "chinese_mappack.lang",
    "dialogue_lips.tsv": "chinese_lips.lang",
}

total_zh = total = 0
for tsv, lang in TABLES.items():
    lines = (TRANS / tsv).read_text(encoding="utf-8-sig").splitlines()
    out = ["// string table", "// chinese", "//", "", "{"]
    n_zh = n = 0
    for l in lines[1:]:
        cols = l.split("\t")
        if len(cols) < 5:
            continue
        sid, en, zh = cols[0], cols[1].replace("\\t", "\t"), cols[2]
        text = zh if zh.strip() else en
        if zh.strip():
            n_zh += 1
        n += 1
        out.append(f'\t"{sid}"\t"{text}"')
    # 无线电台词与 AI 对话缺口台词并入 lips
    # （列: str_id/sound/map/english/chinese/source，id 无 # 前缀）
    if tsv == "dialogue_lips.tsv":
        for extra in ("radio_chatter.tsv", "ai_vo_gap.tsv", "broadcast_pa.tsv", "speaker_chatter.tsv"):
            path = TRANS / extra
            if not path.exists():
                continue
            for l in path.read_text(encoding="utf-8-sig").splitlines()[1:]:
                cols = l.split("\t")
                if len(cols) < 5 or not cols[0].startswith("str_"):
                    continue
                sid, en, zh = "#" + cols[0], cols[3], cols[4]
                text = zh if zh.strip() else en
                if zh.strip():
                    n_zh += 1
                n += 1
                out.append(f'\t"{sid}"\t"{text}"')
    out.append("}")
    p = OUT / lang
    p.write_text("\n".join(out) + "\n", encoding="utf-8-sig")
    print(f"{lang}: {n} 条（中文 {n_zh}，回退英文 {n - n_zh}）")
    total += n
    total_zh += n_zh
print(f"合计 {total} 条，已汉化 {total_zh}（{total_zh / total:.0%}）")

# —— 英文字幕模式：english_lipsadd.lang ——
# 只补自建 id（radio str_380xxx / ai_vo str_385xxx）：主线对白 3962 条
# 原版 zpak_english.pk4 的 english_lips.lang 已全覆盖，无需重复生成。
# 文件名必须与原版不同名：savepath 的 strings/english_lips.lang 会整体
# 遮蔽 pak 内同名文件（丢原版 6085 条），independent 名按语言前缀合并加载。
en_out = ["// string table", "// english (subtitle additions for custom decls)", "//", "", "{"]
n_en = 0
for extra in ("radio_chatter.tsv", "ai_vo_gap.tsv", "broadcast_pa.tsv", "speaker_chatter.tsv"):
    path = TRANS / extra
    if not path.exists():
        continue
    for l in path.read_text(encoding="utf-8-sig").splitlines()[1:]:
        cols = l.split("\t")
        if len(cols) < 5 or not cols[0].startswith("str_"):
            continue
        en_out.append(f'\t"#{cols[0]}"\t"{cols[3]}"')
        n_en += 1
en_out.append("}")
(OUT / "english_lipsadd.lang").write_text("\n".join(en_out) + "\n", encoding="utf-8-sig")
print(f"english_lipsadd.lang: {n_en} 条（英文字幕模式自建 id 补充）")
