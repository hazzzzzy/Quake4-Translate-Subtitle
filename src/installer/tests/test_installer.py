# -*- coding: utf-8 -*-

import tempfile
import unittest
import contextlib
import io
import struct
import zipfile
from pathlib import Path
from unittest import mock

import installer
from build_dist_extras import (
    FONTDAT_BASE_SIZE,
    FONTDAT_MAGIC,
    FONTDAT_VERSION,
    build_vo_alias_pk4,
    extract_strogg_fonts,
    parse_wide_fontdat,
    patch_health_station_strogg_gui,
    patch_readable_strogg_materials,
    patch_static4_gui,
    patch_sys_offline_gui,
    patch_warn_electrical_gui,
)


def make_original_fontdat(size):
    data = bytearray(FONTDAT_BASE_SIZE)
    record = struct.pack("<9f", 8, 10, 9, 8, 10, 0, 0, 0.5, 0.5)
    for code in (*range(97, 123), *range(65, 91), *range(48, 58)):
        data[code * 36:(code + 1) * 36] = record
    struct.pack_into("<5f", data, 256 * 36, size, 9, 10, -1, 0)
    return bytes(data)


def make_wide_fontdat(size, codes):
    output = io.BytesIO()
    output.write(make_original_fontdat(size))
    output.write(struct.pack(
        "<IIiii", FONTDAT_MAGIC, FONTDAT_VERSION, 1, 2048, 2048))
    num_indexes = max(codes) + 1
    indexes = [-1] * num_indexes
    for glyph_index, code in enumerate(codes):
        indexes[code] = glyph_index
    output.write(struct.pack("<i", num_indexes))
    output.write(struct.pack(f"<{num_indexes}i", *indexes))
    output.write(struct.pack("<i", len(codes)))
    for index, _code in enumerate(codes):
        output.write(struct.pack(
            "<9f", 12, 14, 13, 12, 12, 0, index / 100, 0.1, index / 100 + 0.02))
        output.write(f"1_{size}.tga".encode("ascii").ljust(32, b"\x00"))
    return output.getvalue()


