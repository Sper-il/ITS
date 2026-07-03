Get-CimInstance Win32_Process -Filter "ProcessId=41396" | Select-Object ProcessId, CommandLine, ExecutablePath
