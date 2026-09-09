#Requires -Version 5.1

[CmdletBinding()]
param(
    [switch]$CheckOnly,
    [switch]$NoPause
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [Console]::OutputEncoding
$env:PYTHONUTF8 = "1"

$script:LauncherVersion = "1.0.0"
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
            Message = "Неполная готовая сборка: отсутствует release-manifest.json. Распакуйте ZIP заново."
            ExecutablePath = $null
        }
    }

    try {
        $Manifest = Get-Content -LiteralPath $ManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    }
    catch {
        return [PSCustomObject]@{
            Ok = $false
            Missing = @("release-manifest.json (повреждён)")
            Message = "Неполная готовая сборка: файл release-manifest.json повреждён. Распакуйте ZIP заново."
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
            $Missing.Add("$RelativePath (размер файла не совпадает)")
        }
    }

    $ExecutablePath = Join-Path $Root ([string]$Manifest.executable -replace '/', '\')
    if ($Missing.Count -gt 0) {
        return [PSCustomObject]@{
            Ok = $false
            Missing = @($Missing.ToArray())
            Message = "Неполная готовая сборка. Отсутствуют или повреждены файлы: $($Missing -join ', ')"
            ExecutablePath = $ExecutablePath
        }
    }

    return [PSCustomObject]@{
        Ok = $true
        Missing = @()
        Message = "Готовая сборка проверена."
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

    $DevelopmentCandidates = @(
        (Join-Path $Root "AutoNavy_WT.dist\AutoNavy_WT.exe"),
        (Join-Path $Root "start_prog.dist\start_prog.exe")
    )
    foreach ($ExecutablePath in $DevelopmentCandidates) {
        if (Test-Path -LiteralPath $ExecutablePath -PathType Leaf) {
            return [PSCustomObject]@{
                Mode = "StandaloneDevelopment"
                Root = Split-Path -Parent $ExecutablePath
                ManifestPath = $null
                ExecutablePath = $ExecutablePath
                PythonPath = $null
            }
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

    throw "Не найдена готовая программа AutoNavy_WT.exe или полный комплект исходного кода. Распакуйте архив полностью."
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
        & $FilePath @Arguments 2>&1 | ForEach-Object {
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

function Test-PendingRestart {
    $PendingPaths = @(
        "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending",
        "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired"
    )
    foreach ($Path in $PendingPaths) {
        if (Test-Path -LiteralPath $Path) {
            return $true
        }
    }
    try {
        $SessionManager = Get-ItemProperty -LiteralPath "HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager" -Name PendingFileRenameOperations -ErrorAction Stop
        if ($SessionManager.PendingFileRenameOperations) {
            return $true
        }
    }
    catch {
        # The value normally does not exist when no restart is pending.
    }
    return $false
}

function Find-VJoyConfigurationTool {
    $Candidates = New-Object System.Collections.Generic.List[string]
    foreach ($Base in @($env:ProgramFiles, ${env:ProgramFiles(x86)})) {
        if ($Base) {
            $Candidates.Add((Join-Path $Base "vJoy\x64\vJoyConfig.exe"))
            $Candidates.Add((Join-Path $Base "vJoy\x64\vJoyConf.exe"))
            $Candidates.Add((Join-Path $Base "vJoy\vJoyConfig.exe"))
            $Candidates.Add((Join-Path $Base "vJoy\vJoyConf.exe"))
        }
    }
    foreach ($Candidate in $Candidates) {
        if (Test-Path -LiteralPath $Candidate -PathType Leaf) {
            return $Candidate
        }
    }
    return $null
}

function Install-VJoyWithWinget {
    $Winget = Get-Command winget.exe -ErrorAction SilentlyContinue
    if (-not $Winget) {
        Write-Host "[ОШИБКА] Windows Package Manager (WinGet) не найден." -ForegroundColor Red
        Write-Host "Установите официальный vJoy 2.1.9.1 со страницы проекта и повторите запуск:"
        Write-Host "https://sourceforge.net/projects/vjoystick/files/Beta%202.x/2.1.9.1-160719/"
        Write-LauncherLog "vJoy installation unavailable: winget.exe not found."
        return $false
    }

    Write-Host "Проверка точного пакета vJoy в каталоге WinGet..."
    $ShowArguments = @(
        "show", "--exact", "--id", "ShaulEizikovich.vJoyDeviceDriver",
        "--source", "winget", "--accept-source-agreements"
    )
    $ShowCode = Invoke-LoggedProcess -FilePath $Winget.Source -Arguments $ShowArguments -HideConsoleOutput
    if ($ShowCode -ne 0) {
        Write-Host "[ОШИБКА] Точный пакет ShaulEizikovich.vJoyDeviceDriver не найден в WinGet." -ForegroundColor Red
        return $false
    }

    Write-Host "Будет запущен проверенный пакет vJoy Device Driver 2.1.9.1 через WinGet."
    Write-Host "Windows может показать запрос контроля учётных записей (UAC). Нажмите «Да», если хотите продолжить."
    $Answer = Read-Host "Установить vJoy сейчас? Введите ДА для продолжения"
    if ($Answer.Trim().ToUpperInvariant() -notin @("ДА", "Д", "YES", "Y")) {
        Write-Host "Установка vJoy отменена пользователем."
        return $false
    }

    $InstallArguments = @(
        "install", "--exact", "--id", "ShaulEizikovich.vJoyDeviceDriver",
        "--source", "winget", "--interactive",
        "--accept-package-agreements", "--accept-source-agreements"
    )
    Write-Host "Запуск установщика vJoy..."
    $InstallCode = Invoke-LoggedProcess -FilePath $Winget.Source -Arguments $InstallArguments -HideConsoleOutput
    if ($InstallCode -ne 0) {
        Write-Host "[ОШИБКА] Установщик vJoy завершился с кодом $InstallCode." -ForegroundColor Red
        return $false
    }
    Write-Host "Установщик vJoy завершён. Выполняется повторная проверка."
    return $true
}

function Configure-VJoyDevice {
    param([Parameter(Mandatory = $true)][string[]]$ProblemCodes)

    $Tool = Find-VJoyConfigurationTool
    if (-not $Tool) {
        Write-Host "[ОШИБКА] Утилита настройки vJoy не найдена." -ForegroundColor Red
        Write-Host "Откройте «Configure vJoy» из меню Пуск. Для устройства № 1 включите оси X, Y, Z, RY и не менее 8 кнопок."
        return $false
    }

    $IsConsoleTool = [System.IO.Path]::GetFileName($Tool) -ieq "vJoyConfig.exe"
    $NeedsReplacement = @($ProblemCodes | Where-Object { $_ -in @("vjoy_axis_missing", "vjoy_buttons_missing") }).Count -gt 0
    if ($IsConsoleTool) {
        if ($NeedsReplacement) {
            Write-Host "Текущее устройство vJoy № 1 настроено неверно. Автонастройка заменит его конфигурацию."
        }
        else {
            Write-Host "Будет создано устройство vJoy № 1 с осями X, Y, Z, RY и 8 кнопками."
        }
        Write-Host "Windows может показать запрос UAC."
        $Answer = Read-Host "Настроить устройство автоматически? Введите ДА для продолжения"
        if ($Answer.Trim().ToUpperInvariant() -in @("ДА", "Д", "YES", "Y")) {
            $Arguments = @("1")
            if ($NeedsReplacement) {
                $Arguments += "-f"
            }
            $Arguments += @("-a", "x", "y", "z", "ry", "-b", "8")
            try {
                $Process = Start-Process -FilePath $Tool -ArgumentList $Arguments -Verb RunAs -Wait -PassThru
                Write-LauncherLog "vJoyConfig exit code: $($Process.ExitCode)"
                if ($Process.ExitCode -eq 0) {
                    return $true
                }
                Write-Host "[ОШИБКА] Настройка vJoy завершилась с кодом $($Process.ExitCode)." -ForegroundColor Red
            }
            catch {
                Write-LauncherLog "vJoyConfig failure: $($_.Exception.ToString())"
                Write-Host "[ОШИБКА] Не удалось выполнить автоматическую настройку vJoy." -ForegroundColor Red
            }
        }
    }

    Write-Host "Сейчас откроется официальная утилита настройки vJoy."
    Write-Host "Выберите устройство № 1, включите оси X, Y, Z и RY, установите не менее 8 кнопок, затем нажмите Apply."
    try {
        Start-Process -FilePath $Tool | Out-Null
        Read-Host "После сохранения настроек закройте утилиту и нажмите Enter здесь"
        return $true
    }
    catch {
        Write-LauncherLog "Failed to open vJoy configuration UI: $($_.Exception.ToString())"
        Write-Host "[ОШИБКА] Не удалось открыть утилиту настройки vJoy: $Tool" -ForegroundColor Red
        return $false
    }
}

function Ensure-SourceEnvironment {
    param([Parameter(Mandatory = $true)][PSCustomObject]$Layout)

    $Python = $Layout.PythonPath
    $Checker = Join-Path $PSScriptRoot "check_environment.py"
    $NeedsInstall = -not (Test-Path -LiteralPath $Python -PathType Leaf)
    if (-not $NeedsInstall) {
        Write-Host "Проверка Python-среды исходного проекта..."
        $CheckCode = Invoke-LoggedProcess -FilePath $Python -Arguments @($Checker, "--installation-only")
        $NeedsInstall = $CheckCode -ne 0
    }
    if ($NeedsInstall) {
        Write-Host "Подготовка Python-среды исходного проекта..."
        Write-LauncherLog "Source environment installation/repair requested."
        & (Join-Path $PSScriptRoot "install.ps1")
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $Python -PathType Leaf)) {
            throw "Не удалось подготовить Python-среду исходного проекта."
        }
    }
    return $Python
}

function Invoke-RuntimePreflight {
    param(
        [Parameter(Mandatory = $true)][PSCustomObject]$Layout,
        [Parameter(Mandatory = $true)][string]$RuntimePath
    )

    $StatusPath = Join-Path (Split-Path -Parent $script:LauncherLogPath) ("preflight-{0}.json" -f [System.IO.Path]::GetFileNameWithoutExtension($script:LauncherLogPath))
    if (Test-Path -LiteralPath $StatusPath) {
        Remove-Item -LiteralPath $StatusPath -Force
    }
    $env:AUTONAVY_LOG_PATH = $script:LauncherLogPath
    if ($Layout.Mode -eq "Source") {
        $Arguments = @($Layout.ExecutablePath, "--preflight", "--status-file", $StatusPath)
    }
    else {
        $Arguments = @("--preflight", "--status-file", $StatusPath)
    }
    Push-Location -LiteralPath $Layout.Root
    try {
        $ExitCode = Invoke-LoggedProcess -FilePath $RuntimePath -Arguments $Arguments
    }
    finally {
        Pop-Location
    }

    $Status = $null
    if (Test-Path -LiteralPath $StatusPath -PathType Leaf) {
        try {
            $Status = Get-Content -LiteralPath $StatusPath -Raw -Encoding UTF8 | ConvertFrom-Json
        }
        catch {
            Write-LauncherLog "Invalid preflight status file: $($_.Exception.ToString())"
        }
    }
    return [PSCustomObject]@{ ExitCode = $ExitCode; Status = $Status; StatusPath = $StatusPath }
}

function Get-ProblemCodes {
    param($PreflightStatus)

    if ($null -eq $PreflightStatus -or $null -eq $PreflightStatus.results) {
        return @()
    }
    return @($PreflightStatus.results | Where-Object { -not $_.ok -and -not $_.warning } | ForEach-Object { [string]$_.code })
}

function Invoke-Launcher {
    $Root = Split-Path -Parent $PSScriptRoot
    Initialize-LauncherLog -Root $Root
    Write-Host "AutoNavy_WT — проверка готовности"
    Write-Host "Журнал: $script:LauncherLogPath"
    Write-LauncherLog "Root: $Root"
    Write-LauncherLog "CheckOnly: $CheckOnly"

    try {
        $Layout = Resolve-LaunchLayout -Root $Root
        Write-LauncherLog "Mode: $($Layout.Mode)"
        Write-LauncherLog "Executable: $($Layout.ExecutablePath)"
        if ($Layout.Mode -eq "Standalone") {
            $Validation = Test-ReleasePackage -Root $Layout.Root -ManifestPath $Layout.ManifestPath
            if (-not $Validation.Ok) {
                Write-Host "[ОШИБКА] $($Validation.Message)" -ForegroundColor Red
                Write-LauncherLog "Failure: $($Validation.Message)"
                return 3
            }
        }
        elseif ($Layout.Mode -eq "StandaloneDevelopment") {
            foreach ($Required in @("src", "path.json")) {
                if (-not (Test-Path -LiteralPath (Join-Path $Layout.Root $Required))) {
                    throw "Неполная готовая сборка: отсутствует $Required рядом с программой."
                }
            }
        }

        $ModeLabel = if ($Layout.Mode -eq "Source") { "исходный проект" } else { "готовая автономная сборка" }
        Write-Host "[OK] Выбран режим: $ModeLabel."
        if ($Layout.Mode -eq "Source") {
            $RuntimePath = Ensure-SourceEnvironment -Layout $Layout
        }
        else {
            $RuntimePath = $Layout.ExecutablePath
        }

        Write-Host "Безопасная диагностика: ввод с клавиатуры, мыши и vJoy не выполняется."
        $Preflight = Invoke-RuntimePreflight -Layout $Layout -RuntimePath $RuntimePath
        $ProblemCodes = Get-ProblemCodes -PreflightStatus $Preflight.Status

        if (-not $CheckOnly -and "vjoy_not_installed" -in $ProblemCodes) {
            if (Install-VJoyWithWinget) {
                $Preflight = Invoke-RuntimePreflight -Layout $Layout -RuntimePath $RuntimePath
                $ProblemCodes = Get-ProblemCodes -PreflightStatus $Preflight.Status
            }
        }

        $ConfigurationProblems = @($ProblemCodes | Where-Object { $_ -in @("vjoy_device_missing", "vjoy_axis_missing", "vjoy_buttons_missing") })
        if (-not $CheckOnly -and $ConfigurationProblems.Count -gt 0) {
            if (Configure-VJoyDevice -ProblemCodes $ProblemCodes) {
                $Preflight = Invoke-RuntimePreflight -Layout $Layout -RuntimePath $RuntimePath
                $ProblemCodes = Get-ProblemCodes -PreflightStatus $Preflight.Status
            }
        }

        if ($Preflight.ExitCode -ne 0) {
            if ("vjoy_not_installed" -in $ProblemCodes -and (Test-PendingRestart)) {
                Write-Host "После установки vJoy требуется перезапустить Windows, затем снова запустить этот файл." -ForegroundColor Yellow
            }
            Write-LauncherLog "Preflight failed with code $($Preflight.ExitCode); problems: $($ProblemCodes -join ', ')"
            return [int]$Preflight.ExitCode
        }

        if ($CheckOnly) {
            Write-Host "Диагностика завершена. Программа не запускалась и не отправляла ввод."
            return 0
        }

        Write-Host "Запуск AutoNavy_WT. Для остановки нажмите Ctrl+C."
        Push-Location -LiteralPath $Layout.Root
        try {
            if ($Layout.Mode -eq "Source") {
                $ApplicationCode = Invoke-LoggedProcess -FilePath $RuntimePath -Arguments @($Layout.ExecutablePath, "--run")
            }
            else {
                $ApplicationCode = Invoke-LoggedProcess -FilePath $RuntimePath -Arguments @("--run")
            }
        }
        finally {
            Pop-Location
        }
        if ($ApplicationCode -ne 0) {
            Write-Host "[ОШИБКА] AutoNavy_WT неожиданно завершился с кодом $ApplicationCode." -ForegroundColor Red
            Write-LauncherLog "Application failure exit code: $ApplicationCode"
            return [int]$ApplicationCode
        }
        Write-Host "AutoNavy_WT завершил работу."
        return 0
    }
    catch {
        Write-Host "[ОШИБКА] $($_.Exception.Message)" -ForegroundColor Red
        Write-LauncherLog "Failure: $($_.Exception.ToString())"
        return 3
    }
}

if ($MyInvocation.InvocationName -ne '.') {
    $ExitCode = Invoke-Launcher
    if ($ExitCode -ne 0) {
        Write-Host "Запуск остановлен. Подробности: $script:LauncherLogPath" -ForegroundColor Yellow
    }
    exit $ExitCode
}
