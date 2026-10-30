# Haeness2: materialize *every tracked file at HEAD* in the existing sparse clone.
# Does NOT fetch complete Git history and does NOT git clean/reset/delete.
# Run from the project root: powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\SYNC_ALL_UPSTREAM.ps1
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$project = Split-Path -Parent $PSScriptRoot
$repo = Join-Path $project 'upstream'
if (!(Test-Path (Join-Path $repo '.git'))) {
    throw "Missing upstream/.git; do not create a new clone over existing data."
}
if (!(Get-Command git -ErrorAction SilentlyContinue)) {
    throw "git CLI not found"
}
Push-Location $project
try {
    $head = (& git -C $repo rev-parse HEAD)
    if ($LASTEXITCODE -ne 0) { throw 'Cannot determine upstream HEAD' }
    $status = @(& git -C $repo status --porcelain=v1)
    if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect upstream status' }
    if ($status.Count -gt 0) {
        Write-Host 'Upstream has existing changes; refusing to modify this checkout.'
        $status | ForEach-Object { Write-Host $_ }
        throw 'Dirty upstream'
    }
    Write-Host ("Syncing all tracked HEAD files from " + $head)
    Write-Host 'This can download large reference_code, PDF, image and backup files.'
    & git -C $repo sparse-checkout disable
    if ($LASTEXITCODE -ne 0) { throw 'Full worktree checkout failed; repo may remain partially sparse' }
    $after = (& git -C $repo rev-parse HEAD)
    if ($LASTEXITCODE -ne 0 -or $after -ne $head) { throw 'Unexpected HEAD change' }
    $tracked = @(& git -C $repo ls-files)
    if ($LASTEXITCODE -ne 0) { throw 'ls-files failed' }
    $changes = @(& git -C $repo status --porcelain=v1)
    if ($LASTEXITCODE -ne 0) { throw 'status inspection failed' }
    Write-Host ("TRACKED_FILES=" + $tracked.Count)
    Write-Host ("HEAD=" + $head)
    Write-Host ("DIRTY_ITEMS=" + $changes.Count)
    if ($changes.Count -gt 0) { $changes | ForEach-Object { Write-Host $_ }; throw 'Unexpected changed files' }
    & python -B -m scripts.check_sources
    if ($LASTEXITCODE -ne 0) { throw 'Official key files incomplete; see MISSING list above' }
    Write-Host 'FULL_TRACKED_HEAD_SYNC=PASS'
} finally {
    Pop-Location
}
