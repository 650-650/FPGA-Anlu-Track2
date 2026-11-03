$ErrorActionPreference = 'Stop'
$td = if ($env:TD_COMMANDS_PROMPT) { $env:TD_COMMANDS_PROMPT } else { (Get-Command td_commands_prompt.exe -ErrorAction SilentlyContinue).Source }
if (-not $td -or -not (Test-Path -LiteralPath $td -PathType Leaf)) { throw 'Set TD_COMMANDS_PROMPT to the installed td_commands_prompt.exe path, or add it to PATH.' }
& (Join-Path $PSScriptRoot 'prepare_for_build.ps1')
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
