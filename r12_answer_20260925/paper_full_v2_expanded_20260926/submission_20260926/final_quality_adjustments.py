#!/usr/bin/env python3
# 本程序及代码是在人工智能工具辅助下完成的。
# ChatGPT / GPT-6 Astra Pro / OpenAI；Astra系列公告2026-09-03。
from pathlib import Path
root=Path(__file__).resolve().parent
p=root/'build_submission.py';s=p.read_text(encoding='utf-8')
if '# LBSS_FINAL_LABELS_V1' not in s:
    s=s.replace("content=[ps[head].text,ps[inp].text,*lines]","content=[ps[head].text,ps[inp].text,'输出：已成功评价的最佳方案及记录；无可行结果时返回失败。',*lines]")
    s=s.replace("    patch_text(e,r'开发诊断案例','设计阶段的诊断案例')","    patch_text(e,r'开发诊断案例','设计阶段的诊断案例')\n    patch_text(e,r'优化\\s*B1','单核优化结果')")
    p.write_text(s+'\n# LBSS_FINAL_LABELS_V1\n',encoding='utf-8')
p=root/'figures.py';s=p.read_text(encoding='utf-8')
if '# LBSS_SINGLECORE_LABEL_V1' not in s:
    s=s.replace("return s.replace('，；','；').rstrip('，')","s=re.sub(r'优化\\s*B1','单核优化结果',s)\n    return s.replace('，；','；').rstrip('，')")
    p.write_text(s+'\n# LBSS_SINGLECORE_LABEL_V1\n',encoding='utf-8')
