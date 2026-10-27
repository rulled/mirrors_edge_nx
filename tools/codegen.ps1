# Translates Mirror's Edge (default.xex) to C++ on Windows using ReXGlue.
# Usage: powershell -ExecutionPolicy Bypass -File tools\codegen.ps1 [-Rexglue <path>]
param([string]$Rexglue = '')
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$app = Join-Path $root 'app'

if (-not $Rexglue) {
    $Rexglue = Get-ChildItem (Join-Path $root 'sdk\out') -Recurse -Include rexglue.exe -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1 -ExpandProperty FullName
}
if (-not $Rexglue -or -not (Test-Path $Rexglue)) {
    # Check host build path
    $candidate = Join-Path $root 'sdk\out\host\rexglue.exe'
    if (Test-Path $candidate) { $Rexglue = $candidate }
    else { throw 'rexglue.exe not found; build it first (tools\win\host_build.ps1 or build_host.sh)' }
}
if (-not (Test-Path (Join-Path $root 'assets\game_root\default.xex'))) {
    throw 'assets\game_root\default.xex not found; run python tools\extract_iso.py <path_to_iso_or_folder>'
}

New-Item -ItemType Directory -Force (Join-Path $root 'out') | Out-Null
$log = Join-Path $root 'out\codegen.log'
Write-Host "== codegen with $Rexglue"
Push-Location $app
try {
    $env:REX_MAX_JUMP_TABLE_ENTRIES = '1024'
    $env:REXGLUE_DUMP_IMAGE = (Join-Path $root 'out\default_image.bin')
    & $env:ComSpec /c "`"$Rexglue`" codegen mirrorsedge_manifest.toml > `"$log`" 2>&1"
    $code = $LASTEXITCODE
} finally { Pop-Location }

Get-Content $log -Tail 15
if ($code -ne 0) { throw "codegen failed (exit $code), see out\codegen.log" }
Write-Host "done: $app\generated"
