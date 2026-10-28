param(
    [Parameter(Mandatory = $true)][string]$Ref,
    [Parameter(Mandatory = $true)][string]$From,
    [string]$Label = "raw paste by operator, not independently verified"
)
$nl = [Environment]::NewLine
$u = New-Object System.Text.UTF8Encoding($false)
$entries = Join-Path $PSScriptRoot "entries"
New-Item -ItemType Directory -Force -Path $entries | Out-Null
$safe = $Ref -replace '[^A-Za-z0-9-]', '-'
$path = Join-Path $entries ($safe + ".txt")
if (Test-Path $path) {
    Write-Host "STOPPED: $safe exists. Entries are never overwritten. Use a new Ref." -ForegroundColor Red
    exit 1
}
$raw = Get-Clipboard -Raw
if ([string]::IsNullOrWhiteSpace($raw)) {
    Write-Host "STOPPED: clipboard is empty. Copy the handoff first." -ForegroundColor Red
    exit 1
}
$sha = [System.Security.Cryptography.SHA256]::Create()
$hash = ([BitConverter]::ToString($sha.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($raw)))).Replace("-","").ToLower()
$when = Get-Date -Format "yyyy-MM-dd HH:mm"
$header = "Ref: $Ref" + $nl + "From: $From" + $nl + "Received: $when" + $nl + "Label: $Label" + $nl + "Sha256: $hash" + $nl + "-----" + $nl
[IO.File]::WriteAllText($path, $header + $raw, $u)
$idx = Join-Path $PSScriptRoot "INDEX.md"
$row = "| $Ref | $From | $when | $($hash.Substring(0,12)) |"
$lines = (Get-Content $idx -Raw) -split $nl
$out = @()
$done = $false
foreach ($l in $lines) {
    $out += $l
    if (-not $done -and $l -match '^\|[-| ]+\|$') { $out += $row; $done = $true }
}
if (-not $done) { $out += $row }
[IO.File]::WriteAllText($idx, ($out -join $nl) + $nl, $u)
Write-Host "Saved $path"
Write-Host "Added $row"