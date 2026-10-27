import subprocess
import os
import sys

src_nro = os.path.abspath("out/release/switch/mirrorsedge-nx/mirrorsedge.nro")
if not os.path.isfile(src_nro):
    sys.exit(f"File not found: {src_nro}")

nro_size = os.path.getsize(src_nro)
print(f"Source: {src_nro} ({nro_size / (1024*1024):.2f} MB)")

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

$switchDir = $sd.GetFolder.ParseName("switch")
if (-not $switchDir) {{
    Write-Host "switch directory not found."
    exit 1
}}

$meDir = $switchDir.GetFolder.ParseName("mirrorsedge-nx")
if (-not $meDir) {{
    Write-Host "mirrorsedge-nx directory not found."
    exit 1
}}

$targetFolder = $meDir.GetFolder
Write-Host "Found target folder:" $targetFolder.Title

$srcPath = "{src_nro.replace(chr(92), '/')}"
$srcDir = Split-Path $srcPath
$srcFile = Split-Path $srcPath -Leaf

$srcFolderItem = $shell.Namespace($srcDir).ParseName($srcFile)
if (-not $srcFolderItem) {{
    Write-Host "Failed to resolve source folder item."
    exit 1
}}

Write-Host "Copying $srcFile to Switch SD via DBI MTP..."
$targetFolder.CopyHere($srcFolderItem, 16) # 16 = Respond with Yes to All for any dialog box

# Wait for MTP transfer to complete
$done = $false
for ($i = 0; $i -lt 40; $i++) {{
    Start-Sleep -Seconds 1
    $destItem = $targetFolder.ParseName("mirrorsedge.nro")
    if ($destItem -and $destItem.Size -eq {nro_size}) {{
        Write-Host "Transfer complete! mirrorsedge.nro verified on Switch:" $destItem.Size "bytes"
        $done = $true
        break
    }} elseif ($destItem) {{
        Write-Host "In progress: $($destItem.Size) / {nro_size} bytes..."
    }}
}}

if (-not $done) {{
    $destItem = $targetFolder.ParseName("mirrorsedge.nro")
    Write-Host "Status after timeout:" ($destItem.Size)
}}
"""

res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True, text=True)
print(res.stdout)
if res.stderr:
    print("Stderr:", res.stderr)
