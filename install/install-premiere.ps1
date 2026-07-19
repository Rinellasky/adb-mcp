# install-premiere.ps1 â€” one-line installer for the Premiere MCP (Windows)
#
#   irm https://raw.githubusercontent.com/Rinellasky/adb-mcp/master/install/install-premiere.ps1 | iex
#
# What it does (idempotent, backs up before changing anything):
#   1. Verifies/install-hints prerequisites: uv, Claude Desktop
#   2. Downloads the latest release source + proxy executable
#   3. Adds the `premiere-mcp` server to claude_desktop_config.json (backup made)
#   4. Downloads the .ccx UXP plugin and opens it (Creative Cloud installs it)
#   5. Prints the two manual steps that can't be automated
#
# Nothing here touches Premiere settings or existing MCP servers.

$ErrorActionPreference = "Stop"
$Repo = "Rinellasky/adb-mcp"
$InstallDir = Join-Path $env:LOCALAPPDATA "adb-mcp"

Write-Host "=== Premiere MCP installer ===" -ForegroundColor Cyan

# -- 1. prerequisites ---------------------------------------------------------
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "uv not found - installing via winget..." -ForegroundColor Yellow
    winget install --id=astral-sh.uv -e --accept-source-agreements --accept-package-agreements
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "User") + ";" +
                [System.Environment]::GetEnvironmentVariable("Path", "Machine")
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        throw "uv still not found after install - open a new terminal and re-run."
    }
}
$claudeConfig = Join-Path $env:APPDATA "Claude\claude_desktop_config.json"
if (-not (Test-Path (Split-Path $claudeConfig))) {
    throw "Claude Desktop does not appear to be installed (no $((Split-Path $claudeConfig))). Install it from https://claude.ai/download first."
}

# -- 2. download source + proxy ----------------------------------------------
Write-Host "Downloading adb-mcp to $InstallDir ..."
New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
$zip = Join-Path $env:TEMP "adb-mcp-src.zip"
Invoke-WebRequest "https://github.com/$Repo/archive/refs/heads/master.zip" -OutFile $zip
$tmp = Join-Path $env:TEMP "adb-mcp-unzip"
if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
Expand-Archive $zip -DestinationPath $tmp
$src = Get-ChildItem $tmp -Directory | Select-Object -First 1
Copy-Item "$($src.FullName)\*" $InstallDir -Recurse -Force
Remove-Item $zip, $tmp -Recurse -Force

$release = Invoke-RestMethod "https://api.github.com/repos/$Repo/releases/latest"
$proxyAsset = $release.assets | Where-Object { $_.name -eq "adb-proxy-socket-win-x64.exe" }
if ($proxyAsset) {
    Invoke-WebRequest $proxyAsset.browser_download_url -OutFile (Join-Path $InstallDir "adb-proxy-socket-win-x64.exe")
    Write-Host "Proxy downloaded."
}

# -- 3. register the MCP server ----------------------------------------------
Write-Host "Registering premiere-mcp in Claude Desktop config..."
if (Test-Path $claudeConfig) {
    Copy-Item $claudeConfig "$claudeConfig.bak-premiere-mcp" -Force
    $cfg = Get-Content $claudeConfig -Raw | ConvertFrom-Json
} else {
    $cfg = [PSCustomObject]@{}
}
if (-not $cfg.PSObject.Properties["mcpServers"]) {
    $cfg | Add-Member -MemberType NoteProperty -Name mcpServers -Value ([PSCustomObject]@{})
}
$entry = [PSCustomObject]@{
    command = "uv"
    args = @("run", "--directory", (Join-Path $InstallDir "mcp"), "mcp", "run", "pr-mcp.py")
}
$cfg.mcpServers | Add-Member -MemberType NoteProperty -Name "premiere-mcp" -Value $entry -Force
$cfg | ConvertTo-Json -Depth 10 | Set-Content $claudeConfig -Encoding UTF8

# -- 4. UXP plugin ------------------------------------------------------------
$ccxAsset = $release.assets | Where-Object { $_.name -eq "premiere-mcp-plugin.ccx" }
if ($ccxAsset) {
    $ccx = Join-Path $InstallDir "premiere-mcp-plugin.ccx"
    Invoke-WebRequest $ccxAsset.browser_download_url -OutFile $ccx
    Write-Host "Opening the UXP plugin installer (Creative Cloud handles .ccx)..."
    Start-Process $ccx
}

# -- 5. done ------------------------------------------------------------------
Write-Host ""
Write-Host "=== Installed. Two manual steps remain ===" -ForegroundColor Green
Write-Host "1. Start the proxy:  $InstallDir\adb-proxy-socket-win-x64.exe"
Write-Host "   (keep it running; it bridges Claude <-> Premiere on localhost:3001)"
Write-Host "2. In Premiere Pro (Beta): open the 'Premiere MCP Agent' panel (Plugins menu) and click Connect."
Write-Host ""
Write-Host "Then restart Claude Desktop - the premiere-mcp tools will appear."
Write-Host "Health check: ask Claude to run get_project_info."
Write-Host ''
Write-Host 'Known issue: Premiere Beta 26.5 changed UXP APIs - some timeline-write tools can hang.' -ForegroundColor Yellow
Write-Host 'Reads/imports/frame-export are verified working. Details: FINDINGS_2026-07-12_premiere_live_session.md'
