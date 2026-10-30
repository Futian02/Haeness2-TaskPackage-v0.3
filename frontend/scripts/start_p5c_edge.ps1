$ErrorActionPreference = 'Stop'
$edge = 'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
if (-not (Test-Path -LiteralPath $edge)) { throw "Microsoft Edge missing: $edge" }
$profile = Join-Path $env:TEMP ('mechanical-agent-p5c-edge-' + [guid]::NewGuid().ToString('N'))
Start-Process -FilePath $edge -WindowStyle Hidden -PassThru -ArgumentList @(
  '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
  '--remote-debugging-address=127.0.0.1', '--remote-debugging-port=9222',
  "--user-data-dir=$profile", 'about:blank'
) | Select-Object -ExpandProperty Id
