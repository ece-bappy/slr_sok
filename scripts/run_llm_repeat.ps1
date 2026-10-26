# Run denoised + reasoning extraction N times per PDF in papers\pdf (tags r1..rN).
param([string]$Root = "D:\new papers", [string]$Tag = "fix", [int]$Runs = 2)
$script = Join-Path $PSScriptRoot "llm_extract.py"
foreach ($i in 1..$Runs) {
    Get-ChildItem "$Root\papers\pdf\*.pdf" | ForEach-Object {
        $out = "$Root\papers\llm\$($_.BaseName)__$($Tag)_r$i.json"
        if (-not (Test-Path $out)) { python $script $_.FullName $out --think }
    }
}
"ALLDONE"
