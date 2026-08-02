# Quake 4 简体中文汉化工程说明

## 项目定位

本工程为 Quake 4（2005，Raven Software）的简体中文汉化与字幕开发环境。运行时使用开源引擎 idTech4A++ 加载玩家合法持有的 Quake 4 1.4.2 游戏数据，不修改原版游戏目录，并保留官方 `q4game.dll`备份。

主要功能包括：

- UI、菜单、任务文本和剧情对白的简体中文翻译。
- 自研语音字幕系统，覆盖普通对白、无线电、PA 广播和补齐的 AI 语音。
- 基于距离、PVS 和友军容差的字幕可听性门控。
- 自研 CJK 字体导出，包含 2 倍超采样、16:9 横向预压缩、垂直对中和材质别名压缩。
- Strogg 外星文字体，以及改造后转译为可读中文的动画与字体切换。
- 基于 pak021 GUI 底稿的 HUD 和交互面板汉化。
- 规划中的独立英文字幕模式只增加字幕，保留原版英文界面与字体。

## 运行拓扑

| 用途 | 路径 | 说明 |
|---|---|---|
| 原版游戏数据 | `D:\Quake 4\q4base` | `fs_basepath`，必须包含 `pak001.pk4`和 1.4.2 的 `pak021.pk4` |
| 工程引擎 | `idTech4Apx\quake4` | idTech4A++ 的 `Quake4.exe`及当前编译的 `q4game.dll` |
| 工程运行数据 | `savedata\q4base` | `fs_savepath`，部署字体、字符串、GUI、lipsync、语音别名、配置、日志和存档 |
| 已知可玩基线 | `D:\Quake4-CN` | 外部对照目录；未经用户明确许可不要覆盖或同步修改 |
| 测试启动 | exe 安装版 `Quake4中文启动器.exe`（Q4CNLauncher） | 安装后用快捷方式启动；安装器安装时从原版 Quake4.exe 提取图标。便携 ZIP 已停发 |

测试统一用 exe 安装版（安装到游戏目录后点 Quake4中文启动器.exe），不再用工程 .cmd 启动器。引擎中文、宽字符 GUI、高清字体、字幕、阴影等选项由启动器/安装器配置。

## 目录职责

### 工程根

工程根就是公开 Git 仓库，远端目标名称为 `Quake4-Translate-Subtitle`。主要保存可开源内容：

- `src/translations`：翻译主表，是中文字符串的源数据。
- `src/tools`：lang、字体、HUD、主菜单、腕表、无线电 decl 和分发资产生成工具。
- `src/engine-patches/Subtitles.h/.cpp`：字幕系统源码。
- `src/engine-patches/0001-quake4-cn-runtime.patch`：基于固定上游标签的完整 8 文件引擎补丁。
- `dist`：公开可分发内容，不等同于本工程当前部署快照。
- `.github/workflows/package.yml`：push 验证与打包、tag Release 发布流程。

修改前后都要在工程根执行 `git status --short`，不要覆盖用户或前序会话的未提交改动。

### `diii4a`

idTech4A++ 上游源码，基线为 `v1.1.0harmattan70`。当前 Quake 4 汉化改动位于：

- `Q3E/src/main/jni/doom3/neo/quake4`：字幕挂钩、玩家保存提示修复和 `Subtitles.cpp/.h`。
- `Q3E/src/main/jni/doom3/neo/CMakeLists.txt`：将字幕实现加入 q4game 构建。

该目录是独立的上游 Git 工作副本，不纳入根仓库。当前权威补丁是 `src/engine-patches/0001-quake4-cn-runtime.patch`，包含 8 个受跟踪文件，并另外复制 `Subtitles.h/.cpp`。`tmp/scripts/quake4-cn-engine-full.patch`只保留为本机交接副本。

### `assets`

保存不能从公开仓库直接生成或需要固定底稿的开发输入：

- `SourceHanSansSC-Medium.otf`：CJK 字体源。
- `hud_pak021_stock.gui`：Quake 4 1.4.2 HUD 底稿。
- `english_fonts`：原版英文字体缓存。

