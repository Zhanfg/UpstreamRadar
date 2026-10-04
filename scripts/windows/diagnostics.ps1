$ErrorActionPreference = "Stop"

$info = [ordered]@{
    Platform = "windows"
    PowerShell = $PSVersionTable.PSVersion.ToString()
    ProcessorCount = [Environment]::ProcessorCount
    Is64BitProcess = [Environment]::Is64BitProcess
    MachineName = $env:COMPUTERNAME
    Git = $null
    Python = $null
    MemoryPressure = $null
    HarmonyV3Schema = Test-Path "schemas/harmony-v3-score.schema.json"
    ReleaseHardening = Test-Path "config/release-hardening.json"
}

try { $info.Git = (& git --version 2>$null) } catch { $info.Git = "missing" }
try { $info.Python = (& python --version 2>&1) } catch { $info.Python = "missing" }

try {
    $os = Get-CimInstance Win32_OperatingSystem
    $total = [double]$os.TotalVisibleMemorySize
    $free = [double]$os.FreePhysicalMemory
    if ($total -gt 0) {
        $usedRatio = 1.0 - ($free / $total)
        $info.MemoryPressure = [Math]::Round(1.0 - [Math]::Exp(-2.0 * $usedRatio), 6)
    }
} catch {
    $info.MemoryPressure = $null
}

$info | ConvertTo-Json -Depth 3
