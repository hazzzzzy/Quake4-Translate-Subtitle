# Changelog

## v1.2.1 — 2026-08-01

### 字幕颜色 + 驾驶员映射修正 + 专有名词「」格式

- 字幕按说话人类型着色：广播/地点播报=黄、无线电=青、角色对白=白，统一正常亮度（不再淡色）。`Subtitles.h/cpp` 加 `subColor_t` 枚举取代旧 `dimmed` 二态；`subtitles.gui` 文本控件 `forecolor` 改读 `subTxtR/G/B` 状态变量
- walker bay 驾驶员映射修正：70 段驾驶员不再错配"Morois 下士"（实为测试员）→"机甲驾驶员"；40 段驾驶员从"广播"→"机甲驾驶员"；Check 译"收到"→"检测通过"
- 专有名词统一「译名」（英文原词）格式：walker「步行者」、Stroyent「斯托伊文特」、Tetranode「四元节点」、Gladiator/Harvester/Gunner/Hover Tank/Failed Transfer/Repair Bot/Stream Protector 同款；番号"机甲小队/机甲师"保留不拆；Strogg/Makron/Nexus 仍保留英文
- 消毒室 PA 广播（原版用 func_radiochatter 实现，字幕误显"无线电"）配"消毒室播报"映射；颜色判断含"播报"→黄
- `glossary.md` 更新 walker 条目 + 「」排版规范
- CI 修复：patch 验证 sparse-checkout 补 Entity.cpp（c7b653a 引入的遗漏）

## v1.2.0 — 2026-07-26

### 英文原版 + 英文字幕模式

- 安装器新增互斥安装模式：`完整简体中文汉化` / `英文原版 + 英文字幕`。
  英文模式保留原版菜单、HUD、面板与字体，只增加语音字幕
- 引擎 `Subtitles.cpp` 按 `sys_lang` 分支三处表现：说话人冒号（全角`：`/半角`: `）、
  无名友军兜底名（士兵/Marine）、断行度量字库路径（`fonts/<sys_lang>/lowpixel_24.fontdat`）；
  挂钩侧中文语义前缀（无线电/广播）在英文模式映射为 Radio/PA，触发、
  可听性门控、时长、队列与面板行为两种模式完全一致
- 新增 `english_lipsadd.lang`（`build_lang.py` 从 TSV `english` 列生成，979 条）：
  仅补自建 id（无线电 253 + AI 语音 726）；主线对白 3962 条原版
  `english_lips.lang` 已全覆盖。命名刻意避开原版同名文件防 savepath 遮蔽
- 英文模式为纯静态部署：跳过全部四类正版资产现场生成，也不部署语音路径
  别名包（decl 按声音名查找，与 `vo_chinese` 路径无关）
- 启动器单二进制按文件名分流：`Quake4英文字幕启动器.exe` 以
  `sys_lang english` + 独立存档目录 `savedata-english` 启动，
  与中文版及原版存档三方隔离；存档管理界面同步展示三套存档
- 安装器测试新增英文模式部署子集与载荷校验用例（12 用例全绿）

### 修复与工程

- `.gitignore` 与打包审计补齐 v1.1.x 新增运行时生成物
  （`r_strogg_*.tga`、`hud_strogg.gui`、`guis/common|monitors|movers/`、
  引擎首启落盘文件），防止误入库/误打包
- 打包审计 required 清单加入英文字幕载荷（`english_lipsadd.lang`、`subtitles.gui`）
- `docs/english-subtitles-plan.md` 勘误：`english_lips.lang` 同名遮蔽风险、
  别名包依赖判断错误

## v1.1.1 — 2026-07-23

### 单文件安装器

- 将公开可分发的 `dist/engine` 与 `dist/savedata` 完整嵌入 PyInstaller 单文件 EXE
- 冻结运行时从 `_MEIPASS/payload` 读取内置资产，不再依赖下载目录旁的 `engine/savedata`
- Release 新增可直接运行的版本化安装器 `Quake4-Chinese-Installer-v1.1.1.exe`
- `SHA256SUMS.txt` 同时覆盖 EXE 与便携 ZIP，GitHub Actions Artifact 也上传两种格式

