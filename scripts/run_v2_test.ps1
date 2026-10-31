# v2 extraction: 3 runs per development paper (P01-P03 only; never the validation papers), then vote and score.
param([string]$Root = "D:\new papers", [string]$Tag = "v2", [int]$Runs = 3)
$dir = "$Root\papers\llm_v2"
New-Item -ItemType Directory -Force $dir | Out-Null
foreach ($i in 1..$Runs) {
    Get-ChildItem "$Root\papers\pdf\P0*.pdf" | ForEach-Object {
        $out = "$dir\$($_.BaseName)__$($Tag)_r$i.json"
        if (-not (Test-Path $out)) { python -u "$PSScriptRoot\extract_v2.py" $_.FullName $out }
    }
}
python "$PSScriptRoot\vote_v2.py" $dir $Tag "$($Tag)vote"
python "$PSScriptRoot\score_v2.py" $dir $Tag "$($Tag)vote"
