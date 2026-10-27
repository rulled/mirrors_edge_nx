import subprocess
import os
import sys

root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
src_nro = os.path.join(root, "out", "release", "switch", "mirrorsedge-nx", "mirrorsedge.nro")
src_toml = os.path.join(root, "app", "mirrorsedge.toml")

print(f"Source NRO:  {src_nro} ({os.path.getsize(src_nro) / (1024*1024):.2f} MB)")
print(f"Source TOML: {src_toml} ({os.path.getsize(src_toml)} bytes)")

ps_script = f"""
$shell = New-Object -ComObject Shell.Application
$computer = $shell.Namespace(17)
$switch = $computer.Items() | Where-Object {{ $_.Name -like "*Switch*" }}
if (-not $switch) {{
    Write-Host "Switch not found."
    exit 1
}}

$sd = $switch.GetFolder.Items() | Where-Object {{ $_.Name -like "*1: SD Card*" }}
if (-not $sd) {{
    Write-Host "1: SD Card not found."
    exit 1
}}

$meDir = $sd.GetFolder.ParseName("switch").GetFolder.ParseName("mirrorsedge-nx")
$targetFolder = $meDir.GetFolder
Write-Host "Target folder on Switch:" $targetFolder.Title

# Copy mirrorsedge.toml
$tomlPath = "{src_toml.replace('/', chr(92))}"
$tomlDir = Split-Path -Parent $tomlPath
$tomlFile = Split-Path $tomlPath -Leaf
$tomlItem = $shell.Namespace($tomlDir).ParseName($tomlFile)
$targetFolder.CopyHere($tomlItem, 16)
Write-Host "Copied mirrorsedge.toml"

# Copy mirrorsedge.nro
$nroPath = "{src_nro.replace('/', chr(92))}"
$nroDir = Split-Path -Parent $nroPath
$nroFile = Split-Path $nroPath -Leaf
$nroItem = $shell.Namespace($nroDir).ParseName($nroFile)
$targetFolder.CopyHere($nroItem, 16)
Write-Host "Dispatched mirrorsedge.nro copy"
Start-Sleep -Seconds 3

Write-Host "Verifying files in switch/mirrorsedge-nx on Switch:"
foreach ($item in $targetFolder.Items()) {{
    $detail = $targetFolder.GetDetailsOf($item, 1)
    Write-Host "  " $item.Name ":" $detail
}}
"""

res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True, text=True)
print(res.stdout)
if res.stderr:
    print("Stderr:", res.stderr)