## v1.1.0 — 2026-07-23

### 图形安装与存档

- 新增独立图形安装器，自动识别或手动选择 Quake 4 1.4.2 目录
- 安装进度按复制字节、GUI 生成步骤和语音别名处理量真实推进
- 在游戏目录生成独立中文启动器，可选创建桌面快捷方式，并沿用原版 `Quake4.exe` 图标
- 汉化版使用独立 `fs_savepath`，与原版存档共存；新增两套存档的查看与 ZIP 备份管理

### 运行资产与视觉修正

- 从玩家自己的 `pak001/pak014/pak021/zpak_english*` 现场生成版权敏感运行资产
- 修正改造前后 Strogg 面板、生命补给器、静态状态面板和传入通讯的字体与对齐
- 完整引擎补丁补齐 `Player.cpp/.h`，当前权威补丁覆盖 8 个上游文件

### 仓库与发布

- 仓库更名为 `Quake4-Translate-Subtitle`，工程根直接作为 Git 根目录
- 新增 GitHub Actions：验证 Python、安装器测试、上游补丁、Windows 安装器构建和分发资产审计
- push `v*` 标签后由 GitHub 构建 ZIP、生成 SHA-256 校验文件并发布 Release
- 新增英文 README；独立英文字幕模式仍按 `docs/english-subtitles-plan.md` 规划推进

## v1.0.10 — 2026-07-18

### DLL 侧

- 字幕面板 `SUB_ROW_ADJ` 1.0 → 0.0：v1.0.7 的 +1 虚拟 px 让字幕相对面板偏下，撤回恢复居中

### wristcomm.gui 新补丁（新版权敏感物）

- `quicksave_msg` rect y=64→110 与 hud.gui 保持一致
- 根因：v1.0.9 改了 hud.gui 的 y=110 避开准星区，但 objectiveSystem（=wristcomm.gui）里也定义了 quicksave_msg y=64——两处不再重叠导致"游戏已保存"出现两处
- 加入 postinstall 版权敏感物补齐流程

### hud.gui 无线电改为单行

- `str_200272` "incoming" → **"传入通讯"**（原 "传入"），`str_200273` "transmission" 保留但 t_radio2 rect 移出屏幕不显示
- `t_radio1` rect(557,4,69,13) → (556,12,72,14)：垂直居中于背景条 y=5-33
- `t_radio2` rect(557,17,69,13) → (556,999,72,14)：移出屏幕，等效隐藏但保留 windowDef 结构存档兼容

## v1.0.9 — 2026-07-18

### 字体：数字沿用原版视觉

- `chain` 家族独立 canonical，**基础段 fontdat + tga 直接用原版 pak021**（数字/字母恢复原版 Strogg 装饰视觉）
- 用户观察 hud.gui 里 chain 字体**全部用于纯数字**（`player_ammo` / `player_health` / `player_armor` / `player_totalammo` / `powerupN_time`），无中英混排 → 换回原版零副作用
- 副作用回滚：撤销 v1.0.7 的 HUD 数字 rect h+3 补丁（`ammo_amount` / `health_amount` / `armor_amount` 及 MP 版共 7 处）——原版数字与 rect 天然兼容
- CJK 宽表仍保持思源黑体 Medium（chain 用不到中文但保留以防脚本注入）
- dist 磁盘 +60MB（chain 独立宽表页无法与 marine 共享）

### hud.gui 三处新补丁

- 无线电背景条 `radio_backbar` rect(520,5,113,28)→(556,5,72,28) 缩窄贴合中文 4 字（原版按英文 20 字设计留白严重）
- 可交互提示 `bracket_text` textscale .25→.4 让准星旁"可交互"视觉与原版 INTERACTIVE 相近
- `quicksave_msg` rect y 64→110 下移避开准星区域 bracket_text 重叠

