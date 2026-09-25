"""Recover exact hash-addressed historical evidence, never recreate old hashes."""
from pathlib import Path
import zipfile,csv,json,hashlib,time
ROOT=Path(__file__).resolve().parents[1];SRC=Path('/mnt/data');out=ROOT/'evidence_store';out.mkdir(exist_ok=True)
rows=list(csv.DictReader((SRC/'NPU_R8_1400项逐例结果.csv').open(encoding='utf-8-sig')))
bases=json.loads((ROOT/'stage4_reports/baselines.json').read_text())
targets={r[k] for r in rows for k in ('plan_sha256','raw_sha256') if r[k]}|{r['raw_sha256'] for r in bases}
found={};t=time.perf_counter()
archives=sorted(SRC.glob('*.zip'),key=lambda p:(p.stat().st_size,p.name))
for path in archives:
    with zipfile.ZipFile(path) as z:
        for info in z.infolist():
            if not info.filename.endswith('.json') or '/official/data/' in info.filename or '/attachment/data/' in info.filename:continue
            b=z.read(info);h=hashlib.sha256(b).hexdigest()
            if h not in targets or h in found:continue
            (out/f'{h}.json').write_bytes(b);found[h]={'archive':path.name,'member':info.filename,'bytes':len(b),'sha256':h}
    print(path.name,'found',len(found),flush=True)
coverage=[]
for r in rows:
    pc=r['plan_sha256'] in found;rc=r['raw_sha256'] in found
    e={'id':r['id'],'plan_present':pc,'raw_present':rc,'exact_pair':pc and rc,'expected_makespan':int(r['makespan'])}
    if rc:
        raw=json.loads((out/f"{r['raw_sha256']}.json").read_text());e['makespan_matches']=raw['makespan']==int(r['makespan'])
    coverage.append(e)
bcov=[{'case':b['case'],'raw_present':b['raw_sha256'] in found,'expected_makespan':b['makespan']} for b in bases]
summary={'source_csv':'NPU_R8_1400项逐例结果.csv','source_csv_sha':hashlib.sha256((SRC/'NPU_R8_1400项逐例结果.csv').read_bytes()).hexdigest(),'found_hashes':len(found),'target_hashes':len(targets),'exact_pairs':sum(r['exact_pair'] for r in coverage),'total_rows':len(rows),'baseline_raw_present':sum(r['raw_present'] for r in bcov),'coverage':coverage,'baselines':bcov,'hash_sources':found,'seconds':time.perf_counter()-t,'scope':'exact bytes recovered from mounted archives; missing remains missing'}
(ROOT/'round10_reports/historical_evidence_recovery.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2));print({k:v for k,v in summary.items() if k not in ('coverage','baselines','hash_sources')})
