# Run the Gemma extraction test on every PDF in papers\pdf, with and without reasoning.
param([string]$Root = "D:\new papers", [string]$Tag = "denoised")
$script = Join-Path $PSScriptRoot "llm_extract.py"
Get-ChildItem "$Root\papers\pdf\*.pdf" | ForEach-Object {
    foreach ($mode in "think", "no-think") {
        $out = "$Root\papers\llm\$($_.BaseName)__$($mode)__$Tag.json"
        python $script $_.FullName $out "--$mode"
    }
}
"ALLDONE"
