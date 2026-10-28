# archive-paste.ps1
#
# Reads the clipboard, verifies it looks like a handoff, and files it in the
# archive under a ref it can determine. Then optionally commits and pushes.
#
# USAGE
#   powershell -ExecutionPolicy Bypass -File archive-paste.ps1
#   ... -Ref APX-g2-015        override the auto-detected ref
#   ... -NoPush                file it but do not commit
#   ... -Force                 file even if verification is unhappy

param(
    [string]$Repo = "",
    [string]$Ref = "",
    [string]$From = "",
    [switch]$NoPush,
    [switch]$Force
)

$ErrorActionPreference = "Continue"
$nl = [Environment]::NewLine
$utf8 = New-Object System.Text.UTF8Encoding($false)

function Fail($code, $msg) {
    Write-Host ""
    Write-Host "NOT FILED: $msg" -ForegroundColor Red
    Write-Host ""
    Read-Host "Press Enter to close"
    exit $code
}

function Note($msg) { Write-Host "  $msg" }

if (-not $Repo) {
    $d = $PSScriptRoot
    while ($d -and -not (Test-Path (Join-Path $d ".git"))) {
        $parent = Split-Path $d -Parent
        if ($parent -eq $d) { break }
        $d = $parent
    }
    $Repo = $d
}
if (-not $Repo -or -not (Test-Path (Join-Path $Repo ".git"))) {
    Fail 2 "could not find a git repository above this script. Pass -Repo."
}
Set-Location $Repo

Write-Host "Orbital archive - filing from clipboard" -ForegroundColor Cyan
Write-Host ""

$raw = Get-Clipboard -Raw
if ([string]::IsNullOrWhiteSpace($raw)) {
    Fail 1 "the clipboard is empty. Copy a handoff first."
}

$lines = $raw -split "`r?`n"
Note "clipboard: $($raw.Length) chars, $($lines.Count) lines"

$problems = @()
if (-not ($raw -match '(?m)^\s*HANDOFF\s*$' -or $raw -match '(?m)^\s*STATUS\s*$')) {
    $problems += "no 'HANDOFF' or 'STATUS' line found"
}
if ($raw -notmatch '(?m)^\s*Verified\s*:') { $problems += "no 'Verified:' block" }
if ($raw -notmatch '(?m)^\s*Unverified\s*:') { $problems += "no 'Unverified:' block" }
if ($raw -notmatch '(?m)^\s*SIGN-OFF\s*$') { $problems += "no 'SIGN-OFF' block" }

$detected = ""
foreach ($l in $lines) {
    if ($l -match '^\s*Ref\s*:\s*([A-Za-z]{2,7}-g?[0-9]*-?[0-9]{1,4})') { $detected = $Matches[1]; break }
}
if (-not $Ref) { $Ref = $detected }

$detectedFrom = ""
foreach ($l in $lines) {
    if ($l -match '^\s*From\s*:\s*(.+?)\s*$') { $detectedFrom = $Matches[1]; break }
}
if (-not $From) { $From = $detectedFrom }
if (-not $From) { $From = "unknown" }

if ($Ref -and $Ref -notmatch '-g[0-9]+-') {
    if ($Ref -match '^([A-Za-z]+)-([0-9]+)$') {
        $Ref = "$($Matches[1])-g1-$($Matches[2])"
        Note "ref normalised to $Ref"
    }
}

if (-not $Ref) {
    $problems += "could not detect a Ref. Pass -Ref."
} elseif ($Ref -notmatch '^[A-Za-z]{2,7}-g[0-9]+-[0-9]{3}$') {
    $problems += "ref '$Ref' is not in the form PREFIX-gN-NNN"
}

Write-Host ""
if ($problems.Count -gt 0) {
    Write-Host "VERIFICATION: $($problems.Count) problem(s)" -ForegroundColor Yellow
    foreach ($p in $problems) { Write-Host "  - $p" -ForegroundColor Yellow }
    Write-Host ""
    if (-not $Force) {
        Write-Host "This does not look like a handoff. Nothing filed." -ForegroundColor Red
        Write-Host "To file it anyway, run again with -Force" -ForegroundColor Yellow
        Read-Host "Press Enter to close"
        exit 2
    }
    Write-Host "-Force given, continuing." -ForegroundColor Yellow
} else {
    Write-Host "VERIFICATION: passed" -ForegroundColor Green
}
Note "ref  : $Ref"
Note "from : $From"
Write-Host ""

$entries = Join-Path $Repo "docs\archive\entries"
if (-not (Test-Path $entries)) { Fail 2 "docs\archive\entries does not exist." }
$safe = $Ref -replace '[^A-Za-z0-9-]', '-'
$path = Join-Path $entries ($safe + ".txt")
if (Test-Path $path) {
    Fail 3 "$safe already exists. Entries are never overwritten. Use a new ref."
}

$sha = [System.Security.Cryptography.SHA256]::Create()
$hash = ([BitConverter]::ToString($sha.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($raw)))).Replace("-", "").ToLower()
$when = Get-Date -Format "yyyy-MM-dd HH:mm"

$header = "Ref: $Ref" + $nl + "From: $From" + $nl + "Received: $when" + $nl +
          "Label: raw paste by operator, not independently verified" + $nl +
          "Sha256: $hash" + $nl + "-----" + $nl
[IO.File]::WriteAllText($path, $header + $raw, $utf8)
Note "wrote $path"

$idx = Join-Path $Repo "docs\archive\INDEX.md"
if (Test-Path $idx) {
    $row = "| $Ref | $From | $when | $($hash.Substring(0,12)) |"
    $content = Get-Content $idx -Raw
    $out = @()
    $done = $false
    foreach ($l in ($content -split "`r?`n")) {
        $out += $l
        if (-not $done -and $l -match '^\|[-| ]+\|$') { $out += $row; $done = $true }
    }
    if (-not $done) { $out += $row }
    [IO.File]::WriteAllText($idx, (($out -join $nl).TrimEnd()) + $nl, $utf8)
    Note "index row added"
}

if ($NoPush) {
    Write-Host ""
    Write-Host "Filed. -NoPush given, so nothing was committed." -ForegroundColor Yellow
    Read-Host "Press Enter to close"
    exit 0
}

Write-Host ""
$branch = (git branch --show-current)
$a = Read-Host "Type YES to commit and push to origin/$branch. Anything else leaves it staged"
if ($a -ne "YES") {
    Write-Host "Left on disk, not committed." -ForegroundColor Yellow
    Read-Host "Press Enter to close"
    exit 0
}

git add docs/archive
git reset -q -- fix_o1.py PROJECT.md 2>$null
git commit -m "Archive $Ref from $From (raw paste, not independently verified)"
if ($LASTEXITCODE -ne 0) {
    Write-Host "commit failed - paste the output above" -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit 4
}
git push origin $branch
if ($LASTEXITCODE -ne 0) {
    Write-Host "push failed - do NOT force-push. paste the output above" -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit 4
}

Write-Host ""
Write-Host "FILED AND PUSHED" -ForegroundColor Green
Note "ref    : $Ref"
Note "sha256 : $($hash.Substring(0,12))"
Note "commit : $(git rev-parse --short HEAD)"
Write-Host ""
Read-Host "Press Enter to close"
exit 0