## v1.0.8 — 2026-07-18

### hud.gui 补丁扩展

- 关卡末尾大门"EXIT"红色标签重定向：`p_exit_text` 引用从 `#str_200013`（EXIT→退出，主菜单退出按钮共用）改为 `#str_200379`（exit→撤离，关卡语境）。用户反馈"翻译为退出了，应该是撤离"

### mainmenu.gui 补丁扩展

- 制作人员名单职位汉化：credits 段（line 8543-17150）内 36 条硬编码职位（原不走 #str_id）翻译，共替换 78 次。例：`Executive Producer` → `执行制作人`、`Programming Leads` → `编程组长`、`Level Design` → `关卡设计`、`Special Thanks` → `特别鸣谢` 等
- 含人名的兼任标题保留人名：`Fred Hooper - Assistant Art Lead` → `Fred Hooper - 副美术组长`
- 人名（Kevin Long 等约 100 个）与工作室名（Splash Damage / Womb Music / id Software）不译

## v1.0.7 — 2026-07-18

### DLL 侧

- 字幕说话人前缀分隔符改为全角冒号：`"广播: xxx"` → `"广播：xxx"`（去掉半角冒号+空格，改中文标点）
- 字幕面板墨迹垂直居中：`SUB_ROW_ADJ = 1.0` 补偿 CJK drop 让墨迹中线接近面板中线（原偏顶 ~2 屏幕像素）

### hud.gui 补丁扩展

- 切枪武器名 `ws_name` rect y 42→48（用户反馈"向下移一点"；下移 6 虚拟 px ≈ 7 屏幕像素，避开图标 y=20-46 重叠）
- HUD 大数字 rect h 26→29（+3 名义 px，修 v1.0.6 后 ASCII drop=2 让数字位图底端 y=455 卡 rect 底边被裁 10% 的问题）
  - 覆盖 `ammo_amount` / `ammo_amount_nc` / `health_amount` / `armor_amount` 及 MP 版 7 处

### mainmenu.gui 补丁（新增补齐物）

- 设置页 3 按钮 rect y+4：`set_sys_t_auto` (自动检测设置) / `set_sys_t_adv` (高级设置) / `set_sys_t_b9` (高级音频设置)
- CJK 视觉与容器 rect 中线对齐（容器 h=25、文字 rect h=18 原贴容器顶）
- 加入 postinstall 版权敏感物补齐流程

## v1.0.6 — 2026-07-18

### 字体基线（中英混排视觉对齐）

- 修复 `export_font.py`：全档 `ascii_drop = drop`（12→1、24→2、48→4 名义 px）
- 用户反馈"MCC 着陆场 里 MCC 顶部偏上"根因：CJK 已 drop 后视觉在 rect 里居中，ASCII 未 drop 相对 rect 偏上 3.2 屏幕像素（不是相对 CJK）
- 修复后实机验证：`Sanchez 列兵`、`Raven 小队`、`传入 通讯` 中英混排完全齐平；HUD 数字（8/14/100/50）无裁切
- 该修复覆盖所有 UI 家族的 24/48 号（chain/marine/lowpixel/profont/r_strogg），受益场景：loading 地名标签、准星名牌、无线电两行、切枪武器名、菜单标题

## v1.0.5 — 2026-07-17

### CJK 字体质量

- 换字体到**思源黑体 Medium**（Adobe/Google，OFL 开源可分发；替代 v1.0.4 的微软雅黑常规）
- 全档 2x 超采样渲染（1x 灰度 AA 小字发虚参差，1x 单色小字锐利但放大锯齿，2x AA 两全）
- 按 16:9 分辨率预压缩宽高比 `ASPECT=0.75` 抵消引擎 GUI 640×480 → 16:9 拉伸（方块汉字被拉扁根源）
- CJK 视觉基线下沉 `drop=1/2/4`（12/24/48 号）修复"汉字在拉丁窗格里普遍偏上"

