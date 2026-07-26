# 官方 Quake4.exe 中文兼容层

该目录用于验证官方 Windows 1.4.2 `Quake4.exe` 的中文运行路径。目标进程保持为玩家原有的官方 EXE，磁盘文件哈希保持原值；加载器在进程启动阶段加载 `Q4CNCompat32.dll`。

## 当前支持版本

| 属性 | 值 |
|---|---|
| 文件版本 | `1.4.2.0` |
| 架构 | x86 |
| PE 时间戳 | `0x4672CE50` |
| 映像大小 | `0x014CA000` |
| SHA-256 | `DF09FA067569410EFF6E734DD67C8BFF0BE44B3C35CA532F440748D875285262` |

加载器先校验完整文件哈希。兼容 DLL 进入进程后再次校验 PE 头，以及 `idDeviceContext::FindFont`、`SetupFonts`、`Init` 三处机器码签名。任一校验失败时，官方主线程保持挂起并由加载器结束该进程。

## 构建

```powershell
powershell -ExecutionPolicy Bypass -File .\src\official-compat\build.ps1
```

产物位于仓库内的 `tmp\build-official-compat`：

- `Q4CNLoader.exe`
- `Q4CNCompat32.dll`

## 版本校验

```powershell
.\tmp\build-official-compat\Q4CNLoader.exe `
  --game-dir "D:\Quake 4" `
  --save-dir ".\tmp\official-poc\savedata" `
  --verify-only
```

## PoC 启动

```powershell
.\tmp\build-official-compat\Q4CNLoader.exe `
  --game-dir "D:\Quake 4" `
  --save-dir ".\tmp\official-poc\savedata"
```

当前里程碑验证版本识别、挂起启动、DLL 加载和进程内函数签名。下一步在这些已验证地址上接入分页中文字体与 UTF-8 文本绘制。
