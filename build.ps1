$ErrorActionPreference = 'Stop'
$td = 'D:\anlu\TD_6.2.1_Engineer_6.2.168.116\bin\td_commands_prompt.exe'
$python = 'C:\Users\Harry\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $python (Join-Path $PSScriptRoot 'tools\prepare_project.py')
if ($LASTEXITCODE -ne 0) { throw 'Project validation failed' }
foreach ($run in @('syn_1', 'phy_1')) {
    $runDir = Join-Path $PSScriptRoot ('td_project\camera_to_dsi_display_Runs\' + $run)
    Push-Location -LiteralPath $runDir
    try {
        $stageScript = (Join-Path $PSScriptRoot 'tools\build_stage.tcl').Replace('\', '/')
        & $td $stageScript *> build_console.log
        if ($LASTEXITCODE -ne 0) { throw ('TD failed: ' + $run) }
        $log = Get-Content -LiteralPath build_console.log -Raw
        if ($log -match '(?mi)\bERROR\s*:|license checkout failed' -or $log -notmatch 'FUSION_BUILD_STAGE_PASS') { throw ('Inspect TD log: ' + $run) }
    } finally { Pop-Location }
}
Write-Output 'BUILD_STAGES_DONE_VERIFY_FINAL_TIMING_BEFORE_EXPORT'
