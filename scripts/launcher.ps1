#Requires -Version 5.1

# Deliberately not an advanced script: unknown CLI flags belong to Python.
param()
$LaunchArguments = @($args)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [Console]::OutputEncoding
$env:PYTHONUTF8 = "1"

$script:LauncherVersion = "2.0.0"
$script:LauncherLogPath = $null

function Resolve-FullPath {
    param([Parameter(Mandatory = $true)][string]$Path)

    return [System.IO.Path]::GetFullPath($Path)
}

function Test-ReleasePackage {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$ManifestPath
    )

    $Root = Resolve-FullPath $Root
    if (-not (Test-Path -LiteralPath $ManifestPath -PathType Leaf)) {
        return [PSCustomObject]@{
            Ok = $false
            Missing = @("release-manifest.json")
            Message = "Incomplete release: release-manifest.json missing. Extract the complete ZIP again."
            ExecutablePath = $null
        }
    }

    try {
        $Manifest = Get-Content -LiteralPath $ManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
        $Properties = @($Manifest.PSObject.Properties.Name)
        if ('schema_version' -notin $Properties -or 'launcher_version' -notin $Properties -or
            -not ($Manifest.schema_version -is [int] -or $Manifest.schema_version -is [long]) -or
            $Manifest.schema_version -ne 1 -or $Manifest.launcher_version -isnot [string] -or
            $Manifest.launcher_version -cne $script:LauncherVersion) {
            return [PSCustomObject]@{
                Ok = $false
                Missing = @('release-manifest.json (incompatible CLI contract)')
                Message = "Incompatible package: requires schema_version 1 and launcher_version $script:LauncherVersion. Extract a complete v2 release."
                ExecutablePath = $null
            }
        }
        $Prefix = $Root.TrimEnd('\') + '\'
        foreach ($Relative in @([string]$Manifest.executable) + @($Manifest.required_files | ForEach-Object { [string]$_.path })) {
            $Candidate = Resolve-FullPath (Join-Path $Root $Relative)
            if (-not $Relative -or [IO.Path]::IsPathRooted($Relative) -or -not $Candidate.StartsWith($Prefix, [StringComparison]::OrdinalIgnoreCase)) {
                throw 'Manifest paths must stay inside the package.'
            }
        }
        if ([string]$Manifest.executable -notin @($Manifest.required_files | ForEach-Object { [string]$_.path })) {
            throw 'Manifest must declare the executable as a required file.'
        }
    }
    catch {
        return [PSCustomObject]@{
            Ok = $false
            Missing = @("release-manifest.json (invalid)")
            Message = "Incomplete release: release-manifest.json invalid. Extract the complete ZIP again."
            ExecutablePath = $null
        }
    }

    $Missing = New-Object System.Collections.Generic.List[string]
    foreach ($Entry in @($Manifest.required_files)) {
        $RelativePath = [string]$Entry.path
        $FullPath = Join-Path $Root ($RelativePath -replace '/', '\')
        if (-not (Test-Path -LiteralPath $FullPath -PathType Leaf)) {
            $Missing.Add($RelativePath)
            continue
        }
        if ($null -ne $Entry.size -and (Get-Item -LiteralPath $FullPath).Length -ne [long]$Entry.size) {
            $Missing.Add("$RelativePath (file size mismatch)")
        }
    }

    $ExecutablePath = Join-Path $Root ([string]$Manifest.executable -replace '/', '\')
    if ($Missing.Count -gt 0) {
        return [PSCustomObject]@{
            Ok = $false
            Missing = @($Missing.ToArray())
            Message = "Incomplete release. Missing or damaged files: $($Missing -join ', ')"
            ExecutablePath = $ExecutablePath
        }
    }

    return [PSCustomObject]@{
        Ok = $true
        Missing = @()
        Message = "Release package validated."
        ExecutablePath = $ExecutablePath
    }
}

function Resolve-LaunchLayout {
    [CmdletBinding()]
    param([Parameter(Mandatory = $true)][string]$Root)

    $Root = Resolve-FullPath $Root
    $ManifestPath = Join-Path $Root "release-manifest.json"
    if (Test-Path -LiteralPath $ManifestPath -PathType Leaf) {
        $Manifest = Get-Content -LiteralPath $ManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
        return [PSCustomObject]@{
            Mode = "Standalone"
            Root = $Root
            ManifestPath = $ManifestPath
            ExecutablePath = Join-Path $Root ([string]$Manifest.executable -replace '/', '\')
            PythonPath = $null
        }
    }

    $SourceEntry = Join-Path $Root "autonavy.py"
    $SourceInstaller = Join-Path $Root "scripts\install.ps1"
    if ((Test-Path -LiteralPath $SourceEntry -PathType Leaf) -and
        (Test-Path -LiteralPath $SourceInstaller -PathType Leaf) -and
        (Test-Path -LiteralPath (Join-Path $Root "requirements.txt") -PathType Leaf)) {
        return [PSCustomObject]@{
            Mode = "Source"
            Root = $Root
            ManifestPath = $null
            ExecutablePath = $SourceEntry
            PythonPath = Join-Path $Root ".venv\Scripts\python.exe"
        }
    }

    throw "No standalone executable or complete source checkout found. Extract the entire archive."
}

function Initialize-LauncherLog {
    param([Parameter(Mandatory = $true)][string]$Root)

    $LogDirectory = Join-Path $Root "logs"
    try {
        [System.IO.Directory]::CreateDirectory($LogDirectory) | Out-Null
    }
    catch {
        $LogDirectory = Join-Path $env:TEMP "AutoNavy_WT-logs"
        [System.IO.Directory]::CreateDirectory($LogDirectory) | Out-Null
    }
    $Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $script:LauncherLogPath = Join-Path $LogDirectory "launcher-$Timestamp.log"
    [System.IO.File]::WriteAllText(
        $script:LauncherLogPath,
        "AutoNavy_WT launcher $script:LauncherVersion`r`n",
        [System.Text.UTF8Encoding]::new($true)
    )
}

function Write-LauncherLog {
    param([Parameter(Mandatory = $true)][string]$Message)

    if ($script:LauncherLogPath) {
        $Line = "[{0}] {1}`r`n" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff"), $Message
        [System.IO.File]::AppendAllText($script:LauncherLogPath, $Line, [System.Text.UTF8Encoding]::new($true))
    }
}

function Invoke-LoggedProcess {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [string[]]$Arguments = @(),
        [switch]$HideConsoleOutput
    )

    Write-LauncherLog "Process: $FilePath $($Arguments -join ' ')"
    $global:LASTEXITCODE = 0
    $PreviousErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $NativeArguments = @($Arguments | ForEach-Object {
            '"' + ([regex]::Replace([regex]::Replace($_, '(\\*)"', '$1$1\"'), '(\\+)$', '$1$1')) + '"'
        })
        if ((Get-Variable PSNativeCommandArgumentPassing -ErrorAction SilentlyContinue) -and $PSNativeCommandArgumentPassing -ne 'Legacy') {
            $NativeArguments = $Arguments
        }
        & $FilePath @NativeArguments 2>&1 | ForEach-Object {
            $Line = [string]$_
            Write-LauncherLog "Process output: $Line"
            if (-not $HideConsoleOutput) {
                Write-Host $Line
            }
        }
        $Code = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $PreviousErrorActionPreference
    }
    if ($null -eq $Code) {
        $Code = 0
    }
    Write-LauncherLog "Process exit code: $Code"
    return [int]$Code
}

function Invoke-Launcher {
    param([string[]]$CliArguments = @())
    $Root = Split-Path -Parent $PSScriptRoot
    Initialize-LauncherLog -Root $Root
    try {
        $Layout = Resolve-LaunchLayout -Root $Root
        if ($Layout.Mode -eq "Standalone") {
            $Validation = Test-ReleasePackage -Root $Layout.Root -ManifestPath $Layout.ManifestPath
            if (-not $Validation.Ok) { throw $Validation.Message }
        }
        $Forward = @()
        $CheckOnly = $false
        foreach ($Argument in $CliArguments) {
            if ($Argument -ieq '-CheckOnly') { $CheckOnly = $true }
            elseif ($Argument -ine '-NoPause') { $Forward += $Argument }
        }
        if ($CheckOnly -and '--check-config' -notin $Forward) { $Forward = @('--check-config') + $Forward }
        if ($Forward.Count -eq 0) {
            Write-Host 'Safe default: checking configuration. Use --dry-run --capture dxcam/obs for manual capture; physical input requires --enable-input.'
            $Forward = @('--check-config')
        }
        $RuntimePath = $Layout.ExecutablePath
        if ($Layout.Mode -eq "Source") {
            $RuntimePath = $Layout.PythonPath
            if (-not (Test-Path -LiteralPath $RuntimePath -PathType Leaf)) {
                throw 'Local Python environment missing. Run scripts/install.ps1 -Mode Core (offline tools) or -Mode Runtime (manual live use) explicitly.'
            }
            $Forward = @($Layout.ExecutablePath) + $Forward
        }
        return Invoke-LoggedProcess -FilePath $RuntimePath -Arguments $Forward
    }
    catch {
        Write-Host "[ERROR] $($_.Exception.Message)"
        Write-LauncherLog "Failure: $($_.Exception.ToString())"
        return 3
    }
}

if ($MyInvocation.InvocationName -ne '.') {
    exit (Invoke-Launcher -CliArguments $LaunchArguments)
}
