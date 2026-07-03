$proc = Get-CimInstance Win32_Process -Filter "ProcessId=41396"
$parentId = $proc.ParentProcessId
Write-Host "PID 41396:"
Write-Host "  CommandLine: $($proc.CommandLine)"
Write-Host "  ParentProcessId: $parentId"

$parent = Get-CimInstance Win32_Process -Filter "ProcessId=$parentId"
Write-Host "Parent (PID $parentId):"
Write-Host "  CommandLine: $($parent.CommandLine)"
Write-Host "  Name: $($parent.Name)"
