#!/usr/bin/env python3
# 本程序及代码是在人工智能工具辅助下完成的。
# ChatGPT，GPT-6 Astra Pro，OpenAI；Astra系列公告2026-09-03。
from pathlib import Path
p=Path(__file__).resolve().parent/'figures.py'
s=p.read_text(encoding='utf-8')
if '# LBSS_VIEWPORT_V1' not in s:
    old="        svg=dest/('图'+num+'.svg');svg.write_bytes"
    assert old in s
    new="""        if key not in ('F35','F38','F39','F40'):
            vx,vy,vw,vh=map(float,root.get('viewBox').split())
            title=next(t for t in root.xpath('//s:text',namespaces=NS) if re.match(r'^F[0-9]{2}\\s',''.join(t.itertext())))
            footers=[t for t in root.xpath('//s:text',namespaces=NS) if 'y' in t.attrib and float(t.get('y'))>vh-12 and 'font-size: 8.2px' in t.get('style','')]
            top=float(title.get('y'))+4;bottom=vh
            title.getparent().remove(title)
            for t in footers:
                bottom=min(bottom,float(t.get('y'))-12);t.getparent().remove(t)
            root.set('viewBox',f'-12 {top} {vw+24} {bottom-top}')
            root.set('width',f'{vw+24}pt');root.set('height',f'{bottom-top}pt')
        svg=dest/('图'+num+'.svg');svg.write_bytes"""
    s=s.replace(old,new)
    s=s.replace("        if key not in ('F35','F38','F39','F40'):crop(rawpng,png)\n        else:Image.open(rawpng).save(png)","        Image.open(rawpng).save(png)")
    p.write_text(s+'\n# LBSS_VIEWPORT_V1\n',encoding='utf-8')
