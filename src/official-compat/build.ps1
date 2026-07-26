param(
    [string]$Configuration = "Release"
)

$ErrorActionPreference = "Stop"
$source = $PSScriptRoot
$repository = (Resolve-Path (Join-Path $source "..\..")).Path
$workspace = (Resolve-Path (Join-Path $repository "..")).Path
$build = Join-Path $repository "tmp\build-official-compat"
$sdkRoot = Join-Path $workspace "tmp\windows-sdk-nuget"
$sdkVersion = "10.0.26100.0"
$sdkInclude = Join-Path $sdkRoot "common\c\Include\$sdkVersion"
$sdkBin = Join-Path $sdkRoot "common\c\bin\$sdkVersion\x64"
$sdkLib = Join-Path $sdkRoot "x86\c"

$vswhere = Join-Path ${env:ProgramFiles(x86)} "Microsoft Visual Studio\Installer\vswhere.exe"
$vsRoot = $null
if (Test-Path -LiteralPath $vswhere) {
    $vsRoot = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
}
if (-not $vsRoot) {
    $localBuildTools = "D:\Microsoft Visual Studio\2022\BuildTools"
    if (Test-Path -LiteralPath $localBuildTools) {
        $vsRoot = $localBuildTools
    }
}
if (-not $vsRoot) {
    throw "未找到带 x86 C++ 工具链的 Visual Studio Build Tools"
}

$vcvars = Join-Path $vsRoot "VC\Auxiliary\Build\vcvarsall.bat"
$cmake = Join-Path $vsRoot "Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe"
$ninja = Join-Path $vsRoot "Common7\IDE\CommonExtensions\Microsoft\CMake\Ninja\ninja.exe"
foreach ($path in @($vcvars, $cmake, $ninja)) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "缺少构建工具：$path"
    }
}

$rc = Join-Path $sdkBin "rc.exe"
$mt = Join-Path $sdkBin "mt.exe"
$sdkPaths = @(
    (Join-Path $sdkInclude "ucrt"),
    (Join-Path $sdkInclude "shared"),
    (Join-Path $sdkInclude "um"),
    (Join-Path $sdkInclude "winrt"),
    (Join-Path $sdkLib "ucrt\x86"),
    (Join-Path $sdkLib "um\x86"),
    $rc,
    $mt
)
foreach ($path in $sdkPaths) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "缺少本地 Windows SDK 文件：$path"
    }
}

$include = @(
    (Join-Path $sdkInclude "ucrt"),
    (Join-Path $sdkInclude "shared"),
    (Join-Path $sdkInclude "um"),
    (Join-Path $sdkInclude "winrt")
) -join ";"
$lib = @(
    (Join-Path $sdkLib "ucrt\x86"),
    (Join-Path $sdkLib "um\x86")
) -join ";"

$command = @(
    "setlocal EnableExtensions EnableDelayedExpansion",
    "call `"$vcvars`" x86 >nul",
    "set `"INCLUDE=$include;!INCLUDE!`"",
    "set `"LIB=$lib;!LIB!`"",
    "set `"PATH=$sdkBin;!PATH!`"",
    "`"$cmake`" -S `"$source`" -B `"$build`" -G Ninja -DCMAKE_MAKE_PROGRAM=`"$ninja`" -DCMAKE_BUILD_TYPE=$Configuration -DCMAKE_RC_COMPILER=`"$rc`" -DCMAKE_MT=`"$mt`"",
    "`"$cmake`" --build `"$build`" --config $Configuration"
) -join " && "

& cmd.exe /d /v:on /s /c $command
if ($LASTEXITCODE -ne 0) {
    throw "official-compat 构建失败，退出码 $LASTEXITCODE"
}

Write-Output "构建完成：$build"
