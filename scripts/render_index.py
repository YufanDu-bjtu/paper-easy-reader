"""Build an offline subject and related-study index from editor-reviewed records."""
import argparse
import json
from html import escape
from pathlib import Path
from urllib.parse import quote

def render(records,root):
    def e(value):return escape(value,quote=True)
    items={r['id']:r for r in records}
    if len(items)!=len(records):raise ValueError('文献 ID 重复')
    for r in records:
        if not r.get('subjects'):raise ValueError('请按研究对象和具体问题标注文献主题')
        f=(root/r['file']).resolve();f.relative_to(root.resolve())
        if not f.is_file():raise ValueError('读本文件缺失 '+r['file'])
        for rel in r.get('related',[]):
            if rel['id'] not in items or rel['id']==r['id'] or not rel.get('comparison'):raise ValueError('类似研究缺少有效目标或比较依据')
    subjects=sorted({s for r in records for s in r['subjects']})
    cards=[]
    for r in sorted(records,key=lambda x:not x.get('direct',False)):
        peers=''.join('<li><a href="#work-'+e(p['id'])+'">'+e(items[p['id']]['title'])+'</a>　'+e(p['comparison'])+'</li>' for p in r.get('related',[]))
        labels=''.join('<span>'+e(s)+'</span>' for s in r['subjects'])
        cards.append(f'<article id="work-{e(r["id"])}" data-subjects="{e(json.dumps(r["subjects"],ensure_ascii=False))}"><h2><a href="{quote(r["file"])}">{e(r["title"])}</a></h2><p>'+labels+'</p>'+('<ul>'+peers+'</ul>' if peers else '')+'</article>')
    opts=''.join('<option>'+e(s)+'</option>' for s in subjects)
    return '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>研究索引</title><style>
    body{margin:2rem auto;padding:0 1rem;max-width:66rem;color:#243a30;background:#fbf9f2;font:16px/1.65 system-ui,sans-serif}header{display:flex;align-items:center;gap:1rem;flex-wrap:wrap}input,select{font:inherit;padding:.4em;max-width:100%}article{border-top:1px solid #c7d1c7;padding:1.15rem 0}h2{font:600 1.1rem/1.4 system-ui}a{color:#165d50}article span{margin-right:.6rem;font-size:.88rem}li{margin:.35rem 0}[hidden]{display:none}</style>
    <header><h1>研究索引</h1><label>研究主题 <select id="subject"><option value="">全部主题</option>'''+opts+'''</select></label><label>检索 <input id="q" type="search"></label></header>'''+''.join(cards)+'''
    <script>const records=[...document.querySelectorAll('article')],s=document.querySelector('#subject'),q=document.querySelector('#q');function filter(){for(const r of records)r.hidden=(s.value&&!JSON.parse(r.dataset.subjects).includes(s.value))||(q.value&&!r.textContent.toLowerCase().includes(q.value.toLowerCase()));}s.onchange=filter;q.oninput=filter;</script></html>'''

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('records',type=Path);ap.add_argument('output',type=Path);args=ap.parse_args()
    result=render(json.loads(args.records.read_text('utf8')),args.output.parent)
    args.output.write_text(result,'utf8')
