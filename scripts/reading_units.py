"""Validate scientific reading units before making an offline reader."""
import re


def source_text(value):
    if isinstance(value,str):
        return value.strip()
    return ''.join(t if isinstance(t,str) else str(t.get('text',t.get('label',''))) for t in value)


def validate_units(data):
    language=data['meta'].get('original_language','en')
    names=[v.get('name','').strip() for key in ('authors','affiliations') for v in data['meta'].get(key,[]) if isinstance(v,dict)]
    names=sorted({x for x in names if len(x)>=2},key=len,reverse=True)
    byline=re.compile('|'.join(re.escape(x) for x in names),re.I) if names else None
    previous=None
    for section in data['sections']:
        if section.get('kind')=='bibliography':
            previous=None
            continue
        for block in section.get('blocks',[]):
            pairs=block.get('pairs',[])
            if not pairs:continue
            if not block.get('summary') and not any(n.get('label') in ('本段小结','段落小结') for n in block.get('notes',[])):
                raise ValueError('正文缺少中文小结')
            for pair in pairs:
                current=source_text(pair[language])
                if byline and byline.search(current):
                    rest=byline.sub(' ',current)
                    if re.fullmatch(r'(?:[\W\d_]|\b(?:and|[a-d])\b|和|与)*',rest,re.I):
                        raise ValueError('题头中的署名或单位被单列为正文，请核对原稿：'+current[:95])
                if previous:
                    left=previous.rstrip()
                    right=current.lstrip()
                    broken_name=(language=='en' and re.search(r'\b(?:[Cc]ode for|[Ss]tandard for|[Gg]uidelines for)\b[^.!?]{0,100}$',left) and re.match(r'^[A-Z][a-z]+[”"]',right))
                    broken_clause=(language=='en' and re.search(r'\b(?:of|the|between|with|to|from|because|caused by|subjected to|compared with)[,\s]*$',left,re.I) and re.match(r'[a-z]',right))
                    open_title=(language=='zh' and left.count('《')>left.count('》') and '》' in right)
                    if broken_name or broken_clause or open_title:
                        raise ValueError('发现疑似跨句组断句，请对照原页合并为一个完整句对：'+left[-65:]+' | '+right[:65])
                previous=current
                if not block.get('boundary_review') and re.match(r'^\s*(?:Corresponding author\s*(?:at\b|:)|E-mail address\s*:|(?:[a-z1-9][ .]?)?(?:School|Department) of .{1,100}(?:University|Institute)|作者简介[：:]|收稿日期[：:])',current,re.I):
                    raise ValueError('疑似题录混入正文，请核对原稿：'+current[:95])
