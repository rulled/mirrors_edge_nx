# inspect_mtp.py
import subprocess

ps_script = """
$shell = New-Object -ComObject Shell.Application
$computer = $shell.Namespace(17)
$switch = $computer.Items() | Where-Object { $_.Name -like "*Switch*" }
if ($switch) {
    Write-Host "Found device:" $switch.Name
    $devFolder = $switch.GetFolder
    foreach ($storage in $devFolder.Items()) {
        Write-Host " Storage:" $storage.Name
        if ($storage.Name -like "*microSD*") {
            $sdFolder = $storage.GetFolder
            foreach ($item in $sdFolder.Items()) {
                if ($item.Name -in @("switch", "atmosphere", "Nintendo")) {
                    Write-Host "   Folder:" $item.Name
                }
            }
            
            # Check atmosphere/crash_reports
            $atm = $sdFolder.ParseName("atmosphere")
            if ($atm) {
                $atmFolder = $atm.GetFolder
                $cr = $atmFolder.ParseName("crash_reports")
                if ($cr) {
                    Write-Host "   === crash_reports ==="
                    foreach ($c in $cr.GetFolder.Items()) {
                        Write-Host "     Crash:" $c.Name
                    }
                }
                $erpt = $atmFolder.ParseName("erpt_reports")
                if ($erpt) {
                    Write-Host "   === erpt_reports ==="
                    foreach ($e in $erpt.GetFolder.Items()) {
                        Write-Host "     Erpt:" $e.Name
                    }
                }
            }
            
            # Check switch/mirrorsedge-nx
            $sw = $sdFolder.ParseName("switch")
            if ($sw) {
                $me = $sw.GetFolder.ParseName("mirrorsedge-nx")
                if ($me) {
                    Write-Host "   === switch/mirrorsedge-nx ==="
                    foreach ($m in $me.GetFolder.Items()) {
                        Write-Host "     File:" $m.Name
                    }
                }
            }
        }
    }
} else {
    Write-Host "Switch not found."
}
"""

res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True, text=True)
print(res.stdout)
if res.stderr:
    print("Stderr:", res.stderr)
