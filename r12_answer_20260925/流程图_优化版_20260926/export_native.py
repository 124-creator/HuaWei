"""Export editable sources using draw.io Desktop, then verify final bytes.
Only this directory is writable. No manuscript or solver execution.
Native print scaling is removed by a measured uniform vector transformation.
"""
from pathlib import Path
from collections import Counter
import hashlib,json,re,subprocess,shutil,sys
import fitz
from PIL import Image,ImageChops,ImageStat
from build import OUT,BASE,MMPT,parse_drawio,Rich

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def cjk(s):return Counter(c for c in s if '\u4e00'<=c<='\u9fff')
def main():
    exe=shutil.which('drawio') or shutil.which('draw.io')
    if not exe:raise RuntimeError('draw.io Desktop executable missing')
    native=OUT/'qa'/'native';native.mkdir(exist_ok=True,parents=True)
    reports=[];proof=fitz.open()
    for p in sorted((OUT/'drawio').glob('*.drawio')):
        s=parse_drawio(p);target=native/(p.stem+'.pdf')
        cmd=['xvfb-run','-a',exe,'--no-sandbox','--disable-gpu','--export','--format','pdf','--size','page','--timeout','60','--output',str(target),str(p)]
        proc=subprocess.run(cmd,capture_output=True,text=True,timeout=100)
        (native/(p.stem+'.log')).write_text(proc.stdout+'\n'+proc.stderr,encoding='utf-8')
        if proc.returncode!=0 or not target.exists():raise RuntimeError('draw.io native export failed: '+p.name+'\n'+proc.stderr[-1500:])
        raw_doc=fitz.open(target);assert len(raw_doc)==1,(p.name,'page count',len(raw_doc))
        raw_page=raw_doc[0]
        # Chromium PDF printing applies a small uniform scale and page offset.
        # Measure it from the first explicit rectangle, not from text widths.
        # A PDF Form XObject preserves native text, embedded fonts and vector paths.
        anchor=next(n for n in s.nodes if n['shape']=='rect')
        native_box=next(x['rect'] for x in raw_page.get_drawings() if x.get('fill') is not None and x.get('color') is not None and x['rect'].width>20 and x['rect'].height>10)
        sx=native_box.width/(anchor['w']*MMPT);sy=native_box.height/(anchor['h']*MMPT)
        assert abs(sx-sy)<0.002,('Unexpected nonuniform native scale',sx,sy)
        scale=(sx+sy)/2
        ox=native_box.x0-anchor['x']*MMPT*scale;oy=native_box.y0-anchor['y']*MMPT*scale
        clip=fitz.Rect(ox,oy,ox+s.w*MMPT*scale,oy+s.h*MMPT*scale)
        assert raw_page.rect.contains(clip),('Native content bounds',raw_page.rect,clip)
        d=fitz.open();pg=d.new_page(width=s.w*MMPT,height=s.h*MMPT)
        pg.show_pdf_page(pg.rect,raw_doc,0,clip=clip,keep_proportion=False)
        dest=OUT/'exports'/(p.stem+'.pdf');d.save(dest,garbage=4,deflate=True)
        errors=[];w,h=pg.rect.width/MMPT,pg.rect.height/MMPT
        if abs(w-s.w)>.02 or abs(h-s.h)>.02:errors.append(['page_dimensions_mm',w,h,s.w,s.h])
        fonts=subprocess.check_output(['pdffonts',str(dest)],text=True)
        for line in fonts.splitlines()[2:]:
            flags=re.search(r'\s(yes|no)\s+(yes|no)\s+(yes|no)\s+\d',line)
            if not flags or flags.group(1)!='yes' or flags.group(2)!='yes':errors.append(['font_not_embedded_or_subset',line])
            if 'Type 3' in line:errors.append(['type3_font',line])
        if 'WenQuanYi' not in fonts:errors.append(['wrong_chinese_font',fonts])
        if 'LiberationSerif' not in fonts:errors.append(['wrong_latin_font',fonts])
        if pg.get_images():errors.append(['raster_in_vector_pdf',len(pg.get_images())])
        expected=''
        for n in s.nodes:
            r=Rich();r.feed(n['text']);expected+=''.join(run[0] for row in r.rows for run in row)
        extracted=pg.get_text();missing=cjk(expected)-cjk(extracted);extra=cjk(extracted)-cjk(expected)
        if missing or extra:errors.append(['native_text_coverage',dict(missing),dict(extra)])
        if '\ufffd' in extracted:errors.append(['replacement_character'])
        allowed=[fitz.Rect(n['x']*MMPT,n['y']*MMPT,(n['x']+n['w'])*MMPT,(n['y']+n['h'])*MMPT)+(-1,-1,1,1) for n in s.nodes if n['text']]
        spans=[]
        for block in pg.get_text('dict')['blocks']:
            for line in block.get('lines',[]):
                for sp in line['spans']:
                    bb=fitz.Rect(sp['bbox']);spans.append(sp)
                    if sp['text'].strip() and not any(a.contains(bb) for a in allowed):errors.append(['native_text_outside_label',sp['text'],list(bb)])
        sizes=sorted(set(round(sp['size'],3) for sp in spans if sp['text'].strip()))
        body_cjk=[sp['size'] for sp in spans if cjk(sp['text']) and sp['size']<11]
        if body_cjk and min(body_cjk)<8.98:errors.append(['body_font_too_small',min(body_cjk)])
        # Outlined SVG avoids external fonts and unsupported foreignObject text.
        svg=pg.get_svg_image(text_as_path=True)
        svg=re.sub(r'width="[^"]+"',f'width="{s.w}mm"',svg,count=1)
        svg=re.sub(r'height="[^"]+"',f'height="{s.h}mm"',svg,count=1)
        if re.search(r'<(?:text|image|foreignObject)\b',svg):errors.append(['svg_not_portable_vector'])
        (OUT/'exports'/(p.stem+'.svg')).write_text(svg,encoding='utf-8')
        pix=pg.get_pixmap(dpi=600,alpha=False);pix.set_dpi(600,600);pix.save(OUT/'exports'/(p.stem+'.png'))
        prev=pg.get_pixmap(dpi=180,alpha=False);prev.save(OUT/'qa'/(p.stem+'_native.png'))
        im=Image.open(OUT/'exports'/(p.stem+'.png'));dpi=im.info.get('dpi',(0,0))
        if min(dpi)<599:errors.append(['low_dpi',dpi])
        Image.open(OUT/'qa'/(p.stem+'_native.png')).convert('L').save(OUT/'qa'/(p.stem+'_grayscale.png'))
        # Independent PDF decoding/rendering checks font portability.
        prefix=native/(p.stem+'_poppler')
        pr=subprocess.run(['pdftoppm','-singlefile','-r','180','-png',str(dest),str(prefix)],capture_output=True,text=True,timeout=60)
        if pr.returncode or pr.stderr.strip():errors.append(['poppler_warning',pr.returncode,pr.stderr])
        a=Image.open(OUT/'qa'/(p.stem+'_native.png')).convert('RGB');b=Image.open(str(prefix)+'.png').convert('RGB')
        if a.size!=b.size:b=b.resize(a.size)
        mad=sum(ImageStat.Stat(ImageChops.difference(a,b)).mean)/3/255
        if mad>.04:errors.append(['renderer_parity',mad])
        proofpage=proof.new_page(width=210*MMPT,height=297*MMPT)
        proofpage.show_pdf_page(fitz.Rect(22*MMPT,25*MMPT,188*MMPT,(25+s.h)*MMPT),d,0)
        r=dict(figure=p.stem,native_export_returncode=proc.returncode,dimensions_mm=[round(w,3),round(h,3)],native_page_normalization={'uniform_scale':1/scale,'translation_pt':[ox,oy]},fonts=fonts,font_sizes_pt=sizes,body_cjk_min_pt=min(body_cjk),cjk_expected=sum(cjk(expected).values()),cjk_extracted=sum(cjk(extracted).values()),pdf_raster_images=len(pg.get_images()),png_dimensions=im.size,png_dpi=dpi,svg_text_as_paths=True,svg_foreign_objects=0,second_renderer_mad=mad,errors=errors)
        reports.append(r);print(p.stem,errors)
    proof.subset_fonts();proof.save(OUT/'qa'/'打印校样_A4_166mm.pdf',garbage=4,deflate=True)
    report=dict(base_commit=BASE,renderer='draw.io Desktop 31.5.2 -> uniform vector page normalization -> PDF/SVG paths/PNG',figures=reports,error_count=sum(len(r['errors']) for r in reports),visual_review='See separately signed-by-hash visual_review.json; machine checks are not visual review')
    (OUT/'qa'/'native_export_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    assets={p.relative_to(OUT).as_posix():sha(p) for folder in ('drawio','exports') for p in sorted((OUT/folder).glob('*')) if p.is_file()}
    (OUT/'ASSET_SHA256.json').write_text(json.dumps({'scope':'editable sources and final exports only','base_commit':BASE,'sha256':assets},ensure_ascii=False,indent=2),encoding='utf-8')
    if report['error_count']:sys.exit(2)
if __name__=='__main__':main()
