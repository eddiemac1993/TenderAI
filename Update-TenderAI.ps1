$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Windows.Forms

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$managePy = Join-Path $projectRoot "manage.py"

function Show-Message {
    param([string] $Message, [string] $Title = "TenderAI Update")
    [System.Windows.Forms.MessageBox]::Show($Message, $Title) | Out-Null
}

if (-not (Test-Path $managePy)) {
    Show-Message "Could not find manage.py in $projectRoot"
    exit 1
}

$git = Get-Command git -ErrorAction SilentlyContinue
$python = Get-Command python -ErrorAction SilentlyContinue

if (-not $git) {
    Show-Message "Git was not found on PATH. Install Git first, then run this updater again."
    exit 1
}

if (-not $python) {
    Show-Message "Python was not found on PATH. Install Python first, then run this updater again."
    exit 1
}

Push-Location $projectRoot
try {
    git pull
    python -m pip install -r requirements.txt
    python manage.py migrate
    python manage.py collectstatic --noinput
    Show-Message "TenderAI features were updated. Your local database, uploaded files, and private settings were not replaced."
}
catch {
    Show-Message "Update failed:`n$($_.Exception.Message)"
    exit 1
}
finally {
    Pop-Location
}