### `savedata/q4base`

当前工程运行时部署目录。主要内容：

- `fonts/chinese`：当前启用的中文字体和 fontdat。
- `strings`：5 个中文 lang 文件。
- `guis`：HUD、字幕、主菜单、腕表、Strogg 面板和转译动画。
- `lipsync`：无线电及 AI 补齐 decl。
- `materials`：字体材质别名。
- `zzz_vo_chinese_alias.pk4`：中文语音路径别名。
- `savegames`、`screenshots`、`qconsole.log`：运行时数据，不是翻译源文件。

`fonts/chinese_bak_r4`及 `poc_*.cfg`为历史备份或测试资产，不应进入正式分发包。

### `tmp`

构建、验证和临时产物目录：

- `scripts/quake4-cn-engine-full.patch`：完整引擎补丁的本机交接副本；公开权威文件位于 `src/engine-patches`。
- `build-q4-ninja-only`：当前 q4game 增量构建目录。
- `windows-sdk-nuget`：本地 Windows SDK 10.0.26100，不是系统级安装。
- 其余截图、隔离存档和生成目录均为测试证据；删除前必须征得用户确认。

### `docs`

按迭代记录的技术沉淀。先读 `docs/MEMORY.md`索引，再按问题读取对应文档。关键主题：

- `quake4-feedback-fixes-r4.md`：GUI 存档结构、pak021 底稿和旧存档状态覆盖。
- `quake4-r6-crash-and-subtitles.md`：换图崩溃、字幕 GUI 指针生命周期及后续版本记录。
- `quake4-font-aspect-and-size.md`：字体比例与体积优化。
- `quake4-strogg-changeover.md`：Strogg 转译动画与字体语义。
- `quake4-dist-package.md`：分发包结构与打包要求。

## GUI 与存档的绝对约束

Quake 4 会按 GUI 源文件结构和窗口顺序序列化状态。必须遵守：

1. HUD 覆盖必须以 `assets/hud_pak021_stock.gui`为底稿。
2. 为兼容存档，原则上只改既有窗口的数值属性；禁止随意增删 `windowDef`、脚本、变量或改变顺序。
3. 旧存档会恢复保存时的 `rect`、`textscale`、文本和其他 GUI 状态，从而暂时覆盖磁盘上的新配置。
4. 视觉验收应从主菜单进入新流程、换图，或在明确的调试场景执行 `reloadGuis all`；不能用旧 `gamestart`判断当前 HUD 文件是否正确。

## GUI 加载机制与字体共用约束

### 两类 GUI 的加载路径（2026-08-01 摸清）

- **走 savepath 的 GUI**（loose 覆盖生效）：HUD（hud.gui/hud_strogg.gui）、主菜单、腕表、字幕、Strogg 面板、电梯/撤离/生命补给等。由 `build_dist_extras.py` 从原版 pak 现场生成到 `savedata/q4base/guis/`，loose 文件覆盖 pak 原版。
- **不走 savepath 的 GUI**（只认 basepath pak，loose 文件和 savepath 内 pk4 都不覆盖）：武器 viewmodel 弹药 GUI（`machinegun_ammo`/`hyperblaster_ammo`/`shotgun_ammo`/`nailgun_ammo`/`rocketlauncher_ammo.gui`）和准心 GUI（`cursor.gui`）。由武器 def / 引擎代码从 basepath pak 直接加载，不搜 `fs_savepath`。**改这些 GUI 的 rect/font/textscale 等任何属性都不会生效**（实测：ammo rect 大补偿 +28、cursor crossName font 改 lowpixel、cursor 打 zzz pk4，全部纹丝不动）。

### marine 字体被三处共用，字形无法分别

marine 基础段（ASCII/英文/数字）被以下三处共用，字形必须一致：

1. **枪身弹药数字**（武器 viewmodel ammo GUI，`font "fonts/marine"`）
2. **准心人名**（`cursor.gui` 的 `crossName` 控件 `gui::npc`，`font "fonts/marine"`）
3. **MCC 终端/医疗面板/简报/监控的数字编号**（各终端 GUI，`font "fonts/marine"`）

