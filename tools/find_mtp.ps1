$shell = New-Object -ComObject Shell.Application
$folder = $shell.Namespace(17)
foreach ($item in $folder.Items()) {
    Write-Output "Item: $($item.Name) | Type: $($item.Type) | Path: $($item.Path)"
}