class InstallerTests(unittest.TestCase):
    def test_frozen_application_directory_uses_bundled_payload(self):
        with tempfile.TemporaryDirectory() as temporary:
            bundle = Path(temporary)
            executable = bundle / "Quake4-Chinese-Installer.exe"
            with mock.patch.object(installer.sys, "frozen", True, create=True), \
                 mock.patch.object(installer.sys, "_MEIPASS", str(bundle), create=True), \
                 mock.patch.object(installer.sys, "executable", str(executable)):
                self.assertEqual(
                    installer.application_directory(),
                    bundle / "payload",
                )

    def test_strogg_fonts_are_extracted_from_complete_pak(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pak = root / "pak001.pk4"
            output = root / "fonts"
            expected = {
                f"{family}_{size}.{extension}"
                for family in ("strogg", "r_strogg")
                for size in (12, 24, 48)
                for extension in ("fontdat", "tga")
            }
            source_fontdats = {}
            output.mkdir()
            for size in (12, 24, 48):
                (output / f"marine_{size}.fontdat").write_bytes(
                    make_wide_fontdat(size, [0x4E00, 0x6C14]))
                (output / f"r_strogg_{size}.fontdat").write_bytes(
                    make_wide_fontdat(size, [0x4E00, 0x6C14]))
            with zipfile.ZipFile(pak, "w") as archive:
                for name in expected:
                    if name.endswith(".fontdat"):
                        size = int(name.removesuffix(".fontdat").rsplit("_", 1)[1])
                        data = make_original_fontdat(size)
                        source_fontdats[name] = data
                    else:
                        data = name.encode("ascii")
                    archive.writestr(f"fonts/english/{name}", data)

            extract_strogg_fonts(pak, output)

            self.assertEqual(
                {path.name for path in output.iterdir() if not path.name.startswith("marine_")},
                expected,
            )
            strogg = (output / "strogg_12.fontdat").read_bytes()
            self.assertTrue(strogg.startswith(source_fontdats["strogg_12.fontdat"]))
            _height, indexes, _glyphs, _offset = parse_wide_fontdat(strogg)
            self.assertGreaterEqual(indexes[0x4E00], 0)
            self.assertGreaterEqual(indexes[0xFFFD], 0)

            readable = (output / "r_strogg_12.fontdat").read_bytes()
            self.assertTrue(readable.startswith(source_fontdats["r_strogg_12.fontdat"]))
            _height, readable_indexes, _glyphs, glyph_offset = parse_wide_fontdat(
                readable)
            self.assertGreaterEqual(readable_indexes[0x6C14], 0)
            record = struct.unpack_from("<9f", readable, glyph_offset)
            self.assertEqual(record[1], 13)
            self.assertAlmostEqual(record[6], 2 / 2048)

    def test_strogg_font_extraction_rejects_missing_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pak = root / "pak021.pk4"
            with zipfile.ZipFile(pak, "w") as archive:
                archive.writestr("unrelated.txt", b"data")

            with self.assertRaisesRegex(RuntimeError, "缺少 Strogg 字体文件"):
                extract_strogg_fonts(pak, root / "fonts")

    def test_readable_strogg_base_material_uses_extracted_texture(self):
        with tempfile.TemporaryDirectory() as temporary:
            material = Path(temporary) / "fonts.mtr"
            blocks = []
            for size in (12, 24, 48):
                blocks.append(
                    f"fonts/chinese/r_strogg_{size}.tga\n{{\n\t{{\n"
                    f"\t\tblend blend\n\t\tcolored\n"
                    f'\t\tmap "fonts/chinese/marine_{size}.tga"\n\t}}\n}}\n'
                )
            material.write_text("".join(blocks), encoding="utf-8")

            patch_readable_strogg_materials(material)
            patch_readable_strogg_materials(material)

            text = material.read_text(encoding="utf-8")
            for size in (12, 24, 48):
                self.assertIn(
                    f'map "fonts/chinese/r_strogg_{size}.tga"', text)

    def test_noninteractive_panel_text_alignment(self):
        health = """windowDef r_text1
{
	rect	272,90,347,48
	text	\"#str_200960\"
}
windowDef r_text2
{
	rect	272,130,347,48
	text	\"#str_200961\"
}
windowDef r_text3
{
	rect	272,170,347,48
	text	\"#str_200871\"
}
"""
        patched_health = patch_health_station_strogg_gui(health)
        for y in (85, 125, 165):
            self.assertIn(f"rect\t272,{y},347,48", patched_health)

        system = """windowDef system_r
{
	rect	186,169,275,63
}
windowDef offline_r
{
	rect	121,223,403,87
	text	\"#str_200402\"
}
"""
        patched_system = patch_sys_offline_gui(system)
        self.assertIn("rect\t276,169,222,63", patched_system)

        static4 = """windowDef system_r
{
	rect	169,302,305,77
}
windowDef offline_r
{
	rect	78,347,489,102
	textscale	2
	text	\"#str_200402\"
}
"""
        patched_static4 = patch_static4_gui(static4)
        self.assertIn("rect\t276,302,247,77", patched_static4)

        electrical = """windowDef warning
{
	rect	104,329,431,73
	text	\"#str_200370\"
	textscale	1.6
}
windowDef highvoltage
{
	rect	58,341,515,54
	text	\"#str_200372\"
	textscale	1.2
}
"""
        patched_electrical = patch_warn_electrical_gui(electrical)
        self.assertEqual(patched_electrical.count('text\t"#str_390000"'), 2)
        self.assertEqual(
            patched_electrical.count("rect\t218,332,317,73"), 2)

    def test_voice_alias_uses_english_voice_paks_and_patch_precedence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            base = root / "zpak_english.pk4"
            patch = root / "zpak_english_02.pk4"
            output = root / "alias.pk4"
            with zipfile.ZipFile(base, "w") as archive:
                archive.writestr("sound/vo_english/a.ogg", b"base")
                archive.writestr("sound/vo_english/b.ogg", b"only-base")
            with zipfile.ZipFile(patch, "w") as archive:
                archive.writestr("sound/vo_english/a.ogg", b"patch")

            count = build_vo_alias_pk4([base, patch], output)

            self.assertEqual(count, 2)
            with zipfile.ZipFile(output) as archive:
                self.assertEqual(archive.read("sound/vo_chinese/a.ogg"), b"patch")
                self.assertEqual(archive.read("sound/vo_chinese/b.ogg"), b"only-base")

    def test_callback_writer_allows_print_callback(self):
        captured = io.StringIO()
        writer = installer.CallbackWriter(print)
        writer.callback_stdout = captured
        writer.callback_stderr = captured
        with contextlib.redirect_stdout(writer):
            print("进度")
        self.assertEqual(captured.getvalue(), "进度\n")

    def test_save_backup_keeps_sources_and_archives_all_slot_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "savegames"
            backups = root / "backups"
            source.mkdir()
            expected = {
                "slot.save": b"save-data",
                "slot.txt": "存档说明".encode("utf-8"),
                "slot.tga": b"image-data",
            }
            for name, data in expected.items():
                (source / name).write_bytes(data)

            target = installer.backup_savegames(source, backups, "chinese")

            self.assertTrue(target.is_file())
            with zipfile.ZipFile(target) as archive:
                self.assertEqual(set(archive.namelist()), set(expected))
                for name, data in expected.items():
                    self.assertEqual(archive.read(name), data)
            for name, data in expected.items():
                self.assertEqual((source / name).read_bytes(), data)

    def test_validate_game_directory_requires_all_paks(self):
        with tempfile.TemporaryDirectory() as temporary:
            game = Path(temporary)
            (game / "q4base").mkdir()
            (game / "q4base" / "pak001.pk4").touch()
            with self.assertRaises(installer.InstallError):
                installer.validate_game_directory(game)

    def test_validate_payload_english_mode_requires_subtitle_assets(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            payload = root / "payload"
            launcher = root / "launcher.exe"
            (payload / "engine").mkdir(parents=True)
            (payload / "engine" / "Quake4.exe").touch()
            (payload / "engine" / "q4game.dll").touch()
            launcher.touch()
            # 中文载荷齐全但缺英文字幕资产 -> 英文模式校验必须失败
            strings = payload / "savedata" / "q4base" / "strings"
            strings.mkdir(parents=True)
            (strings / "chinese_guis.lang").touch()

            installer.validate_payload(payload, launcher)
            with self.assertRaises(installer.InstallError):
                installer.validate_payload(payload, launcher, mode="english")

            (payload / "savedata" / "q4base" / "guis").mkdir(parents=True)
            (payload / "savedata" / "q4base" / "guis" / "subtitles.gui").touch()
            (strings / "english_lipsadd.lang").touch()
            with self.assertRaisesRegex(installer.InstallError, "lipsync"):
                installer.validate_payload(payload, launcher, mode="english")

            lipsync = payload / "savedata" / "q4base" / "lipsync"
            lipsync.mkdir(parents=True)
            (lipsync / "zz_chinese_radio.lipsync").touch()
            installer.validate_payload(payload, launcher, mode="english")

    def test_install_english_mode_deploys_subtitle_subset_without_generation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            game = root / "Quake 4"
            payload = root / "payload"
            launcher = root / "launcher.exe"
            (game / "q4base").mkdir(parents=True)
            (game / "Quake4.exe").touch()
            for name in installer.REQUIRED_PAKS:
                (game / "q4base" / name).touch()
            (payload / "engine").mkdir(parents=True)
            (payload / "engine" / "Quake4.exe").touch()
            (payload / "engine" / "q4game.dll").touch()
            savedata = payload / "savedata" / "q4base"
            (savedata / "strings").mkdir(parents=True)
            (savedata / "strings" / "chinese_guis.lang").touch()
            (savedata / "strings" / "english_lipsadd.lang").touch()
            (savedata / "guis").mkdir(parents=True)
            (savedata / "guis" / "subtitles.gui").touch()
            (savedata / "lipsync").mkdir(parents=True)
            (savedata / "lipsync" / "zz_chinese_radio.lipsync").touch()
            (savedata / "lipsync" / "zz_chinese_aivo.lipsync").touch()
            # 中文专属资产：英文模式绝不能部署
            (savedata / "fonts" / "chinese").mkdir(parents=True)
            (savedata / "fonts" / "chinese" / "marine_48.fontdat").touch()
            launcher.write_bytes(b"launcher")

            with mock.patch.object(installer, "application_directory", return_value=payload), \
                 mock.patch.object(installer, "bundled_launcher", return_value=launcher), \
                 mock.patch.object(installer, "build_assets", return_value=0) as build, \
                 mock.patch.object(installer, "grant_install_access"), \
                 mock.patch.object(installer, "apply_game_icon"):
                target = installer.install_localization(
                    game,
                    False,
                    lambda _line: None,
                    mode="english",
                )

            resolved_game = game.resolve()
            install_root = resolved_game / installer.INSTALL_DIRECTORY_NAME
            english_root = install_root / installer.ENGLISH_SAVEDATA_DIRECTORY_NAME
            self.assertEqual(
                target, resolved_game / installer.LAUNCHER_NAME_ENGLISH)
            build.assert_not_called()
            self.assertTrue((install_root / "engine" / "Quake4.exe").is_file())
            self.assertTrue(
                (english_root / "q4base" / "guis" / "subtitles.gui").is_file())
            self.assertTrue(
                (english_root / "q4base" / "strings" / "english_lipsadd.lang").is_file())
            self.assertTrue(
                (english_root / "q4base" / "lipsync" / "zz_chinese_radio.lipsync").is_file())
            self.assertTrue(
                (english_root / "q4base" / "lipsync" / "zz_chinese_aivo.lipsync").is_file())
            # 英文模式不得部署中文资产，也不得动中文模式的 savedata
            self.assertFalse((english_root / "q4base" / "fonts").exists())
            self.assertFalse(
                (english_root / "q4base" / "strings" / "chinese_guis.lang").exists())
            self.assertFalse((install_root / "savedata").exists())

    def test_install_uses_separate_localization_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            game = root / "Quake 4"
            payload = root / "payload"
            launcher = root / installer.LAUNCHER_NAME
            (game / "q4base").mkdir(parents=True)
            (game / "Quake4.exe").touch()
            for name in installer.REQUIRED_PAKS:
                (game / "q4base" / name).touch()
            (payload / "engine").mkdir(parents=True)
            (payload / "engine" / "Quake4.exe").touch()
            (payload / "engine" / "q4game.dll").touch()
            strings = payload / "savedata" / "q4base" / "strings"
            strings.mkdir(parents=True)
            (strings / "chinese_guis.lang").touch()
            launcher.write_bytes(b"launcher")

            progress_events = []
            with mock.patch.object(installer, "application_directory", return_value=payload), \
                 mock.patch.object(installer, "bundled_launcher", return_value=launcher), \
                 mock.patch.object(installer, "build_assets", return_value=0) as build, \
                 mock.patch.object(installer, "grant_install_access") as grant_access, \
                 mock.patch.object(installer, "apply_game_icon") as apply_icon:
                target = installer.install_localization(
                    game,
                    False,
                    lambda _line: None,
                    lambda value, message: progress_events.append((value, message)),
                )

            install_root = game / installer.INSTALL_DIRECTORY_NAME
            resolved_game = game.resolve()
            install_root = resolved_game / installer.INSTALL_DIRECTORY_NAME
            self.assertEqual(target, resolved_game / installer.LAUNCHER_NAME)
            self.assertTrue((install_root / "engine" / "Quake4.exe").is_file())
            self.assertTrue((install_root / "savedata" / "q4base" / "strings" / "chinese_guis.lang").is_file())
            self.assertFalse((game / "q4base" / "strings").exists())
            self.assertFalse(any(
                path.name.startswith(".Quake4-Chinese-install-")
                for path in resolved_game.iterdir()
            ))
            build.assert_called_once()
            self.assertEqual(build.call_args.args[0], resolved_game)
            self.assertEqual(
                build.call_args.args[1].relative_to(resolved_game).parts[-2:],
                ("savedata", "q4base"),
            )
            self.assertIn("progress", build.call_args.kwargs)
            grant_access.assert_called_once_with(install_root)
            apply_icon.assert_called_once_with(
                resolved_game / "Quake4.exe",
                resolved_game / installer.LAUNCHER_NAME,
            )
            values = [value for value, _message in progress_events]
            self.assertEqual(values[-1], 100)
            self.assertEqual(values, sorted(values))


if __name__ == "__main__":
    unittest.main()
