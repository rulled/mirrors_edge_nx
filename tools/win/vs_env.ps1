# Sets up the Visual Studio 2022 Developer environment in PowerShell.
$vswhere = "C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe"
if (-not (Test-Path $vswhere)) {
    throw "vswhere.exe not found at $vswhere"
}

$installPath = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if (-not $installPath) {
    throw "Visual Studio C++ build tools not found"
}

$vcvars = Join-Path $installPath "VC\Auxiliary\Build\vcvars64.bat"
if (-not (Test-Path $vcvars)) {
    throw "vcvars64.bat not found at $vcvars"
}

# Import environment variables from vcvars64.bat
cmd /c "`"$vcvars`" > nul && set" | ForEach-Object {
    if ($_ -match "^(.*?)=(.*)$") {
        Set-Item -Force -Path "env:\$($matches[1])" -Value $matches[2]
    }
}

Write-Host "Visual Studio 2022 Build Tools environment initialized for x64."
Write-Host "MSVC Compiler: $(Get-Command cl.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source)"
Write-Host "CMake:         $(Get-Command cmake.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source)"
Write-Host "Ninja:         $(Get-Command ninja.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source)"
