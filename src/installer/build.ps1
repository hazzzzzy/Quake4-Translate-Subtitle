param(
    [string]$Configuration = "Release",
    [string]$Python = "",
    [string]$WindowsSdkRoot = ""
)

$ErrorActionPreference = "Stop"
$source = $PSScriptRoot
$repository = (Resolve-Path (Join-Path $source "..\..")).Path
$distribution = Join-Path $repository "dist"
$build = Join-Path $repository "tmp\build-installer-native"
$package = Join-Path $repository "tmp\package-installer"
$pyiWork = Join-Path $repository "tmp\pyinstaller-work"
$pyiSpec = Join-Path $repository "tmp\pyinstaller-spec"
$sdkRoot = if ($WindowsSdkRoot) {
    $WindowsSdkRoot
} else {
    Join-Path $repository "tmp\windows-sdk-nuget"
}
$sdkVersion = "10.0.26100.0"
$sdkInclude = Join-Path $sdkRoot "common\c\Include\$sdkVersion"
$sdkBin = Join-Path $sdkRoot "common\c\bin\$sdkVersion\x64"
$sdkLib = Join-Path $sdkRoot "x64\c"

if ($Python) {
    $python = $Python
} else {
    $localPython = Join-Path $repository "venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $localPython) {
        $python = $localPython
    } else {
        $pythonCommand = Get-Command python.exe -ErrorAction SilentlyContinue
        if (-not $pythonCommand) {
            $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
        }
        if (-not $pythonCommand) {
            throw "Python 3 was not found"
        }
        $python = $pythonCommand.Source
    }
}

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
    throw "Visual Studio Build Tools with the x64 C++ toolchain was not found"
}

$vcvars = Join-Path $vsRoot "VC\Auxiliary\Build\vcvarsall.bat"
$cmake = Join-Path $vsRoot "Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe"
$ninja = Join-Path $vsRoot "Common7\IDE\CommonExtensions\Microsoft\CMake\Ninja\ninja.exe"
$cmakeCommand = Get-Command cmake.exe -ErrorAction SilentlyContinue
$ninjaCommand = Get-Command ninja.exe -ErrorAction SilentlyContinue
if (-not (Test-Path -LiteralPath $cmake) -and $cmakeCommand) {
    $cmake = $cmakeCommand.Source
}
if (-not (Test-Path -LiteralPath $ninja) -and $ninjaCommand) {
    $ninja = $ninjaCommand.Source
}
$rc = Join-Path $sdkBin "rc.exe"
$mt = Join-Path $sdkBin "mt.exe"
$useLocalSdk = (
    (Test-Path -LiteralPath $sdkInclude) -and
    (Test-Path -LiteralPath $sdkLib) -and
    (Test-Path -LiteralPath $rc) -and
    (Test-Path -LiteralPath $mt)
)
foreach ($path in @($vcvars, $cmake, $ninja, $python)) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Missing build dependency: $path"
    }
}

$command = [System.Collections.Generic.List[string]]@(
    "setlocal EnableExtensions EnableDelayedExpansion",
    "call `"$vcvars`" x64 >nul"
)
$cmakeOptions = [System.Collections.Generic.List[string]]@(
    "-DCMAKE_MAKE_PROGRAM=`"$ninja`"",
    "-DCMAKE_BUILD_TYPE=$Configuration"
)
if ($useLocalSdk) {
    $include = @(
        (Join-Path $sdkInclude "ucrt"),
        (Join-Path $sdkInclude "shared"),
        (Join-Path $sdkInclude "um"),
        (Join-Path $sdkInclude "winrt")
    ) -join ";"
    $lib = @(
        (Join-Path $sdkLib "ucrt\x64"),
        (Join-Path $sdkLib "um\x64")
    ) -join ";"
    $command.Add("set `"INCLUDE=$include;!INCLUDE!`"")
    $command.Add("set `"LIB=$lib;!LIB!`"")
    $command.Add("set `"PATH=$sdkBin;!PATH!`"")
    $cmakeOptions.Add("-DCMAKE_RC_COMPILER=`"$($rc.Replace('\', '/'))`"")
    $cmakeOptions.Add("-DCMAKE_MT=`"$($mt.Replace('\', '/'))`"")
}
$command.Add(
    "`"$cmake`" -S `"$source`" -B `"$build`" -G Ninja " +
    ($cmakeOptions -join " ")
)
$command.Add("`"$cmake`" --build `"$build`" --config $Configuration")
$commandLine = $command -join " && "

& cmd.exe /d /v:on /s /c $commandLine
if ($LASTEXITCODE -ne 0) {
    throw "Launcher build failed with exit code $LASTEXITCODE"
}

$launcher = Join-Path $build "Q4CNLauncher.exe"
if (-not (Test-Path -LiteralPath $launcher)) {
    throw "Launcher output was not found: $launcher"
}

$payloadEngine = Join-Path $distribution "engine"
$payloadSavedata = Join-Path $distribution "savedata"
$payloadRequired = @(
    (Join-Path $payloadEngine "Quake4.exe"),
    (Join-Path $payloadEngine "q4game.dll"),
    (Join-Path $payloadSavedata "q4base\strings\chinese_guis.lang")
)
foreach ($path in $payloadRequired) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Missing installer payload: $path"
    }
}

& $python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --uac-admin `
    --name "Quake4-Chinese-Installer" `
    --icon "$source\app.ico" `
    --distpath $package `
    --workpath $pyiWork `
    --specpath $pyiSpec `
    --paths (Join-Path $repository "src\tools") `
    --hidden-import build_dist_extras `
    --add-binary "$launcher;." `
    --add-data "$payloadEngine;payload\engine" `
    --add-data "$payloadSavedata;payload\savedata" `
    "$source\installer.py"

if ($LASTEXITCODE -ne 0) {
    throw "Installer build failed with exit code $LASTEXITCODE"
}

$installer = Join-Path $package "Quake4-Chinese-Installer.exe"
$destination = Join-Path $repository "dist\Quake4-Chinese-Installer.exe"
& $python (Join-Path $source "verify_bundle.py") `
    --installer $installer `
    --engine $payloadEngine `
    --savedata $payloadSavedata
if ($LASTEXITCODE -ne 0) {
    throw "Installer payload verification failed with exit code $LASTEXITCODE"
}
Copy-Item -LiteralPath $installer -Destination $destination -Force
Write-Output "Launcher: $launcher"
Write-Output "Installer: $destination"
