#!/usr/bin/env python3
# 本程序及代码是在人工智能工具辅助下完成的。
# ChatGPT，GPT-6 Astra Pro，OpenAI；Astra系列公告日期2026-09-03。
# 仅整理文件和注释；不运行打包的求解器或评价器。
from __future__ import annotations
import ast, hashlib, json, shutil, zipfile
from pathlib import Path

COMMENT='''# 本程序及代码是在人工智能工具辅助下完成的。
# 本次工具：ChatGPT，GPT-6 Astra Pro，OpenAI。
# Astra系列公告日期：2026-09-03（Pro未另列发布日期）。
# 本次辅助范围：注释整理、静态阅读与语法树一致性核对；未运行本程序。
# 历史开发工具记录见论文附录D；本次型号不替代未留存的历史型号。
'''

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

ENTRY=COMMENT+'''"""Neutral public entry for the archived LBSS algorithm. No execution during packaging."""
from pathlib import Path
import argparse, subprocess, sys

def main():
    ap=argparse.ArgumentParser(description='LBSS multicore scheduling')
    ap.add_argument('--graph',type=Path,required=True)
    ap.add_argument('--cores',type=int,required=True)
    ap.add_argument('--scene',choices=['A','B','L2'],required=True)
    ap.add_argument('--budget',type=float,default=600)
    ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args()
    if not a.graph.is_file():ap.error('Original official input graph not found: '+str(a.graph))
    if a.cores<1 or a.budget<=0:ap.error('cores and budget must be positive')
    root=Path(__file__).resolve().parent/'engine'
    cmd=[sys.executable,'-B','-S',str(root/'round12_src/solve_round12.py'),str(a.graph.resolve()),'-n',str(a.cores),'--scene',a.scene,'--profile','full','--budget',str(a.budget),'--out',str(a.out.resolve())]
    return subprocess.call(cmd)
if __name__=='__main__':raise SystemExit(main())
'''

RECOMPUTE=COMMENT+'''"""Frozen-table statistics only. Does not import program/ or an evaluator."""
from pathlib import Path
from statistics import median
import csv, json, hashlib
root=Path(__file__).resolve().parents[1]
v=root/'results/verification.json';q=root/'results/tables/Q1_per_case.csv'
r=[x for x in json.loads(v.read_text(encoding='utf-8'))['checks'] if x['kind']=='selected']
assert len(r)==1400
result={'scope':'Frozen-table read-only recomputation; selected configurations, not runtime gate frequency','scenes':{}}
for scene in ('A','B','L2'):
    z=[x for x in r if x['scene']==scene]
    result['scenes'][scene]={'total':len(z),'certificates_le_3pct':sum(x['compute_gap_upper_bound']<=.03 for x in z),'five_core_median_gap':median(x['compute_gap_upper_bound'] for x in z if x['cores']==5)}
sums={}
with q.open(encoding='utf-8-sig') as f:
    for row in csv.DictReader(f):sums[row['case']]=sums.get(row['case'],0)+float(row['wall_seconds'])
result['A_successful_wall_sum']={'median':median(sums.values()),'above_600':sum(x>600 for x in sums.values()),'per_case':sums,'excludes':'Unrecorded failed-attempt elapsed time; not concurrent batch duration'}
result['sources']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (v,q)}
print(json.dumps(result,ensure_ascii=False,indent=2))
'''

EXPORT=r'''# 本脚本由ChatGPT（GPT-6 Astra Pro，OpenAI；Astra系列公告2026-09-03）辅助编写。
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
'''

