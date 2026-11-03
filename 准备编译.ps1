$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$hdl = Join-Path $root 'user_source\hdl_source'
$names = @('image_curve_rom.v','isp\stylize_v5_96.v','display_contrast.v')
$pattern = '"[^"\r\n]*/(curve_srgb|curve_gain|curve_gain_scaled|median_majority|display_tone)\.dat"'
foreach ($name in $names) {
    $file = Join-Path $hdl $name
    $text = [IO.File]::ReadAllText($file, [Text.Encoding]::UTF8)
    $updated = [regex]::Replace($text, $pattern, [Text.RegularExpressions.MatchEvaluator]{ param($m)
        $data = Join-Path $hdl ($m.Groups[1].Value + '.dat')
        if (-not (Test-Path -LiteralPath $data -PathType Leaf)) { throw "Missing ROM data: $data" }
        '"' + $data.Replace('\','/') + '"'
    })
    if ($updated -ne $text) { [IO.File]::WriteAllText($file, $updated, (New-Object Text.UTF8Encoding($false))) }
}
$project = Join-Path $root 'td_project\camera_to_dsi_display.al'
$text = [IO.File]::ReadAllText($project, [Text.Encoding]::UTF8)
$projectDir = (Join-Path $root 'td_project').Replace('\','/')
$updated = [regex]::Replace($text, '<Project Version="3" Minor="2" Path="[^"]+">', ('<Project Version="3" Minor="2" Path="' + $projectDir + '">'), 1)
if ($updated -ne $text) { [IO.File]::WriteAllText($project, $updated, (New-Object Text.UTF8Encoding($false))) }
$missing = @([regex]::Matches($updated, '<File Path="([^"]+)"') | ForEach-Object {
    $candidate = Join-Path (Join-Path $root 'td_project') $_.Groups[1].Value
    if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) { $candidate }
})
if ($missing.Count) { throw "Missing project input(s): $($missing -join ', ')" }
Write-Host 'ROM paths and project references are ready. Reopen td_project\camera_to_dsi_display.al, then run synthesis.'
