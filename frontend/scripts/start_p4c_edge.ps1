$ErrorActionPreference = 'Stop'
$edge = 'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
$profile = Join-Path $env:TEMP 'mechanical-agent-p4c-edge-profile'
Start-Process -FilePath $edge -WindowStyle Hidden -PassThru -ArgumentList @(
  '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
  '--remote-debugging-address=127.0.0.1', '--remote-debugging-port=9222',
  "--user-data-dir=$profile", 'about:blank'
) | Select-Object -ExpandProperty Id
