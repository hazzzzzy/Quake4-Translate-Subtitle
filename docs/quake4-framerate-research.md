# Quake 4 高帧率方案研究（2026-08-05）

## 背景

玩家反馈安装器的"解锁帧率"选项（`com_fixedTic -1`）在高刷新率显示器上观感无提升。
一位玩家指出：`com_fixedTic -1` 在两个 game tic 之间插入的是完全相同的复制帧，
而非真正的插值帧。本文档记录了为解决此问题所做的完整研究和实验。

## 引擎主循环架构

```
主线程                          异步线程（独立，60Hz 定时器）
│                               │
├── session->Frame()            ├── WaitForSingleObject(hTimer)
│   ├── 等待 com_ticNumber      │   （每 16ms 触发一次）
│   ├── RunGameTic() × N        └── common->Async()
│   │   └── game->RunFrame()         └── SingleAsyncTic()
│   └── lastGameTic = latched            └── com_ticNumber++
│
├── session->UpdateScreen()
│   └── game->Draw()
│       └── RenderScene(view)
```

- `USERCMD_HZ = 60`，`USERCMD_MSEC = 16`（编译期常量，`framework/UsercmdGen.h`）
- 异步线程通过 `SetWaitableTimer(hTimer, &t, USERCMD_MSEC, ...)` 以 60Hz 触发
  （`sys/win32/win_main.cpp:836`）
- `com_fixedTic` 控制主线程是否等待 tic：
  - `0`（默认）：主线程等待每个 tic → 渲染率 = 60Hz
  - `-1`：不等待 → 渲染率解锁，但 tic 之间的渲染帧是复制帧
  - `>0`：强制每帧 N 个 tic → 游戏加速

## 研究的三条路线

### 路线 A：相机帧间插值（q4game.dll）

**原理**：保持 60Hz 游戏逻辑，在 tic 之间的渲染帧中用真实时间计算插值因子 `frac`，
在上一 tic 和当前 tic 的相机位置之间做线性插值。

**实现**：
- `Player.cpp CalculateRenderView()`：每 tic 快照 `prevViewOrigin/Axis` 和 `baseViewOrigin/Axis`
- `Player.cpp GetInterpolatedRenderView()`：用 `idLib::sys->Milliseconds()` 计算 `frac`，
  线性插值 `vieworg` 和 `viewaxis`（nlerp + 正交化）
- `PlayerView.cpp RenderPlayerView()`：用插值视角调用 `RenderScene`

**结果**：功能正确实现（日志确认 `interp>0`），但 100Hz 屏幕上肉眼不可见差异。
原因：100Hz 渲染 / 60Hz tic = 每秒仅 40 个插值帧，且 60→100 的帧率跨度本身就微妙。

**局限**：只插值了相机，实体位置和骨骼动画仍以 60Hz 更新（会"跳"）。
完整插值（实体位置 + 骨骼关节）需要改 Quake4.exe 渲染器。

### 路线 B：改引擎 tic 率（Quake4Tweaker 路线）

**原理**：把引擎 tic 率从 60Hz 改为显示器刷新率（如 144Hz），每个 tic 是独一无二的帧。

**实现**（已完成并回退）：
- `Common.cpp`：新增 `com_engineHz` cvar（默认 60），`GetUserCmdMSec()` 返回 `1000 / com_engineHz`
- `Common.cpp Async()`：用 `1000 / com_engineHz` 替代 `USERCMD_MSEC`
- `win_main.cpp`：`SetWaitableTimer` 用 `1000 / com_engineHz` 作为定时器间隔
- `Game_local.cpp RunFrame()`：每帧刷新 `msec = common->GetUserCmdMSec()`
  （原版只在地图加载时设一次）

**遇到的 bug**：
1. 游戏加速：`msec` 只在地图加载时设（`Game_local.cpp:1322`），运行时改 `com_engineHz`
   后 Async 线程用新 ticMsec 生成更多 tic，但每个 tic 仍按旧 msec 推进时间 → 加速。
   修复：每帧刷新 `msec`。
