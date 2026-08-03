# Changelog
## v1.2.10 — 2026-08-04

### 修复 v1.2.9 性能回退

引擎:
- Quake4.exe 回退到预编译版本（v1.2.9 自编译引擎导致部分玩家严重卡顿）
- SDL2.dll 回退到配套旧版
- q4game.dll 保留 v1.2.9 版本（喷血修复不受影响）

说明:
- v1.2.9 的准心命中变红功能暂时不可用（该修复需要自编译引擎，后续版本设法恢复）
- 喷血修复、安装器界面升级、存档保护等 v1.2.9 其他改动均保留

## v1.2.9 — 2026-08-03

### 准心命中变红 + 喷血修复 + 安装器界面升级

引擎改动（Quake4.exe，首次编译完整引擎）:
- 准心命中变红修复：ui/Window.cpp GetWinVarByName 补充 matColor_x/y/z → matColor_r/g/b 映射。原版 cursor.gui 用 Vec4 的 x/y/z 分量名设命中红色，idTech4A++ 只实现了 r/g/b/w 别名遗漏 x/y/z，导致 set matcolor_x/y/z 找不到目标变量、命中只有缩放没有变红。在 #ifdef _RAVEN 块内新增 3 个 if 映射，不影响其他游戏编译
- SDL2 升级至 2.30.10（匹配新编译的 Quake4.exe）

引擎改动（q4game.dll）:
- 喷血修复：Game_local.cpp HitScan 三处 + Projectile.cpp DefaultDamageEffect，命中标有 bleed 属性的有机体时强制传 flesh materialType，覆盖 idAnimatedEntity/idAFAttachment/所有 bleed=true 实体（Strogg 步兵/人彘/俘虏/生命补给器等），金属管道保持火花
- 准心变红清理：移除 Player.cpp 中无效的 SetStateString(matcolor_x/y/z) 绕过代码（SetStateString 只设 state 字典 key，不能操作窗口属性）

安装器:
- 安装器界面标题右侧新增开发者链接：GitHub logo + B站 logo，点击跳转浏览器
- exe 图标替换为 Quake4 原版图标
- 版本号标注 v1.2.9（标题栏 + 标题右侧）
- 安装补丁时保留已有存档目录（不清空重建）

补丁/CI:
- 引擎补丁新增 ui/Window.cpp + quake4/Projectile.cpp
- package.yml sparse-checkout 同步新增两文件

## v1.2.8 — 2026-08-02

### 主菜单分辨率/比例设置可选 + FOV 调整

引擎改动（q4game.dll）:
- g_fov 加 CVAR_ARCHIVE，选值持久（重启保持）
- 新增 Harm_ApplyResolution：解析 harm_g_resIndex → r_mode -1 + r_customWidth/Height + vid_restart；经 game->HandleMainMenuCommands 直接调用（主菜单时 Clear 未执行、命令未注册；session HandleMainMenuCommands 是白名单不转发未知命令，但每个菜单命令都转发给 game）
- harm_g_resIndex 加 CVAR_ARCHIVE
- 从 rvSubtitles::Draw 移除失效的选项注入/解析块（主菜单 player==NULL 提前返回，Draw 不执行）

GUI patch（build_dist_extras.patch_resolution_settings，安装器现场生成）:
- 三个分辨率 choiceDef 硬编码 choices/values + 绑 harm_g_resIndex
- 比例 choiceDef 补 choices/values（原引用 fixup_mode 填充的 gui 变量）
- vidwarn 确认按钮（ESC 路径 curr==34 + pop_b_vidwarn_close onAction）触发 harm_applyVideo：切换不立即 vid_restart，点确认时一次性应用
- 系统设置页新增 FOV 选择器（高级设置与音频之间），绑 g_fov，选项 80/90/100/110

其他:
- 启动器不再命令行覆盖分辨率：首次写入 cfg 后续尊重用户修改
- 视频设置弹窗提示文字："更改将在下次运行 Quake 4 时生效" → "更改将在返回主菜单时立即生效"
- patch 与 package.yml sparse-checkout 加入 SysCvar.cpp

