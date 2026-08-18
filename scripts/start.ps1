<#
.SYNOPSIS
    Start the whole SecureLock stack for the SIH demo (Windows).

.DESCRIPTION
    Brings up, in order: local blockchain -> contract deployment -> database seed
    -> API. Everything runs locally; no internet, faucet or API key is required.

.EXAMPLE
    .\scripts\start.ps1
    .\scripts\start.ps1 -Reset      # wipe and rebuild the demo data
#>
[CmdletBinding()]
param(
    [switch]$Reset,
    [switch]$SkipFrontend
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root "backend\.venv\Scripts\python.exe"

function Write-Step($n, $msg) {
    Write-Host ""
    Write-Host ("=" * 68) -ForegroundColor DarkCyan
    Write-Host "  $n. $msg" -ForegroundColor Cyan
    Write-Host ("=" * 68) -ForegroundColor DarkCyan
}

function Wait-ForPort($port, $seconds = 45) {
    $deadline = (Get-Date).AddSeconds($seconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $c = New-Object Net.Sockets.TcpClient
            $c.Connect("127.0.0.1", $port); $c.Close()
            return $true
        } catch { Start-Sleep -Milliseconds 700 }
    }
    return $false
}

# ---------------------------------------------------------------- prerequisites
Write-Step 0 "Checking prerequisites"
foreach ($cmd in @("node", "npm", "python")) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
        throw "$cmd is not on PATH. Install it and try again."
    }
}
Write-Host "  node   $(node --version)"
Write-Host "  npm    $(npm --version)"
Write-Host "  python $(python --version)"

if (-not (Test-Path $Python)) {
    Write-Host "  Creating Python virtual environment..." -ForegroundColor Yellow
    python -m venv (Join-Path $Root "backend\.venv")
    & $Python -m pip install --quiet --upgrade pip
    & $Python -m pip install --quiet -r (Join-Path $Root "backend\requirements.txt")
}
if (-not (Test-Path (Join-Path $Root "blockchain\node_modules"))) {
    Write-Host "  Installing blockchain dependencies..." -ForegroundColor Yellow
    Push-Location (Join-Path $Root "blockchain"); npm install --no-audit --no-fund; Pop-Location
}

# ---------------------------------------------------------------- blockchain
Write-Step 1 "Starting local blockchain (Hardhat, chainId 31337)"
if (Wait-ForPort 8545 1) {
    Write-Host "  A node is already listening on 8545; reusing it." -ForegroundColor Yellow
} else {
    Push-Location (Join-Path $Root "blockchain")
    Start-Process -FilePath "npx.cmd" `
        -ArgumentList "hardhat","node","--hostname","127.0.0.1","--port","8545" `
        -WindowStyle Minimized
    Pop-Location
    if (-not (Wait-ForPort 8545 60)) { throw "Hardhat node did not start on port 8545." }
}
Write-Host "  Blockchain up at http://127.0.0.1:8545" -ForegroundColor Green

Write-Step 2 "Deploying contracts"
Push-Location (Join-Path $Root "blockchain")
npx hardhat run scripts/deploy.js --network localhost
Pop-Location

# ---------------------------------------------------------------- database
Write-Step 3 "Seeding the demo database"
Push-Location (Join-Path $Root "backend")
if ($Reset) {
    # The chain is append-only, so a fresh database needs freshly deployed
    # contracts -- otherwise re-registering Q-000001 reverts. Step 2 above
    # already redeployed, so this is safe.
    & $Python -m app.seed --reset
} else {
    & $Python -m app.seed
}
Pop-Location

# ---------------------------------------------------------------- api
Write-Step 4 "Starting the API"
if (Wait-ForPort 8000 1) {
    Write-Host "  Something is already listening on 8000; leaving it alone." -ForegroundColor Yellow
} else {
    Push-Location (Join-Path $Root "backend")
    Start-Process -FilePath $Python `
        -ArgumentList "-m","uvicorn","app.main:app","--host","127.0.0.1","--port","8000" `
        -WindowStyle Minimized
    Pop-Location
    if (-not (Wait-ForPort 8000 45)) { throw "API did not start on port 8000." }
}

# ---------------------------------------------------------------- frontend
if (-not $SkipFrontend) {
    $frontend = Join-Path $Root "frontend"
    if (Test-Path (Join-Path $frontend "package.json")) {
        Write-Step 5 "Starting the frontend"
        if (-not (Test-Path (Join-Path $frontend "node_modules"))) {
            Push-Location $frontend; npm install --no-audit --no-fund; Pop-Location
        }
        Push-Location $frontend
        Start-Process -FilePath "npm.cmd" -ArgumentList "run","dev" -WindowStyle Minimized
        Pop-Location
        Wait-ForPort 3000 90 | Out-Null
    }
}

Write-Host ""
Write-Host ("=" * 68) -ForegroundColor Green
Write-Host "  SecureLock is running" -ForegroundColor Green
Write-Host ("=" * 68) -ForegroundColor Green
Write-Host "  API docs    http://127.0.0.1:8000/docs"
Write-Host "  Blockchain  http://127.0.0.1:8545  (LOCAL EVM DEMO NETWORK)"
if (Test-Path (Join-Path $Root "frontend\package.json")) {
    Write-Host "  Frontend    http://localhost:3000"
}
Write-Host ""
Write-Host "  Demo accounts (password: SecureLock#2026)"
Write-Host "    admin@securelock.demo       SUPER_ADMIN"
Write-Host "    setter1@securelock.demo     QUESTION_SETTER"
Write-Host "    setter2@securelock.demo     QUESTION_SETTER"
Write-Host "    reviewer@securelock.demo    REVIEWER"
Write-Host "    authority@securelock.demo   EXAM_AUTHORITY"
Write-Host "    auditor@securelock.demo     AUDITOR"
Write-Host ""
Write-Host "  Verify the whole demo flow:" -ForegroundColor Cyan
Write-Host "    backend\.venv\Scripts\python.exe scripts\e2e_demo.py"
Write-Host ""