marine 恢复原版基础段后，这三处的英文/数字**同时变原版方正字形**，无法只让枪身是原版、准心是思源。要让准心英文名回思源只能 marine 整体回思源（枪身数字也回思源）。当前（2026-08-01）选择 marine 原版基础段：三者统一原版，并附数字位置补偿。

### 改 viewmodel/准心数字位置：改 fontdat，不要改 GUI rect

武器弹药数字和准心的位置由 fontdat 里数字字形的 `top`（垂直）和 `xSkip`（水平 center 基准）决定，`PaintChar` 直接读取这两个度量。GUI rect 改动对这些 viewmodel/准心 GUI 无效（不走 savepath），**改 fontdat 才有效**（2026-08-01 大补偿实证：fontdat 数字 top-10/xSkip-10 立刻右下移）。marine 数字位置补偿（`top-4`/`xSkip-15`，实机标定：垂直下移到不偏上、水平 center 右移到居中）集成在 `export_font.py` 的 `use_original_base` 分支（marine 基础段拷贝后改数字 0-9 的 top/xSkip 再写）；`patch_marine_numoffset.py` 是实机快速微调工具（每次基于 pak 原版重新算，不累积偏移）。注意 xSkip 大幅缩小会让多字符（如机枪"24"）字间距变窄，单字符（霰弹枪）不受影响。

## 引擎构建与部署

q4game 使用 VS2022、CMake 和 Ninja 构建，核心配置为：

```text
-DCORE=OFF -DBASE=OFF -DRAVEN=OFF -DQUAKE4=ON
```

当前构建目录是 `tmp/build-q4-ninja-only`，本地 SDK 位于 `tmp/windows-sdk-nuget`。产物部署到：

```text
idTech4Apx/quake4/q4game.dll
```

官方备份必须保留为：

```text
idTech4Apx/quake4/q4game.dll.official
```

源码中的中文注释使用 UTF-8 BOM，避免 MSVC 按系统代码页误读；窄字符串中的中文运行时常量必须用显式 UTF-8 字节转义（如 `"\xE5\xB9\xBF\xE6\x92\xAD"` 表示"广播"），否则 MSVC 按系统 GBK 码页编译窄字面量会得到错误字节。

实际编译（2026-08-01 摸清）：工具链在 D 盘非默认位——VS2022 BuildTools `D:/Microsoft Visual Studio/2022/BuildTools/`（MSVC 14.44，Hostx64/x64）+ Windows SDK 10.0.22621.0（需 VS Installer 勾装；缺 UCRT 会 `malloc.h` C1083）。增量编译跑 `tmp/build_q4.bat`（先 `call vcvars64.bat` 初始化 INCLUDE/LIB，再 `ninja q4game`，构建目录 `tmp/build-q4-ninja-only`）。**bat 必须 CRLF**——LF 会让含空格路径的 call 行截断；改 `Subtitles.{h,cpp}` 后先 `cp` 到 `diii4a/Q3E/src/main/jni/doom3/neo/quake4/` 再编译（双写同步）。产物部署三处：`idTech4Apx/quake4/q4game.dll`、`dist/engine/q4game.dll`、`D:/Quake 4/Quake4-Chinese/engine/q4game.dll`（实际游玩目录）。

## 生成工具与部署纪律

