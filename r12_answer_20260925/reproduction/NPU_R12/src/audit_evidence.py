"""Audit completed results without changing official code or evaluation outputs."""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys


def sha(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()


def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--official',type=Path,required=True)
    ap.add_argument('--root',type=Path,required=True)
    args=ap.parse_args();root=args.root.resolve();off=args.official.resolve();sys.path.insert(0,str(off/'code'))
    from evaluation_validation import read_evaluation_config
    from traffic_model import predict_partition_bytes
    config=read_evaluation_config(str(off/'data/config.txt'))
    plans={sha(p):p for p in (root/'plans').rglob('*.json') if not p.name.endswith('.meta.json') and p.name!='manifest.json'}
    verified=0;traffic_verified=0;counts=Counter();graphs={}
    raw_hashes=set()
    for p in (root/'results').rglob('*.json'):
        if p.name.endswith('.official.json') or p.name.endswith('.trace.json'):continue
        r=json.loads(p.read_text(encoding='utf-8'))
        if 'status' not in r or 'graph_sha256' not in r or 'mode' not in r:continue
        counts[r['status']]+=1
        if r['status']!='ok':continue
        graph=off/'data'/(r['case']+'.json')
        assert sha(graph)==r['graph_sha256'],('graph hash',p)
        assert sha(off/'data/config.txt')==r['config_sha256'],('config hash',p)
        raw=p.with_name(r['official_result_file'])
        assert sha(raw)==r['official_result_sha256'],('result hash',p)
        official=json.loads(raw.read_text(encoding='utf-8'))
        assert r['makespan']==official['makespan'],('makespan',p)
        move=r['data_movement_bytes']
        assert move['scheduled_copy_bytes']==move['original_graph_copy_bytes']+move['added_copy_bytes'],('total',p)
        assert move['added_copy_bytes']==move['partition_added_copy_bytes']+move['spill_added_copy_bytes'],('parts',p)
        for mem in (r.get('memory_peak_by_core') or {}).values():
            for kind,cap in config['capacity'].items():assert mem[kind]<=cap,('capacity',p)
        c=r.get('cache_stats')
        if c:
            den=c['hit_bytes']+c['miss_bytes'];expected=c['hit_bytes']/den if den else 0
            assert abs(c['hit_rate']-expected)<1e-12,('cache byte fraction',p)
        ph=r.get('plan_sha256')
        if ph in plans:
            if r['case'] not in graphs:graphs[r['case']]=json.loads(graph.read_text(encoding='utf-8'))
            prediction=predict_partition_bytes(graphs[r['case']],json.loads(plans[ph].read_text(encoding='utf-8')),r['mode'])
            assert prediction['predicted_partition_added_copy_bytes']==move['partition_added_copy_bytes'],('partition bytes',p)
            traffic_verified+=1
        verified+=1;raw_hashes.add(r['official_result_sha256'])
    manifest=json.loads((root/'plans/all/manifest.json').read_text(encoding='utf-8'))
    for r in manifest['rows']:
        assert r['status']=='structural_ok',('plan construction',r)
        assert sha(root/'plans/all'/r['plan_file'])==r['plan_sha256'],('plan hash',r)
    report={'successful_result_records_checked':verified,'unique_official_result_hashes':len(raw_hashes),
            'pre_spill_traffic_predictions_checked':traffic_verified,'status_counts':dict(counts),
            'plan_records_checked':len(manifest['rows']),'input_hashes_and_result_hashes':'pass',
            'copy_decomposition':'pass','memory_capacity':'pass','cache_byte_fraction':'pass',
            'scope':'Checks recorded outputs and pre-spill predictor consistency, not optimality or hardware truth.'}
    (root/'reports/evidence_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))
    return 0


if __name__=='__main__':raise SystemExit(main())
