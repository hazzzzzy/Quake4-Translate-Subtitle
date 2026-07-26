param(
    [string]$Version = "dev",
    [string]$OutputDirectory = "artifacts"
)

$ErrorActionPreference = "Stop"
$repository = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$distribution = Join-Path $repository "dist"
if (-not [System.IO.Path]::IsPathRooted($OutputDirectory)) {
    $OutputDirectory = Join-Path $repository $OutputDirectory
}

$required = @(
    "Quake4-Chinese-Installer.exe",
    "engine\Quake4.exe",
    "engine\q4game.dll",
    "savedata\q4base\strings\chinese_guis.lang",
    "savedata\q4base\strings\english_lipsadd.lang",
    "savedata\q4base\guis\subtitles.gui"
)
foreach ($relativePath in $required) {
    $path = Join-Path $distribution $relativePath
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "分发目录缺少必需文件：$relativePath"
    }
}

$forbidden = Get-ChildItem -LiteralPath $distribution -Recurse -Force -File | Where-Object {
    $relativePath = $_.FullName.Substring($distribution.Length + 1).Replace("\", "/")
    $relativePath -match "^savedata/q4base/fonts/chinese/strogg_" -or
    $relativePath -match "^savedata/q4base/fonts/chinese/r_strogg_.*\.tga$" -or
    $relativePath -match "^savedata/q4base/guis/(hud|mainmenu|wristcomm|hud_strogg|wristcomm_strogg)\.gui$" -or
    $relativePath -match "^savedata/q4base/guis/(maps|common|monitors|movers)/" -or
    $relativePath -match "(^|/)(savegames|screenshots)/" -or
    $relativePath -match "(^|/)qconsole.*\.log$" -or
    $relativePath -match "(^|/)Quake4Config\.cfg$" -or
    $relativePath -match "(^|/)(config\.spec|quake4key|xpkey|noninteractive-before|\.console_history\.dat)$" -or
    $relativePath -match "^savedata/q4base/zzz_vo_chinese_alias\.pk4$"
}
if ($forbidden) {
    $details = ($forbidden | ForEach-Object {
        $_.FullName.Substring($distribution.Length + 1)
    }) -join "`n"
    throw "分发目录含有运行时或正版提取产物：`n$details"
}

$safeVersion = [regex]::Replace($Version, "[^0-9A-Za-z._-]", "-")
$packageName = "Quake4-Translate-Subtitle-$safeVersion"
$installerName = "Quake4-Chinese-Installer-$safeVersion.exe"
$stageParent = Join-Path $repository "tmp\package-release"
$stage = Join-Path $stageParent $packageName
$zip = Join-Path $OutputDirectory "$packageName.zip"
$installer = Join-Path $OutputDirectory $installerName
$checksums = Join-Path $OutputDirectory "SHA256SUMS.txt"

if (Test-Path -LiteralPath $stageParent) {
    Remove-Item -LiteralPath $stageParent -Recurse -Force
}
if (Test-Path -LiteralPath $zip) {
    Remove-Item -LiteralPath $zip -Force
}
if (Test-Path -LiteralPath $installer) {
    Remove-Item -LiteralPath $installer -Force
}
New-Item -ItemType Directory -Path $stage -Force | Out-Null
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null

Get-ChildItem -LiteralPath $distribution -Force | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination $stage -Recurse -Force
}
foreach ($name in @("LICENSE", "LICENSE-FONTS.txt", "CHANGELOG.md")) {
    Copy-Item -LiteralPath (Join-Path $repository $name) -Destination $stage -Force
}

Copy-Item -LiteralPath (Join-Path $distribution "Quake4-Chinese-Installer.exe") `
    -Destination $installer -Force
Compress-Archive -LiteralPath $stage -DestinationPath $zip -CompressionLevel Optimal
$checksumLines = foreach ($path in @($installer, $zip)) {
    $hash = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
    "$hash  $([System.IO.Path]::GetFileName($path))"
}
$checksumLines | Set-Content -LiteralPath $checksums -Encoding ASCII

Write-Output "Installer: $installer"
Write-Output "Package: $zip"
Write-Output "Checksums: $checksums"
$checksumLines | ForEach-Object { Write-Output "SHA256: $_" }