2. 武器模型闪烁、手电筒忽明忽暗、连射中断：帧率相关的游戏逻辑 bug，
   和 Quake4Tweaker v1.1 修复的"弹丸伤害计算"属同类问题。

**结论**：改 tic 率能产生真独立帧，但触发大量帧率相关游戏逻辑 bug，
逐个修复成本高。已回退。

### 路线 C：openQ4 方案（仅解耦渲染上限）

通过源码分析确认 openQ4（github.com/themuffinator/openQ4）的实际做法：

- **tic 率不变**：`USERCMD_HZ = 60`，`GetUserCmdMSec()` 仍返回 16
- **渲染解耦**：新增 `com_maxfps`（默认 240）+ `Common_ThrottlePresentationFrame()` 帧步调控制
- **无插值**：渲染器和 Session 中没有任何插值代码
- **删除 `com_fixedTic -1`**：范围改为 0-10

**结论**：openQ4 和 `com_fixedTic -1` 原理相同（60Hz 逻辑 + 解锁渲染），
只是加了帧步调控制让帧间隔更均匀。"true higher framerates"指的是引擎在 >60 FPS 时
不崩溃/不出慢动作 bug，而非每帧独一无二。

## 三条路线对比

| | 路线 A（相机插值） | 路线 B（改 tic 率） | 路线 C（解耦渲染） |
|---|---|---|---|
| 编译目标 | q4game.dll | Quake4.exe + q4game.dll | Quake4.exe |
| 每帧独一无二 | 仅相机 | 是 | 否 |
| 游戏逻辑 bug | 无 | 有（武器/手电筒/伤害） | 无 |
| 自编译引擎性能风险 | 无 | 有 | 有 |
| 100Hz 屏幕观感 | 微妙 | 微妙（但有 bug） | 无可见提升 |
| 144Hz 屏幕观感 | 可能可感知 | 明显（但有 bug） | 微妙 |

## 当前状态

已回退所有帧率改动，恢复为预编译引擎 + 60Hz。
安装器的"解锁帧率"选项保留（等价 `com_fixedTic -1`）。

## 待办：144Hz 屏幕 A/B 对照测试

用户有 144Hz 屏幕，可作为决定性测试。测试时需重新编译自编译引擎（路线 B）。

### 测试 A：渲染解耦（无 bug）
```
com_engineHz 60
com_fixedTic -1
```
60Hz 逻辑 + 144Hz 渲染，每秒 84 个复制帧。快速转向观察是否有可见提升。

### 测试 B：真高 tic 率（有 bug）
```
com_engineHz 144
com_fixedTic 0
```
144Hz 游戏逻辑，每帧独一无二。观察转向流畅度提升幅度和武器/手电筒 bug 严重程度。

### 判断标准

| 结果 | 决策 |
|---|---|
| B 明显更顺滑 + bug 可接受 | 修 bug，保留 tic 率方案 |
| B 明显更顺滑 + bug 严重 | 实现完整插值（Phase 2 实体插值） |
| A 和 B 差不多 | 永久搁置，保持 60Hz |

## 相关源码位置

| 文件 | 内容 |
|---|---|
| `framework/UsercmdGen.h:40-41` | `USERCMD_HZ`/`USERCMD_MSEC` 定义 |
| `framework/Common.cpp` | `GetUserCmdMSec/Hz`、`Async()` |
| `sys/win32/win_main.cpp:827-836` | `Sys_StartAsyncThread`（定时器） |
| `framework/Session.cpp:3201-3220` | `com_fixedTic` 等待逻辑 |
| `quake4/Game_local.cpp:3560-3565` | `RunFrame` 时间推进 |
| `quake4/Player.cpp:11302-11338` | `SmoothenRenderView`（原版视角插值，仅 demo 回放） |
