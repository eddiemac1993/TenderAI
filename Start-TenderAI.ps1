$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Windows.Forms

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$managePy = Join-Path $projectRoot "manage.py"
$hostName = "127.0.0.1"
$port = 8005
$url = "http://$hostName`:$port/"
$outputLog = Join-Path $projectRoot "tenderai-server.log"
$errorLog = Join-Path $projectRoot "tenderai-server-error.log"

function Test-PortOpen {
    param (
        [string] $HostName,
        [int] $Port
    )

    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $async = $client.BeginConnect($HostName, $Port, $null, $null)
        $connected = $async.AsyncWaitHandle.WaitOne(400, $false)
        if ($connected) {
            $client.EndConnect($async)
        }
        $client.Close()
        return $connected
    }
    catch {
        return $false
    }
}

if (-not (Test-Path $managePy)) {
    [System.Windows.Forms.MessageBox]::Show("Could not find manage.py in $projectRoot", "TenderAI Launcher")
    exit 1
}

if (-not (Test-PortOpen -HostName $hostName -Port $port)) {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCommand) {
        [System.Windows.Forms.MessageBox]::Show("Python was not found on PATH. Please install Python or add it to PATH.", "TenderAI Launcher")
        exit 1
    }

    $arguments = "manage.py runserver $hostName`:$port"
    Start-Process `
        -FilePath $pythonCommand.Source `
        -ArgumentList $arguments `
        -WorkingDirectory $projectRoot `
        -WindowStyle Minimized `
        -RedirectStandardOutput $outputLog `
        -RedirectStandardError $errorLog

    $deadline = (Get-Date).AddSeconds(18)
    while ((Get-Date) -lt $deadline) {
        if (Test-PortOpen -HostName $hostName -Port $port) {
            break
        }
        Start-Sleep -Milliseconds 500
    }
}

Start-Process $url
