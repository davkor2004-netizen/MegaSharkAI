PS> Start-Sleep -Seconds 8; curl "http://localhost:3000/settings" -TimeoutSec 5 -ErrorAction SilentlyContinue 2>&1 | Select-String -Pattern "Настройки|Settings" | Select-Object -First 3
#< CLIXML

<!doctype html>
<html lang="ru">
  <head>
    <meta charset="utf-8" />
    <link rel="icon" href="./favicon.png" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
