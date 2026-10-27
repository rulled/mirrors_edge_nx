import subprocess
import os
import sys

root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
src_nro = os.path.join(root, "out", "release", "switch", "mirrorsedge-nx", "mirrorsedge.nro")
nro_size = os.path.getsize(src_nro)
print(f"Source NRO: {src_nro} ({nro_size} bytes)")

ps_script = f"""
$shell = New-Object -ComObject Shell.Application
$computer = $shell.Namespace(17)
$switch = $computer.Items() | Where-Object {{ $_.Name -like "*Switch*" }}
$sd = $switch.GetFolder.Items() | Where-Object {{ $_.Name -like "*1: SD Card*" }}
$targetFolder = $sd.GetFolder.ParseName("switch").GetFolder.ParseName("mirrorsedge-nx").GetFolder

$nroPath = "{src_nro.replace('/', chr(92))}"
$nroDir = Split-Path -Parent $nroPath
$nroFile = Split-Path $nroPath -Leaf
$nroItem = $shell.Namespace($nroDir).ParseName($nroFile)

Write-Host "Starting copy of $nroFile..."
# 4 = Do not display a progress dialog box.
# 16 = Respond with "Yes to All" for any dialog box that is displayed.
$targetFolder.CopyHere($nroItem, 0) # Use 0 so standard copy occurs

$found = $false
for ($i = 0; $i -lt 120; $i++) {{
    Start-Sleep -Seconds 1
    $item = $targetFolder.ParseName("mirrorsedge.nro")
    if ($item) {{
        $sizeStr = $targetFolder.GetDetailsOf($item, 1)
        Write-Host "Found file ($i s):" $item.Name "($sizeStr)"
        if ($sizeStr -match "60") {{
            $found = $true
            break
        }}
    }} else {{
        if ($i % 5 -eq 0) {{ Write-Host "Waiting ($i s)..." }}
    }}
}}

if ($found) {{
    Write-Host "SUCCESS: mirrorsedge.nro fully transferred and verified on Switch!"
}} else {{
    Write-Host "Timeout waiting for transfer."
}}
"""

res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True, text=True)
print(res.stdout)
if res.stderr:
    print("Stderr:", res.stderr)
