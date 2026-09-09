#Requires -Version 5.1

[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [Console]::OutputEncoding
$env:PYTHONUTF8 = "1"

$RepositoryRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $RepositoryRoot

if ($env:OS -ne "Windows_NT") {
    Write-Error "AutoNavy_WT поддерживает только Windows."
}

function Find-Python311 {
    $Candidates = New-Object System.Collections.Generic.List[string]
    if (Get-Command py.exe -ErrorAction SilentlyContinue) {
        $Executable = & py.exe -3.11 -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $Executable) {
            $Candidates.Add($Executable.Trim())
        }
    }

    if (Get-Command python.exe -ErrorAction SilentlyContinue) {
        $Executable = & python.exe -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $Executable) {
            $Candidates.Add($Executable.Trim())
        }
    }

    foreach ($Candidate in $Candidates | Select-Object -Unique) {
        & $Candidate -c "import struct, sys; raise SystemExit(0 if sys.version_info[:2] == (3, 11) and struct.calcsize('P') == 8 else 1)"
        if ($LASTEXITCODE -eq 0) {
            return $Candidate
        }
    }

    throw "Не найден 64-битный CPython 3.11. Он нужен только для запуска из исходников. Установите Python 3.11 x64 с python.org и повторите запуск."
}

$Python = Find-Python311

$VirtualEnvironment = Join-Path $RepositoryRoot ".venv"
$VenvPython = Join-Path $VirtualEnvironment "Scripts\python.exe"
if (Test-Path -LiteralPath $VenvPython -PathType Leaf) {
    & $VenvPython -c "import struct, sys; raise SystemExit(0 if sys.version_info[:2] == (3, 11) and struct.calcsize('P') == 8 else 1)"
    if ($LASTEXITCODE -ne 0) {
        $ExpectedVenv = [System.IO.Path]::GetFullPath((Join-Path $RepositoryRoot ".venv"))
        $ActualVenv = [System.IO.Path]::GetFullPath($VirtualEnvironment)
        if ($ExpectedVenv -ne $ActualVenv -or $ActualVenv -eq [System.IO.Path]::GetPathRoot($ActualVenv)) {
            throw "Небезопасный путь виртуального окружения: $ActualVenv"
        }
        Write-Host "Повреждённое или несовместимое окружение .venv будет пересоздано."
        Remove-Item -LiteralPath $ActualVenv -Recurse -Force
    }
}
if (-not (Test-Path -LiteralPath $VenvPython -PathType Leaf)) {
    Write-Host "Создание виртуального окружения .venv..."
    & $Python -m venv $VirtualEnvironment
    if ($LASTEXITCODE -ne 0) {
        throw "Не удалось создать виртуальное окружение."
    }
}

Write-Host "Установка зависимостей..."
& $VenvPython -m pip install --disable-pip-version-check -r (Join-Path $RepositoryRoot "requirements.txt")
if ($LASTEXITCODE -ne 0) {
    throw "Установка зависимостей завершилась с ошибкой."
}

$VJoyRuntimeSource = Join-Path $RepositoryRoot "third_party\vjoy\2.1.9.1\x64\vJoyInterface.dll"
$VJoyRuntimeTarget = Join-Path $VirtualEnvironment "Lib\site-packages\pyvjoy\utils\x64\vJoyInterface.dll"
if (-not (Test-Path -LiteralPath $VJoyRuntimeSource -PathType Leaf)) {
    throw "Отсутствует библиотека управления vJoy 2.1.9.1. Получите полный комплект исходного кода."
}
Copy-Item -LiteralPath $VJoyRuntimeSource -Destination $VJoyRuntimeTarget -Force

Write-Host "Проверка установленной среды..."
& $VenvPython (Join-Path $PSScriptRoot "check_environment.py") --installation-only
if ($LASTEXITCODE -ne 0) {
    throw "Среда установлена не полностью. Исправьте ошибки, показанные выше."
}

Write-Host "Установка Python-зависимостей завершена."
Write-Host "Продолжайте через файл ЗАПУСТИТЬ.bat в корне проекта."