## v1.2.7 — 2026-08-02

### 字幕配色系统 + 射击表面类型修复

引擎改动:
- 字幕五色配色系统：角色白/无线电青/Strogg广播黄/舰船广播绿/Makron紫
- 人类广播(非vo_pa_*)自动识别为绿色"舰载广播"前缀，Strogg广播(vo_pa_*)保持黄色
- Makron加入knownSpeakers列表，Boss嘲讽显示紫色"Makron："前缀
- 字幕换行优化：空格断行阈值70%改为92%，行宽预算356改为362
- Event_StartSound精准字幕hook(替代catch-all，消除重复字幕+说话人误识别)
- 过场门控修复：只拦speaker实体，不误杀剧情对白
- PA广播距离门控豁免：speaker实体跳过距离/PVS检查
- rvModmodel无头分支补字幕hook
- Clip.cpp Sentry物理故障速度清零修复
- GetDefaultSurfaceType修复：idAnimatedEntity默认METAL改为FLESH，生命补给器/尸体射击喷血而非冒火花

翻译改动:
- 89条原版缺失lipSync decl声音批量补齐
- 受伤/死亡音格式统一：【受伤】【死亡】
- Voss过场问候翻译+lipSync decl
- 3条Hub字幕截短修正
- Voss简报"Damn"漏译修正


## v1.2.6 — 2026-08-02

### 字幕系统全面修复：过场对话/PA广播/换行/批量补缺

引擎改动（q4game.dll）:
- Subtitles.cpp 过场门控修复：过场期间只拦 speaker 实体（环境广播），不再误杀 rvModmodel/idAI 剧情对白（Voss 被抓过场恢复字幕）
- Subtitles.cpp PA广播距离门控豁免：speaker 实体跳过距离/PVS 门控，Strogg 化后全设施 PA 广播字幕不再时有时无
- Subtitles.cpp 字幕去重：同一字幕 300ms 内不重复添加（多 hook 并发保护）
- Subtitles.cpp 字幕换行优化：空格优先断行阈值从 70% 改为 92%，文字填满行才换，不再在英文词后提前断行（SUB_TEXT_W 356->362）
- Entity.cpp Event_StartSound 字幕 hook：脚本通过 startSound 播放的 snd_*/lipsync_*/vo_* 对白补字幕（Voss 过场问候、MCC 守卫等），不与 StartLipSyncing/AI Speak/speaker 实体的已有 hook 冲突
- Entity.cpp StartSoundShader catch-all hook 已移除（与已有 hook 双重触发导致重复字幕+说话人误识别）
- GameEdit.cpp rvModmodel::Event_Speak 无头分支补字幕 hook
- Clip.cpp TestHugeTranslation 速度清零修复 Sentry 物理故障掉帧（v1.2.5 已发，此处纳入补丁）