def package_support(base,here,statistics):
    root=here/'out/支撑材料';root.mkdir(parents=True,exist_ok=True)
    engine=root/'program/engine';source=base/'reproduction/NPU_R12'
    custom=official=0;entries=[]
    for p in sorted(source.rglob('*')):
        if not p.is_file() or '__pycache__' in p.parts:continue
        rel=p.relative_to(source);dst=engine/rel;dst.parent.mkdir(parents=True,exist_ok=True)
        if p.suffix=='.py' and rel.parts[0]!='official':
            old=p.read_text(encoding='utf-8-sig');new=COMMENT+old
            assert ast.dump(ast.parse(old),include_attributes=False)==ast.dump(ast.parse(new),include_attributes=False),str(rel)
            dst.write_text(new,encoding='utf-8');custom+=1
        else:
            shutil.copy2(p,dst)
            assert sha(p)==sha(dst)
            if p.suffix=='.py':official+=1
        entries.append({'path':dst.relative_to(root).as_posix(),'source_path':str(rel),'source_sha256':sha(p),'sha256':sha(dst),'change':'AI comment only; AST identical' if p.suffix=='.py' and rel.parts[0]!='official' else 'byte-identical'})
    assert custom==58 and official==10,(custom,official)
    (root/'program/solve.py').write_text(ENTRY,encoding='utf-8')
    (root/'analysis').mkdir(exist_ok=True);(root/'analysis/recompute.py').write_text(RECOMPUTE,encoding='utf-8')
    (root/'data').mkdir(exist_ok=True);shutil.copy2(source/'official/data/config.txt',root/'data/config.txt')
    # Preserve every existing archived table and raw data file in the scoped publication package.
    publication=base/'publication'
    for name in ('tables','sources'):
        if (publication/name).exists():shutil.copytree(publication/name,root/'results'/name,dirs_exist_ok=True)
    shutil.copy2(publication/'sources/closeout/results/verification.json',root/'results/verification.json')
    (root/'analysis/补报统计.json').write_text(json.dumps(statistics,ensure_ascii=False,indent=2))
    (root/'analysis/字段命名映射.json').write_text(json.dumps({'archival_R12':'LBSS','archival_C3':'SCB','policy':'Frozen raw CSV/JSON keys and numbers remain untouched; public paper uses formal names.'},ensure_ascii=False,indent=2))
    needed={'official_input_graphs_present':len(list((source/'official/data').glob('case_*.json'))),'full_selected_plan_files_present':len(list(source.rglob('selected_plan.json'))),'status':'CODE_AND_ARCHIVED_TABLES_PACKAGED; complete replay inputs not present in scoped source snapshot','required_from_official_originals':['100 original case_*.json graphs','Actual selected two-field plans and complete official raw outputs/traces for independent replay as needed'],'note':'Existing answer/team-share archives were inventoried; they are document/table packages, not a complete graph-and-plan replay archive.'}
    (root/'运行与材料清单.md').write_text('''# 支撑材料

## 入口与目录

`program/solve.py`为中性名称入口；`program/engine/`保留归档模块布局以维持导入与逻辑一致。正文不再使用这些历史迭代名称作为算法名称。

```text
python program/solve.py --graph data/case_001.json --cores 2 --scene A --budget 600 --out work/case001_A2
python analysis/recompute.py
```

第一条仅供具备原始输入后复现实验，本次没有执行；第二条只重算已有表格。

## 完整性边界

已提供58个补充AI注释的自编Python文件、10个逐字节保留的官方Python文件、固定配置和全部publication范围内的结果材料。自编文件AST与来源相同。新增入口仅整理参数传递，不改算法。

所取仓库范围没有100张原始计算图，也未含完整selected_plan.json集合；不能把本包称为已经具备全部输入的独立重评包。须将官方原始图按清单补齐，并由队伍核对实际方案及完整官方输出。归档的SHA256只能用来核对实际文件，不能替代缺失文件。

## AI使用与数值

自编程序注释披露本次工具为ChatGPT / GPT-6 Astra Pro / OpenAI（Astra系列公告2026-09-03）；历史模型记录未被本次型号替代。官方程序未添加注释，保持原样。所有原始CSV/JSON数值和字段保持不变，文稿中的LBSS/SCB名称由字段映射说明对应。
''',encoding='utf-8')
    manifest={'custom_python_AI_annotated':custom,'official_python_byte_identical':official,'custom_AST_identical':True,'solver_or_evaluator_executed':False,'input_completeness':needed,'engine_files':entries,'files':[]}
    for p in sorted(root.rglob('*')):
        if p.is_file():manifest['files'].append({'path':p.relative_to(root).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)})
    (root/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    zpath=here/'out/支撑材料.zip'
    with zipfile.ZipFile(zpath,'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(root.rglob('*')):
            if p.is_file():z.write(p,Path('支撑材料')/p.relative_to(root))
    (here/'out/Windows_Word正式导出.ps1').write_text(EXPORT,encoding='utf-8-sig')
    return {'custom_python_AI_annotated':custom,'official_python_byte_identical':official,'custom_AST_identical':True,'archive_sha256':sha(zpath),'input_completeness':needed}
