param(
    [ValidateSet("dev", "dev-windows", "build", "test", "backend", "frontend", "status")]
    [string]$Mode = "dev"
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"

function Clear-LocalProxy {
    $proxyVars = @(
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy"
    )
    foreach ($name in $proxyVars) {
        Remove-Item "Env:$name" -ErrorAction SilentlyContinue
    }
}

function Start-VisiblePowerShell {
    param(
        [string]$Title,
        [string]$WorkingDirectory,
        [string]$Command
    )

    $script = @"
`$Host.UI.RawUI.WindowTitle = "$Title"
Set-Location "$WorkingDirectory"
Remove-Item Env:HTTP_PROXY,Env:HTTPS_PROXY,Env:ALL_PROXY,Env:http_proxy,Env:https_proxy,Env:all_proxy -ErrorAction SilentlyContinue
$Command
Read-Host "Press Enter to close this window"
"@

    Start-Process powershell.exe -ArgumentList @(
        "-NoExit",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        $script
    )
}

function Assert-Directory {
    param([string]$Path)
    if (-not (Test-Path $Path)) {
        throw "Expected directory does not exist: $Path"
    }
}

function Clear-NextCache {
    $nextCache = Join-Path $Frontend ".next"
    if (Test-Path $nextCache) {
        Remove-Item -LiteralPath $nextCache -Recurse -Force
    }
}

function Stop-ProcessTree {
    param([System.Diagnostics.Process]$Process)

    if ($Process -and -not $Process.HasExited) {
        taskkill.exe /PID $Process.Id /T /F 2>$null | Out-Null
    }
}

function Start-DevProcess {
    param(
        [string]$Name,
        [string]$WorkingDirectory,
        [string]$FilePath,
        [string[]]$ArgumentList
    )

    Write-Host "Starting $Name in $WorkingDirectory"
    Start-Process `
        -FilePath $FilePath `
        -ArgumentList $ArgumentList `
        -WorkingDirectory $WorkingDirectory `
        -NoNewWindow `
        -PassThru
}

function Start-DevInline {
    Clear-NextCache

    $backendProcess = $null
    $frontendProcess = $null

    try {
        $backendProcess = Start-DevProcess `
            -Name "backend :8000" `
            -WorkingDirectory $Backend `
            -FilePath "py" `
            -ArgumentList @("-3.13", "-m", "uvicorn", "app.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000")

        $frontendProcess = Start-DevProcess `
            -Name "frontend :3000" `
            -WorkingDirectory $Frontend `
            -FilePath "npm.cmd" `
            -ArgumentList @("run", "dev")

        Write-Host ""
        Write-Host "Backend:  http://localhost:8000"
        Write-Host "Frontend: http://localhost:3000"
        Write-Host "Press Ctrl+C to stop both servers."
        Write-Host ""

        while (-not $backendProcess.HasExited -and -not $frontendProcess.HasExited) {
            Start-Sleep -Seconds 1
        }
    }
    finally {
        Stop-ProcessTree $frontendProcess
        Stop-ProcessTree $backendProcess
    }
}

function Show-PortStatus {
    $ports = @(
        @{ Port = 3000; App = "Frontend"; Url = "http://localhost:3000" },
        @{ Port = 8000; App = "Backend"; Url = "http://localhost:8000" }
    )

    $rows = foreach ($item in $ports) {
        $connections = Get-NetTCPConnection -LocalPort $item.Port -State Listen -ErrorAction SilentlyContinue

        if (-not $connections) {
            [pscustomobject]@{
                App = $item.App
                Port = $item.Port
                Status = "free"
                PID = ""
                Process = ""
                Url = $item.Url
            }
            continue
        }

        foreach ($connection in $connections) {
            $process = Get-Process -Id $connection.OwningProcess -ErrorAction SilentlyContinue
            [pscustomobject]@{
                App = $item.App
                Port = $item.Port
                Status = "listening"
                PID = $connection.OwningProcess
                Process = if ($process) { $process.ProcessName } else { "unknown" }
                Url = $item.Url
            }
        }
    }

    $rows | Format-Table -AutoSize
    Write-Host "To stop a process: Stop-Process -Id <PID>"
}

Assert-Directory $Backend
Assert-Directory $Frontend
Clear-LocalProxy

switch ($Mode) {
    "status" {
        Show-PortStatus
    }
    "dev" {
        Start-DevInline
    }
    "dev-windows" {
        Start-VisiblePowerShell `
            -Title "CareerPilot Backend :8000" `
            -WorkingDirectory $Backend `
            -Command "py -3.13 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"

        Start-VisiblePowerShell `
            -Title "CareerPilot Frontend :3000" `
            -WorkingDirectory $Frontend `
            -Command "if (Test-Path '.next') { Remove-Item -LiteralPath '.next' -Recurse -Force }; npm run dev"

        Write-Host "Started backend and frontend in visible PowerShell windows."
        Write-Host "Backend:  http://localhost:8000"
        Write-Host "Frontend: http://localhost:3000"
        Write-Host "Stop either server with Ctrl+C in its window."
    }
    "backend" {
        Set-Location $Backend
        py -3.13 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
    }
    "frontend" {
        Set-Location $Frontend
        Clear-NextCache
        npm run dev
    }
    "test" {
        Set-Location $Backend
        py -3.13 -m pytest
        Set-Location $Frontend
        npm run typecheck
    }
    "build" {
        Set-Location $Backend
        py -3.13 -m pytest
        Set-Location $Frontend
        Clear-NextCache
        npm run typecheck
        npm run build
    }
}
