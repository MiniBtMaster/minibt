# 把仓库里的 vscode-minibt/ 链接成"已安装扩展"，改完代码只要 Reload Window，
# 不必每次重新 `vsce package` + 安装 .vsix。
#
#   powershell -ExecutionPolicy Bypass -File link-dev.ps1
#   powershell -ExecutionPolicy Bypass -File link-dev.ps1 -Remove
#
# 原理：在 VS Code 扩展目录里建一个**目录联接（junction）**，名字按 VS Code 的
# 约定 `<publisher>.<name>-<version>`（从 package.json 读，别手抄）。
# 删除联接不会动源目录（rmdir 只删链接）。
param(
    [string]$Source = $PSScriptRoot,
    [string]$Extensions = "$env:USERPROFILE\.vscode\extensions",
    [switch]$Remove
)

$ErrorActionPreference = 'Stop'

$manifestPath = Join-Path $Source 'package.json'
if (-not (Test-Path $manifestPath)) {
    throw "找不到 $manifestPath（请在 vscode-minibt/ 目录里运行）"
}
$manifest = Get-Content $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
foreach ($field in 'publisher', 'name', 'version') {
    if (-not $manifest.$field) { throw "package.json 缺少 $field" }
}

$folder = '{0}.{1}-{2}' -f $manifest.publisher.ToLower(), $manifest.name.ToLower(), $manifest.version
$target = Join-Path $Extensions $folder

if ($Remove) {
    if (Test-Path $target) {
        cmd /c rmdir "$target"      # junction：只删链接，不动源目录
        Write-Host "已移除联接：$target"
    } else {
        Write-Host "没有找到：$target"
    }
    Write-Host "在 VS Code 里执行 “Developer: Reload Window” 生效。"
    exit 0
}

if (-not (Test-Path $Extensions)) { New-Item -ItemType Directory -Path $Extensions | Out-Null }

if (Test-Path $target) {
    $item = Get-Item $target -Force
    $isLink = $item.Attributes -band [IO.FileAttributes]::ReparsePoint
    if ($isLink) {
        cmd /c rmdir "$target" | Out-Null
    } else {
        # 真目录（比如从 .vsix 装的那份）绝不擅自删，先让用户自己处理
        throw "$target 是真实目录（可能是 .vsix 装的）。请先在扩展面板卸载它，或手动删除后再运行本脚本。"
    }
}

cmd /c mklink /J "$target" "$Source" | Out-Null
if (-not (Test-Path (Join-Path $target 'extension.js'))) {
    throw "联接创建失败：$target"
}

# 同名的旧版本目录一并提示（VS Code 会优先用高版本，容易看混）
Get-ChildItem $Extensions -Directory -Filter "$($manifest.publisher.ToLower()).$($manifest.name.ToLower())-*" |
    Where-Object { $_.Name -ne $folder } |
    ForEach-Object { Write-Host "提示：还留着旧版本 $($_.Name)，建议在扩展面板卸载它。" }

Write-Host "已联接：$target"
Write-Host "  →  $Source"
Write-Host "现在在 VS Code 里执行 “Developer: Reload Window”（Ctrl+Shift+P）即可测试；"
Write-Host "以后改 extension.js / runner/*.py 只要 Reload Window，不用重新打包。"
