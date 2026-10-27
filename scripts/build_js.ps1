# 构建 jslib（TS → pylightcharts/js/）
#
# Windows PowerShell 5.1 **不支持** `cd jslib && npm run build`（`&&` 不是分隔符 ✗），
# 用这个脚本，或者把两条命令分开写：
#
#   cd jslib
#   npm run build
#
# 用法：  powershell -ExecutionPolicy Bypass -File scripts/build_js.ps1
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location (Join-Path $root 'jslib')
Write-Host "[build] $((Get-Location).Path)" -ForegroundColor Cyan
& npm run build
if ($LASTEXITCODE -ne 0) { throw "npm run build 失败（exit $LASTEXITCODE）" }
Write-Host '[build] 完成 → pylightcharts/js/' -ForegroundColor Green
