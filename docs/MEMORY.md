# 记忆索引

- [Quake 4 汉化 PoC 已通过](quake4-poc-passed.md) — 引擎路径/启动参数/中文渲染 cvar/exportFont bug 绕过/自动化要点，正式翻译期直接采用
- [第三轮反馈修复](quake4-feedback-fixes-r3.md) — 字幕标签清理/可听性门控/无线电字幕/字体基线机制（HUD 裁切根因）/Strogg 字体 full 化/米勒卡关分析
- [第四轮反馈修复](quake4-feedback-fixes-r4.md) — 读档崩溃根因（gui 覆盖必须基于 pak021 底稿、只改数值）/字幕按 fontdat 真实度量断行+断点策略/无线电 decl 缺口 251 条已补齐（sndshd description 是台词一手文本源）/MSVC 中文字面量 GBK 坑/纯 cfg 帧驱动测试法
- [第五轮：字体拉伸与体积](quake4-font-aspect-and-size.md) — 拉伸根因=GUI 640×480 虚拟坐标拉宽屏（ASPECT=0.75 预压缩修复）/体积 1067MB→131MB（RLE TGA + 同源家族 .mtr 材质别名）/换字体改 FAMILIES 重跑即可
- [Strogg 转译动画与字体语义](quake4-strogg-changeover.md) — 已实装：strogg=原版外星文直通+CJK→符号宽表、r_strogg=思源 Medium、textchange 中文化（神经细胞已植入）；含实机演示法
- [汉化分发包](quake4-dist-package.md) — dist/Quake4-CN-v1.0 打包清单/启动器要点（pak021 检查防读档崩溃）/排除项/重打包方法
- [第六轮：换图崩溃与字幕完善](quake4-r6-crash-and-subtitles.md) — 崩溃根因=GUI 裸指针跨图悬空（每帧 FindGui 修复）/无 cdb 符号化排障流程/speaker 字幕钩子/友军门控/面板布局三处联动
- [第九轮：MCC 对齐 + 开源仓库 + Strogg 士兵](quake4-r9-mcc-align-repo-strogg.md) — ASCII 视觉中线偏上根因/正解全档 ascii_drop=drop（度量陷阱教训）/hazzzzzy/Quake4-Chinese public 仓库剥离 5 类版权物+postinstall+汉化流程指南/Strogg 士兵原版无 speech 只有 grunt
- [高帧率方案研究](quake4-framerate-research.md) — 三条路线（相机插值/改 tic 率/openQ4 解耦），改 tic 率有武器闪烁 bug，openQ4 也不改 tic 率；待 144Hz 屏幕 A/B 测试决策
