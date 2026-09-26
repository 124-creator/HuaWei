$ErrorActionPreference = "Continue"
$p = [System.IO.File]::ReadAllText((Join-Path $PSScriptRoot "export_params.json"), [System.Text.Encoding]::UTF8)
$p = $p.TrimStart([char]0xFEFF) | ConvertFrom-Json
$src = $p.src
$dst = $p.dst
if (-not (Test-Path $src)) { Write-Output ("SRC NOT FOUND: " + $src); exit 1 }
if (Test-Path $dst) { Remove-Item $dst -Force }
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
$doc = $word.Documents.Open($src, $false, $true)
$doc.SaveAs2($dst, 17)
$doc.Close($false)
try { $word.Quit() } catch { Write-Output "quit warning ignored" }
if (Test-Path $dst) { Write-Output ("OK size MB: " + [math]::Round((Get-Item $dst).Length / 1MB, 2)) } else { Write-Output "FAILED" }