翻译改动:
- 修复 3 条 Hub 关卡字幕截短（vo_1_2_14_10_1 Voss简报/vo_1_2_17_10_7 Strauss被困/vo_1_2_20_40_1 维护平台）
- 新增 Voss 过场问候对白翻译+lipSync decl（vo_2_1_2_70_1_full，原版无 decl）
- 批量补齐 89 条原版缺失 lipSync decl 的 vo_ 声音（Makron嘲讽/战斗喊叫/储藏塔剧情/网络塔对话/车队指令等）
- 受伤/死亡音格式统一：（受伤音）->【受伤】，(死亡音）->【死亡】
- Voss 简报翻译修正："Damn" 漏译补为"好家伙"

CI:
- sparse-checkout 新增 GameEdit.cpp

## v1.2.5 — 2026-08-01

### 引擎修复：Hub1 关卡 Sentry 物理故障导致严重掉帧（6fps）

- 根因：Hub1（Nexus 枢纽隧道）3 台 `rvMonsterSentry` 生成时掉出地图底部，物理引擎每帧检测到 >4096 单位的巨型位移（`TestHugeTranslation`），`fraction=0` 短路了碰撞检测但未清零速度，形成「速度保留→下帧重复」死循环，3 台 Sentry 各被 3 处 trace 调用点内联触发，每帧数十次 Printf + 物理计算拖垮帧率
- 修复：`quake4/physics/Clip.cpp` 的 `TestHugeTranslation` 中检测到巨型位移时直接 `SetLinearVelocity(vec3_origin)` 清零实体速度，打断死循环；同时限速 Printf 最多 5 条避免日志 I/O 开销
- 效果：Sentry 停止挣扎不再吃 CPU，帧率恢复正常；玩家可正常击杀卡住的 Sentry 推进剧情

## v1.2.4 — 2026-08-01

### 修复 3 条 Hub 关卡字幕截短（转写不完整导致中文字幕缺段落）

- `vo_1_2_14_10_1`（Voss 简报）：英文转写截短在"逞英雄。Voss out."，实际音频含完整「四元节点/Nexus」段落（~100 词 / 30 秒）。修复 radio_chatter `str_380070` + dialogue_lips `str_300640` 英文+中文补全
- `vo_1_2_17_10_7`（Strauss 被困呼叫）：英文截短在"What has happened?"，实际音频含"门打不开了，需要支援"（20 词 / 6.8 秒）。修复 radio_chatter `str_380074`
- `vo_1_2_20_40_1`（Strauss 维护平台指引）：英文截短在"Get onboard."，实际音频含"在线缆上方行驶，供 Strogg 检修"（22 词 / 5.1 秒）。修复 radio_chatter `str_380079`
- 根因：dialogue_lips.tsv 有完整版英文+中文，但 radio_chatter.tsv（lipsync decl 实际引用的 string id 来源）的英文来自被截短的声音 shader description，中文跟着截短；用 ffprobe 词/秒全量扫描 931 条语音确认仅此 3 条

## v1.2.3 — 2026-08-01

### 字幕标点全角化 + 专名去英文括号 + GUI 加载机制文档

- 字幕半角标点全角化：speaker_chatter/radio_chatter 中文列 38 条半角标点（逗号/冒号/问号/感叹号/分号）转全角，修复字幕混入英文标点
- 专名去英文括号：全部 tsv 约 50 处 `「译名」（英文）` 去掉英文括号，只保留 `「中文译名」`（斯托伊文特 21 处、四元节点 4 处等）
- CLAUDE.md/AGENTS.md 新增「GUI 加载机制与字体共用约束」章节：viewmodel 武器弹药 GUI + cursor.gui 只从 pak 加载不走 savepath；marine 被枪身弹药数字/准心人名/终端数字三处共用、字形无法分别；改这些数字位置走 fontdat top/xSkip 不走 GUI rect
- build_dist_extras 清理无效 patch_cursor_gui（cursor.gui 不走 savepath，补丁不生效）

## v1.2.2 — 2026-08-01

### 枪身弹药数字字体恢复原版 + 位置修正

- 武器 viewmodel 弹药计数（机枪/高爆弹/霰弹枪）与 MCC 终端/医疗面板/简报/监控的数字恢复原版方正字形：`marine` 字体基础段（ASCII/数字）改为直接拷贝 pak001 原版 fontdat+tga，CJK 宽表仍用思源黑体；marine 独立 canonical 避免原版基础段经别名传染字幕字体 lowpixel
- 枪身弹药数字位置补偿：原版方正数字 `xSkip`(~37) 远大于思源(~21)导致 center 偏左、top 略偏上，经武器 GUI 的 textscale 4~6 放大后明显；在 fontdat 数字字形上叠 `top-4`/`xSkip-15`（实机标定）修正到水平居中 + 垂直不偏上。GUI rect 改动实测不生效（viewmodel GUI 不从 savepath 加载），改 fontdat 度量（PaintChar 直接读取）解决

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