- 修改翻译时先改 `src/translations`，再运行对应生成工具，不要只改部署后的 lang。术语译名（武器/单位/装备/概念）以 `docs/glossary.md` 为准，专名用「」包裹（首次「译名」（英文），后续「译名」）；人名、番号（机甲小队等）、保留英文的 Strogg/Makron/Nexus 不包裹。
- `build_lang.py` 还生成 `speaker_map.txt`（声音 shader 名 → 说话人，来自 radio_chatter/broadcast_pa/speaker_chatter 三表 speaker 列）：引擎按此区分角色台词（带名）与环境广播（"广播"/"无线电" fallback）。改 speaker 映射后重跑 `build_lang.py` + 部署 `speaker_map.txt`（**游戏启动时一次性加载，需重启游戏**生效，读档不行）。
- 字幕颜色按说话人类型：广播/含"播报"=黄、无线电=青、角色对白=白，统一正常亮度（`Subtitles.cpp` 的 `subColor_t`；`subtitles.gui` 文本控件 `forecolor` 读 `subTxtR/G/B` 变量）。
- 部分原版 PA 广播借 `func_radiochatter` 无线电实体实现 → 字幕误显"无线电"；需在 tsv 给该声音 speaker 列填"广播"或"XX播报"覆盖 fallback（如 mcc_1 消毒室 `vo_1_1_11_100_*` 配"消毒室播报"）。
- 修改 HUD 或其他生成资产时，同步修改对应 Python 工具并重新生成，避免部署目录与生成逻辑分叉。
- Python 工具从脚本位置推导仓库内部路径；正版数据输入 `Q4BASE`仍是本机路径，运行生成任务前必须核对。
- 生成脚本必须断言待替换块唯一；找不到或命中多次都应失败，不得静默跳过。
- 不要把原版版权资产、历史字体备份、测试 cfg、存档、截图或日志提交到公开仓库。

## 验证要求

最小静态验证：

- 根仓库和 `diii4a`分别执行 `git diff --check`。
- Python 工具至少进行 AST/语法检查。
- `src/engine-patches/0001-quake4-cn-runtime.patch`在已应用补丁的 `diii4a`上通过 `git apply --check --reverse`。
- 构建产物与部署 DLL的 SHA-256 一致，官方备份哈希保持不变。

## 自动打包

- push 到 `main`后，GitHub Actions 运行 Python 检查、安装器测试、上游补丁校验、安装器构建和分发审计，并上传自包含 EXE 与校验文件 Artifact。
- **patch 加新文件时，必须同步 `.github/workflows/package.yml` 的 sparse-checkout 列表**：Validate engine patch 步骤只 checkout 列表内文件做 `git apply --check`，缺文件即失败（c7b653a 加 Entity.cpp 漏同步，导致两次构建红，2026-08-01 补）。
- 版本号 tag 驱动：push `v*`标签触发 Release 构建（版本 = tag 名），在相同验证通过后创建 GitHub Release；main 分支构建用 commit hash 作版本，不发 Release。出正式版打 `vX.Y.Z` tag。
- 本地等价打包入口是 `src/tools/package_release.ps1`。
- 分发包不得包含运行时从正版 pak 提取的 Strogg 图集、GUI、语音别名、存档、日志或截图。

## 英文字幕模式边界

- 英文模式只增加英文字幕，菜单、HUD、面板和字体保持原版英文状态。
- 英文文本直接使用 `src/translations`现有 TSV 的 `en`列生成。
- 安装器界面语言与游戏安装模式是两个独立设置。
- 具体资源边界和验收标准见 `docs/english-subtitles-plan.md`。

运行时验证：

- 正常验收使用 exe 安装版（`Quake4中文启动器.exe`），不得自动加载旧存档。
- 日志位于 `savedata/q4base/qconsole.log`。
- 日志不得出现中文字体缺失、字体图片降采样、`ERROR`或 `FATAL`。
- 原版 pak 的材质重复定义、无窗口 Gamma、主菜单选项数量和未知原版字符串警告属于已知噪声，但仍需分类报告，不能笼统声称“无警告”。
- 字幕调试使用 `harm_g_subtitleDebug 1`，日志应出现 `[SUB]`决策记录。

## 当前功能基线与对照原则

`D:\Quake4-CN`是用户确认的已知可玩基线：除无线电四字的字号/居中和可交互 Strogg 面板纵向位置外，没有用户已知的其他视觉问题。对比时应直接比较实际加载路径、文件哈希和 GUI 块，不得只看脚本名称或截图猜版本。

工程目录在该基线上叠加了正在验证的 HUD、升降机和保存提示修复。不要把 `D:\Quake4-CN`整目录覆盖到工程，也不要反向覆盖目标目录；需要同步时先列出逐文件差异并征得用户确认。
