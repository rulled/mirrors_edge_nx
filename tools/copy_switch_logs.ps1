$shell = New-Object -ComObject Shell.Application
$folder = $shell.Namespace(17)
$switch = $null
foreach ($item in $folder.Items()) {
    if ($item.Name -match "Switch") {
        $switch = $item.GetFolder
        break
    }
}

$sdCard = $null
foreach ($sub in $switch.Items()) {
    if ($sub.Name -match "1: SD Card") {
        $sdCard = $sub.GetFolder
        break
    }
}

function Get-SubFolder($parent, $name) {
    foreach ($item in $parent.Items()) {
        if ($item.Name -eq $name) {
            return $item.GetFolder
        }
    }
    return $null
}

$destDir = "E:\MirrorsEdge_NX\out\switch_logs"
if (-not (Test-Path $destDir)) {
    New-Item -ItemType Directory -Path $destDir | Out-Null
}
$destFolder = $shell.Namespace($destDir)

# Copy latest crash reports
$atmos = Get-SubFolder $sdCard "atmosphere"
if ($atmos) {
    $crashReports = Get-SubFolder $atmos "crash_reports"
    if ($crashReports) {
        # find the ones starting with 0179251
        foreach ($cr in $crashReports.Items()) {
            if ($cr.Name -like "*0179251*") {
                Write-Output "Copying crash report $($cr.Name)..."
                $destFolder.CopyHere($cr, 16) # 16 = respond "Yes to All"
            }
        }
    }
}

# Copy switch/mirrorsedge-nx/logs
$switchDir = Get-SubFolder $sdCard "switch"
if ($switchDir) {
    $meDir = Get-SubFolder $switchDir "mirrorsedge-nx"
    if ($meDir) {
        $logsDir = Get-SubFolder $meDir "logs"
        if ($logsDir) {
            Write-Output "=== Found logs in mirrorsedge-nx/logs ==="
            foreach ($lf in $logsDir.Items()) {
                Write-Output "Copying log $($lf.Name)..."
                $destFolder.CopyHere($lf, 16)
            }
        }
    }
}
Write-Output "Done copying logs."
