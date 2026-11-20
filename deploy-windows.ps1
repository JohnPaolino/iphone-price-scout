# First-time deployment using Git for Windows and the GitHub CLI (gh).
# Run from an extracted copy of the project in PowerShell:
#   powershell -ExecutionPolicy Bypass -File .\deploy-windows.ps1
# Your API key is entered in GitHub CLI's prompt, not written into this project.
param([string]$Repository = 'iphone-price-scout')
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

foreach ($tool in @('git','gh')) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        throw "Missing $tool. Install Git for Windows and GitHub CLI, then retry."
    }
}

& gh auth status
if ($LASTEXITCODE -ne 0) { throw 'Please run: gh auth login' }

if (-not (Test-Path '.git')) {
    & git init -b main
    if ($LASTEXITCODE -ne 0) { throw 'git init failed' }
}

$login = (& gh api user --jq '.login').Trim()
if ($LASTEXITCODE -ne 0 -or -not $login) { throw 'Unable to determine GitHub account' }
$remote = "$login/$Repository"
if (-not (git config --local user.name)) { & git config --local user.name $login }
if (-not (git config --local user.email)) { & git config --local user.email "$login@users.noreply.github.com" }

& git add -A
& git diff --cached --quiet
if ($LASTEXITCODE -ne 0) {
    & git commit -m 'Create Price Scout monitoring dashboard'
    if ($LASTEXITCODE -ne 0) { throw 'git commit failed' }
}

Write-Host "Creating public repository $remote ..."
& gh repo create $Repository --public --source . --remote origin --push
if ($LASTEXITCODE -ne 0) { throw 'Could not create repository. Check that the name is available.' }

Write-Host 'Setting up GitHub Pages (GitHub Actions source) ...'
& gh api -X POST "repos/$remote/pages" -f 'build_type=workflow' 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Warning "Could not enable Pages automatically. Open https://github.com/$remote/settings/pages and choose GitHub Actions as the source."
}

Write-Host ''
Write-Host 'Now set the SERPER_API_KEY secret (paste the key when prompted).'
& gh secret set SERPER_API_KEY -R $remote
if ($LASTEXITCODE -ne 0) { throw 'Cannot save API secret; set it manually in repository Settings > Secrets and variables > Actions.' }

Write-Host 'Triggering the first scan ...'
& gh workflow run monitor.yml -R $remote --ref main
if ($LASTEXITCODE -ne 0) {
    Write-Warning "Could not trigger immediately. Open https://github.com/$remote/actions and select 'Hourly iPhone price monitor' > Run workflow."
}

Write-Host ''
Write-Host "Repository: https://github.com/$remote"
Write-Host "Actions: https://github.com/$remote/actions"
Write-Host "Shareable dashboard (after first successful run): https://$login.github.io/$Repository/"
Write-Host 'Telegram alerts are optional. See README.md for recipient setup.'
