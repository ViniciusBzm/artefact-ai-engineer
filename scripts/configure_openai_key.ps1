# Run locally. Input is hidden, the value never becomes part of command history.
$ErrorActionPreference = 'Stop'
$taskProjectRoot = Split-Path -Parent $PSScriptRoot
$taskPrivateDir = Join-Path $taskProjectRoot '.local'
New-Item -ItemType Directory -Force -Path $taskPrivateDir | Out-Null
$taskSecureKey = Read-Host 'OpenAI application API key (hidden; never paste it in chat)' -AsSecureString
$taskKeyValue = [System.Net.NetworkCredential]::new('', $taskSecureKey).Password
if ([string]::IsNullOrWhiteSpace($taskKeyValue)) { throw 'No key supplied.' }
$taskKeyValue = $taskKeyValue.Trim()
if ($taskKeyValue -notmatch '^sk-[A-Za-z0-9_-]{30,}$') { throw 'This does not resemble a complete OpenAI secret key. Nothing was saved. Copy the newly created secret value, not its name, ID or a command.' }
$taskKeyPath = Join-Path $taskPrivateDir 'openai_api_key.txt'
[System.IO.File]::WriteAllText($taskKeyPath, $taskKeyValue, [System.Text.UTF8Encoding]::new($false))
$taskKeyValue = $null
$taskSecureKey = $null
Write-Output 'Key saved under ignored .local. It was not displayed or added to Git.'
Write-Output 'This is a local plaintext file protected by your OS account; remove it after validation.'
