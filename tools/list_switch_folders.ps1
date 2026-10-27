$shell = New-Object -ComObject Shell.Application
$folder = $shell.Namespace(17)
$switch = $null
foreach ($item in $folder.Items()) {
    if ($item.Name -match "Switch") {
        $switch = $item.GetFolder
        break
    }
}

if (-not $switch) {
    Write-Error "Switch not found"
    exit 1
}

Write-Output "Found Switch:"
foreach ($sub in $switch.Items()) {
    Write-Output "  $($sub.Name)"
}
