$ErrorActionPreference = "SilentlyContinue"

$listeners = @(Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue)
$processIds = @()

foreach ($conn in $listeners) {
    $processIds += [int]$conn.OwningProcess
}

$uvicornProcesses = Get-CimInstance Win32_Process |
    Where-Object { $_.CommandLine -like "*uvicorn*app.main:app*" -and $_.CommandLine -like "*--port 8000*" }

foreach ($proc in $uvicornProcesses) {
    $processIds += [int]$proc.ProcessId
    $children = Get-CimInstance Win32_Process | Where-Object { $_.ParentProcessId -eq $proc.ProcessId }
    foreach ($child in $children) {
        $processIds += [int]$child.ProcessId
    }
}

$processIds = $processIds | Sort-Object -Unique

if (-not $processIds.Count) {
    Write-Host "No backend process found on port 8000."
    exit 0
}

foreach ($processId in $processIds) {
    Stop-Process -Id $processId -Force
    Write-Host "Stopped backend process $processId"
}

Start-Sleep -Seconds 1
$remaining = @(Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue)
if ($remaining.Count -eq 0) {
    Write-Host "Port 8000 is free."
} else {
    Write-Host "Port 8000 is still occupied:"
    $remaining | Select-Object LocalAddress, LocalPort, OwningProcess | Format-Table -AutoSize
}
