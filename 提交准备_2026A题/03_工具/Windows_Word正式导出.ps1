# 本脚本由ChatGPT（GPT-6 Astra Pro，OpenAI；Astra系列公告2026-09-03）辅助编写。
# 仅在已授权且安装Microsoft Word及规定字体的Windows计算机上执行。
param([Parameter(Mandatory=$true)][string]$Docx,[Parameter(Mandatory=$true)][string]$Pdf)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$fonts = New-Object System.Drawing.Text.InstalledFontCollection
$names = $fonts.Families | ForEach-Object { $_.Name }
if (-not (($names -contains 'SimSun') -or ($names -contains '宋体'))) { throw '缺少宋体，停止正式导出。' }
if (-not (($names -contains 'SimHei') -or ($names -contains '黑体'))) { throw '缺少黑体，停止正式导出。' }
$inputPath = (Resolve-Path -LiteralPath $Docx).Path
$outputPath = [System.IO.Path]::GetFullPath($Pdf)
if (Test-Path -LiteralPath $outputPath) { throw '目标PDF已存在，请指定新路径以保留已核验版本。' }
$word=$null; $doc=$null
try {
  $word=New-Object -ComObject Word.Application
  $word.Visible=$false; $word.DisplayAlerts=0
  $doc=$word.Documents.Open($inputPath,$false,$true)
  $doc.Repaginate()
  $doc.ExportAsFixedFormat($outputPath,17)
  $pages=$doc.ComputeStatistics(2)
  Write-Output "Word导出完成；页数=$pages；PDF=$outputPath"
  Get-FileHash -LiteralPath $outputPath -Algorithm SHA256
} finally {
  if ($doc) { $doc.Close(0) }
  if ($word) { $word.Quit() }
}
