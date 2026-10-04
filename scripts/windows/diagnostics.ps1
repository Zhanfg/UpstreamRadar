$ErrorActionPreference = "Stop"

$info = [ordered]@{
    Platform = "windows"
    PowerShell = $PSVersionTable.PSVersion.ToString()
    ProcessorCount = [Environment]::ProcessorCount
    Is64BitProcess = [Environment]::Is64BitProcess
    MachineName = $env:COMPUTERNAME
    Git = $null
    Python = $null
}

try { $info.Git = (& git --version 2>$null) } catch { $info.Git = "missing" }
try { $info.Python = (& python --version 2>&1) } catch { $info.Python = "missing" }

$info | ConvertTo-Json -Depth 3
