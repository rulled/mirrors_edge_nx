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

# Check atmosphere/crash_reports
$atmos = Get-SubFolder $sdCard "atmosphere"
if ($atmos) {
    Write-Output "=== Atmosphere folders ==="
    foreach ($sub in $atmos.Items()) {
        Write-Output "  $($sub.Name)"
    }
    
    $crashReports = Get-SubFolder $atmos "crash_reports"
    if ($crashReports) {
        Write-Output "=== Crash Reports ==="
        foreach ($cr in $crashReports.Items()) {
            Write-Output "  $($cr.Name) - $($cr.Size)"
        }
    }
    $fatalReports = Get-SubFolder $atmos "fatal_reports"
    if ($fatalReports) {
        Write-Output "=== Fatal Reports ==="
        foreach ($fr in $fatalReports.Items()) {
            Write-Output "  $($fr.Name) - $($fr.Size)"
        }
    }
}

# Check switch/mirrorsedge-nx
$switchDir = Get-SubFolder $sdCard "switch"
if ($switchDir) {
    $meDir = Get-SubFolder $switchDir "mirrorsedge-nx"
    if ($meDir) {
        Write-Output "=== switch/mirrorsedge-nx files ==="
        foreach ($f in $meDir.Items()) {
            Write-Output "  $($f.Name) - $($f.Size)"
        }
    }
}