### 体积优化

- TGA 改 RLE (type 10) + 同源家族共享贴图（材质别名 `.mtr`），字体从 **1067MB → 131MB**（磁盘/显存同比例降）

### Strogg 转译

- `strogg` 家族改**原版直通** + CJK Knuth 乘散列稳定映射到原版 62 个符号（改造前终端外星文氛围恢复）
- `r_strogg` 家族沿用思源黑体（可读侧）
- `med1_textchange.gui` 中文化补丁（神经细胞植入转译动画）

## v1.0.4 — 2026-07-16 晚

### 读档崩溃根因（重大）

- `hud.gui` 覆盖必须基于 **pak021 版底稿**（1.4 补丁 2507 行，运行时实际生效）；上轮基于 pak001 版（2272 行）导致结构差 235 行，存档序列化流错位内存踩坏
- 覆盖只允许改数值（rect/textscale），禁止增删 windowDef/脚本/变量

### 字幕改进

- 换行按 fontdat 真实字体度量计算（原 MAX_UNITS=58 半角只用面板 64% 宽）
- 空格断点仅在行预算 70% 之后可取，防"瘫痪了 Strogg 的"式短行

### 无线电 decl 缺口补齐

- 全游戏 336 条 `func_radiochatter` 台词，原版仅 84 条有 lipsync decl；本轮补齐 251 条（`vo_1_2_20_50_1` 全资产无定义 = 死引用，跳过）
- 英文文本一手来源 = `.sndshd` 的 `description` 字段（3948 条 VO shader 全带台词全文）；辅助源 = Quake4[CC] 听障模组转写 archive.org 快照

### 自研 exporter 上线

- 替代引擎 `exportFont` 三大缺陷：bearing 烘位图 / xSkip 用真 advance / 尾字符不丢
- 废弃 48=24 复制、哨兵字符两个绕过

## v1.0.3 — 2026-07-17 凌晨

### 启动器

- 加 `+set logFile 2`（日志常开，报障直接发 `qconsole.log`）
- GTX 1650 稳 60 fps 默认关软阴影 `harm_r_softStencilShadow 0`

### 换图崩溃修复

- `rvSubtitles::Draw` 缓存 gui 裸指针跨图悬空 → CRT c0000409；改每帧按名 `FindGui`

## v1.0.2 — 2026-07-16 下午

### 第三轮反馈

- 字幕文本剥离 `{furrow}`/`{idle}` 等录音情绪标记（585 处保留在源 lang）
- 可听性门控：友军/敌军差异化 PVS+距离容差
- AI 无头模型走 `idAI::Speak` else 分支补挂 lipsync
- HUD 数字裁切根源分析：引擎运行时 `maxHeight = max(全部字形 top)`
- Strogg 两套字体全字库化（`chinese` 2048 宽）

## v1.0.1 — 2026-07-16 早

### 第二轮反馈

- 设置页问号根因：`gb1` 档只有 GB2312 一级，缺全角符号区；改用 `full` 档 = GB2312 全集 ∪ 主表实用字 ∪ ASCII
- 小队名全部中文化（Rhino→犀牛小队、Scorpion→天蝎小队等）

## v1.0.0 — 2026-07-16 深夜

### PoC 通过

- UI 2272 条 + 对白 3962 条全部翻译并部署（build_lang 99%）
- 字幕系统实装（`rvSubtitles` 单例 + LipSync/Game_local/AI 挂钩 + `subtitles.gui` 面板 + 3 个 cvar）
- 引擎选定 [idTech4A++ v1.1.0harmattan70](https://github.com/glKarin/com.n0n3m4.diii4a/tree/v1.1.0harmattan70)（master 与 h70 ABI 不兼容）
- 中文渲染链路打通：`sys_lang chinese` + `harm_gui_wideCharLang 1` + 5 个 lang（code/guis/lips/mappack/maps）+ 字体 fontdat/TGA + VO 路径别名 pk4
