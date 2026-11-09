# SARScope public-repository publisher for the repository owner.
# Creates and pushes ONLY Git-tracked source files. Model weights, full datasets,
# local credentials and large rescue archives stay out of Git via .gitignore.
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$repo = 'keyurck7/SARScope'
$remote = 'https://github.com/keyurck7/SARScope.git'

function Require-Program([string]$name, [string]$help) {
    if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
        throw "$name is not installed. $help"
    }
}
function Run-Checked([string]$label, [scriptblock]$action) {
    Write-Host "`n== $label ==" -ForegroundColor Cyan
    & $action
    if ($LASTEXITCODE -ne 0) { throw "$label failed (exit $LASTEXITCODE). No further publishing was attempted." }
}

Require-Program 'git' 'Install Git for Windows with: winget install --id Git.Git -e'
Require-Program 'gh' 'Install GitHub CLI with: winget install --id GitHub.cli -e'
Require-Program 'py' 'Install Python 3.12 with: winget install --id Python.Python.3.12 -e'

Write-Host "Publishing SARScope as a PUBLIC repository: $repo" -ForegroundColor Yellow
Write-Host 'The full trained checkpoint and training dataset will NOT be uploaded.'
Write-Host 'They remain in your authorized local workspace (see WINDOWS_GITHUB_SETUP.md).'

& gh auth status --hostname github.com
if ($LASTEXITCODE -ne 0) {
    Write-Host 'Authenticate in your browser...' -ForegroundColor Yellow
    Run-Checked 'GitHub login' { gh auth login --hostname github.com --git-protocol https --web }
}
$account = (& gh api user --jq '.login')
if ($LASTEXITCODE -ne 0) { throw 'Cannot verify your authenticated GitHub account.' }
if ($account.Trim() -ne 'keyurck7') {
    throw "Signed into '$account', expected 'keyurck7'. Change accounts using gh auth switch and retry."
}

if (-not (Test-Path '.git')) {
    Run-Checked 'Initialize source repository' { git init -b main }
}
Run-Checked 'Stage source (excluded files stay untracked)' { git add -A }
Run-Checked 'Repository audit' { py -3.12 scripts/repository_audit.py }
Run-Checked 'Public-source safety scan' { py -3.12 scripts/public_release_check.py }

# Prevent anonymous commits from inheriting an unexpected identity.
$name = (& git config user.name)
$email = (& git config user.email)
if (-not $name -or -not $email) {
    Write-Host 'Git author identity is not configured for this computer.' -ForegroundColor Yellow
    $name = Read-Host 'Your Git author name'
    $email = Read-Host 'Your Git author email (GitHub noreply email is fine)'
    if (-not $name -or -not $email) { throw 'Git author name and email are required.' }
    git config user.name $name
    git config user.email $email
}

& git diff --cached --quiet
if ($LASTEXITCODE -eq 1) {
    Run-Checked 'Commit SARScope project' { git commit -m 'Initialize SARScope research platform' }
} elseif ($LASTEXITCODE -ne 0) {
    throw 'Could not determine staged changes.'
}
Run-Checked 'Use main branch' { git branch -M main }

& gh repo view $repo --json visibility --jq '.visibility' *> $null
$exists = $LASTEXITCODE -eq 0
if (-not $exists) {
    # GitHub CLI creates the repository on the account you authenticated.
    Run-Checked 'Create public GitHub repository' {
        gh repo create $repo --public --source . --remote origin --description 'Sentinel-1 SAR monthly land-cover intelligence and scientific reliability review'
    }
} else {
    $visibility = (& gh repo view $repo --json visibility --jq '.visibility')
    if ($visibility.Trim() -ne 'PUBLIC') {
        throw "$repo exists but is not public. No visibility change has been made."
    }
    $origin = (& git remote get-url origin 2>$null)
    if ($LASTEXITCODE -ne 0) {
        Run-Checked 'Connect remote' { git remote add origin $remote }
    } elseif ($origin.Trim() -notin @($remote,'git@github.com:keyurck7/SARScope.git')) {
        throw "Existing remote origin points somewhere else: $origin. Aborting to protect your other repository."
    }
}

Run-Checked 'Push project to GitHub' { git push -u origin main }
Write-Host "`nPUBLIC SOURCE REPOSITORY: https://github.com/$repo" -ForegroundColor Green
Write-Host 'To deploy the static demo: Settings > Pages > Source: GitHub Actions.'
Write-Host 'To run dynamic inference: see WINDOWS_GITHUB_SETUP.md and install the local checkpoint.'
