# Verify gates for the BE-perf + UI + prompt agent deliverables.
# Run:  pwsh -File _tmp_verify_gates.ps1
$ErrorActionPreference = "Continue"
$root = "D:\rag-real-estate"
Set-Location $root
$py = ".venv\Scripts\python.exe"

Write-Host "=== 1. PYTEST ===" -ForegroundColor Cyan
& $py -m pytest -q 2>&1 | Select-Object -Last 5

Write-Host ""
Write-Host "=== 2. FE TYPECHECK ===" -ForegroundColor Cyan
npm run typecheck -w @rag-ragre/web 2>&1 | Select-Object -Last 15
Write-Host ("typecheck exit: " + $LASTEXITCODE)

Write-Host ""
Write-Host "=== 3. FE BUILD ===" -ForegroundColor Cyan
npm run build -w @rag-ragre/web 2>&1 | Select-Object -Last 15
Write-Host ("build exit: " + $LASTEXITCODE)

Write-Host ""
Write-Host "=== 4. RUFF (current vs baseline JSON) ===" -ForegroundColor Cyan
& $py -m ruff check api tests eval --output-format json 2>$null | Out-File -Encoding utf8 _tmp_ruff_current.json
if (Test-Path _tmp_ruff_baseline.json) {
  $base = Get-Content _tmp_ruff_baseline.json -Raw | ConvertFrom-Json
  $cur  = Get-Content _tmp_ruff_current.json -Raw | ConvertFrom-Json
  $baseKeys = @{}
  foreach ($b in $base) {
    $k = $b.location.filename + ":" + $b.location.row + ":" + $b.location.column + ":" + $b.code
    $baseKeys[$k] = $true
  }
  $newOnes = @()
  foreach ($c in $cur) {
    $k = $c.location.filename + ":" + $c.location.row + ":" + $c.location.column + ":" + $c.code
    if (-not $baseKeys.ContainsKey($k)) { $newOnes += ($k + "  " + $c.message) }
  }
  Write-Host ("baseline: " + $base.Count + "  current: " + $cur.Count + "  NEW: " + $newOnes.Count)
  if ($newOnes.Count -gt 0) { $newOnes | Select-Object -First 40 }
} else {
  $c2 = Get-Content _tmp_ruff_current.json -Raw | ConvertFrom-Json
  Write-Host ("baseline JSON missing; current count: " + $c2.Count)
}

Write-Host ""
Write-Host "=== 5. COMPILEALL ===" -ForegroundColor Cyan
& $py -m compileall -q api ingest eval 2>&1 | Select-Object -Last 5
Write-Host ("compileall exit: " + $LASTEXITCODE)
Write-Host ""
Write-Host "DONE"
