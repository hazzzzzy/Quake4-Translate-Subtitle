[Simplified Chinese](README.md) | English

# Quake 4 Simplified Chinese Localization

A complete Simplified Chinese localization for Quake 4 (2005), including translated menus, UI, objectives, dialogue, radio messages, PA announcements, and a new real-time subtitle system for speech that the original game does not subtitle.

The project runs legitimate Quake 4 1.4.2 game data through the open-source [idTech4A++](https://github.com/glKarin/com.n0n3m4.diii4a) engine. It keeps the original executable and `q4base` data unchanged.

The installer offers two mutually exclusive modes: the **full Simplified Chinese localization** (menus + subtitles in Chinese), or **English original + English subtitles** — the game keeps its stock English UI, HUD, panels, and fonts, and only gains the real-time subtitle system the original game never had.

## Features

- 2,272 UI entries and 3,962 dialogue entries translated into Simplified Chinese
- 251 radio/PA subtitle entries and 668 supplemental AI speech declarations
- Real-time subtitles hooked into AI speech, radio chatter, and sound playback
- Distance and PVS audibility filtering, with more tolerant handling for friendly NPCs
- Custom CJK font exporter with true glyph advances, 2x supersampling, widescreen compensation, and texture sharing
- Original Strogg glyphs before the player transformation and readable Chinese panels afterward
- GUI changes constrained to existing structures for savegame compatibility
- Graphical installer with measured progress, optional desktop shortcut, and separate save management

## Requirements

- Windows 10 or Windows 11, 64-bit
- A legitimate Quake 4 installation updated to version 1.4.2
- `pak021.pk4` and `pak022.pk4` in the original `q4base` directory
- A 16:9 display is recommended for the supplied font metrics

The graphical installer is self-contained and does not require a separate Python installation. Python 3.9 or newer is only needed for the maintainer-oriented portable `postinstall.cmd` workflow.

## Installation

1. Download the latest `Quake4-Chinese-Installer-vX.Y.Z.exe` from [Releases](https://github.com/hazzzzzy/Quake4-Translate-Subtitle/releases). It is a standalone installer containing the public engine and localization payload, so the portable ZIP is not required.
2. Run the downloaded installer.
3. Confirm the detected Quake 4 directory or select it manually.
4. Pick the install mode: full Chinese localization (default) or English original + English subtitles.
5. Optionally enable the desktop shortcut, then start the installation.
6. Launch the game with `Quake4中文启动器.exe` (Chinese mode) or `Quake4英文字幕启动器.exe` (English-subtitles mode) in the original game directory, or through the desktop shortcut.

In Chinese mode, the installer derives several runtime assets from the player's own game files (1-3 minutes):

- Original Strogg font data
- HUD layout patches
- Post-transformation translation animation and panel layouts
- An English-voice path alias package used by the Chinese language mode

These derived assets are not distributed by this repository. The English-subtitles mode is a purely static deployment — no runtime asset generation, done in seconds. Both modes can be installed side by side; each keeps its own save directory (`savedata` / `savedata-english`), isolated from the stock game's saves.

The versioned ZIP remains available as a complete portable package for maintainers and manual deployments.

## Installed Layout

| Path | Purpose |
|---|---|
| `Quake 4\Quake4.exe` | Original executable |
| `Quake 4\Quake4中文启动器.exe` | Localization launcher |
| `Quake 4\q4base` | Original game data |
| `Quake 4\Quake4-Chinese\engine` | idTech4A++ and `q4game.dll` |
| `Quake 4\Quake4-Chinese\savedata` | Localization assets and saves |

The localized launcher uses `Quake4-Chinese\savedata` as `fs_savepath`. Original and localized savegames therefore coexist without overwriting each other.

The installer's save manager can inspect both save directories and create independent ZIP backups under `Quake4-Chinese\save-backups`.

## Console Variables

Open the console with `~`.

| Variable | Description |
|---|---|
| `harm_g_subtitles 0` | Disable subtitles |
| `harm_g_subtitleHoldTime 3.0` | Change subtitle hold time |
| `harm_g_subtitleMinTime 1.0` | Change the minimum display time for short lines |
| `harm_g_subtitlePVSCheck 0` | Disable PVS occlusion filtering |
| `harm_g_subtitleDebug 1` | Log subtitle decisions with the `[SUB]` prefix |
| `harm_r_softStencilShadow 0` | Disable soft stencil shadows |

## Troubleshooting

| Problem | Resolution |
|---|---|
| `pak021.pk4` is missing | Update the original game to version 1.4.2 |
| Strogg terminals show question marks | Run the graphical installer again |
| A spoken line has no subtitle | Attach `Quake4-Chinese\savedata\q4base\qconsole.log` to an issue |
| The game crashes | Attach the same `qconsole.log` file and describe the loaded level/save |
| HUD numbers are clipped | Remove stale custom font/GUI overrides and reinstall the localization |

## Building from Source

Install the Python dependencies into a project virtual environment:

```powershell
python -m venv venv
& .\venv\Scripts\python.exe -m pip install -r requirements.txt
```

Build the Windows installer:

```powershell
& .\src\installer\build.ps1 -Configuration Release
```

Create the same standalone installer, portable archive, and checksum assets used by GitHub Actions:

```powershell
& .\src\tools\package_release.ps1 -Version dev
```

To rebuild `q4game.dll`, check out idTech4A++ tag `v1.1.0harmattan70`, apply `src/engine-patches/0001-quake4-cn-runtime.patch`, copy `Subtitles.h/.cpp` into the Quake 4 game source directory, and build with:

```text
-DCORE=OFF -DBASE=OFF -DRAVEN=OFF -DQUAKE4=ON
```

See [src/engine-patches/README.md](src/engine-patches/README.md) for the full procedure.

## Automated Releases

- Pushes to `main` run validation and upload the standalone EXE, portable ZIP, and checksums as workflow artifacts.
- Tags matching `v*` run the same validation and publish a GitHub Release.
- Release assets include the versioned standalone installer, portable ZIP, and `SHA256SUMS.txt`.

## Licensing

| Component | License |
|---|---|
| Engine patches, subtitle code, tools, GUI files, and declarations | GPL-3.0 |
| Translation text | CC BY-NC-SA 4.0 |
| CJK font bitmaps derived from Source Han Sans | SIL Open Font License 1.1 |
| Runtime assets generated from the player's game data | Owned under the player's original game license; not distributed here |

Quake 4 is a trademark of id Software and Raven Software. This is a non-commercial fan project and is not affiliated with id Software, Raven Software, Bethesda, or ZeniMax.

## References

- [Localization workflow](docs/localization-guide.md)
- [Terminology glossary](docs/glossary.md)
- [English subtitles plan](docs/english-subtitles-plan.md)
- [idTech4A++ upstream](https://github.com/glKarin/com.n0n3m4.diii4a)
