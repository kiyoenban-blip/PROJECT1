"""Deterministic version comparison with exact moves and typed changes."""
import re
from collections import Counter
from difflib import SequenceMatcher
from .rules import groups,key_text,emit
from .tables import DATE


def change_type(a,b):
    if DATE.findall(a)!=DATE.findall(b):
        return 'DATE_CHANGED'
    if re.findall(r'주석\s*\d+',a)!=re.findall(r'주석\s*\d+',b):
        return 'NOTE_CHANGED'
    if re.findall(r'[+-]?\d[\d,.]*',a)!=re.findall(r'[+-]?\d[\d,.]*',b):
        return 'NUMERIC_CHANGED'
    if ('주식회사' in a or '주식회사' in b) and a!=b:
        return 'COMPANY_CHANGED'
    return 'TEXT_CHANGED'


def changes(old,new):
    rows=[]; a=dict(old.texts); b=dict(new.texts)
    for loc in list(a):
        if loc in b and a[loc]==b[loc]:
            del a[loc]; del b[loc]
    ac=Counter(a.values()); bc=Counter(b.values())
    for loc,text in list(a.items()):
        if ac[text]==bc[text]==1:
            dest=next(k for k,v in b.items() if v==text)
            rows.append({'type':'MOVED','old_location':loc,'location':dest,'old':text,'new':text})
            del a[loc]; del b[dest]
    for loc,text in list(a.items()):
        if loc in b:
            rows.append({'type':change_type(text,b[loc]),'old_location':loc,'location':loc,'old':text,'new':b.pop(loc)})
            del a[loc]
    rows.extend({'type':'DELETED','old_location':k,'location':None,'old':v,'new':None} for k,v in a.items())
    rows.extend({'type':'ADDED','old_location':None,'location':k,'old':None,'new':v} for k,v in b.items())
    ag,bg=groups(old),groups(new)
    for key in sorted(set(ag)|set(bg)):
        av=sorted({str(f.value) for f in ag.get(key,[])}); bv=sorted({str(f.value) for f in bg.get(key,[])})
        if av!=bv:
            rows.append({'type':'FACT_ADDED' if not av else 'FACT_DELETED' if not bv else 'FACT_CHANGED',
                'location':key_text(key),'old':';'.join(av),'new':';'.join(bv)})
    for i,(a,b) in enumerate(zip(old.tables,new.tables)):
        if a['rows']!=b['rows']:
            rows.append({'type':'TABLE_CHANGED','location':b['location'],'old':a['rows'],'new':b['rows']})
    return rows


def unexpected_changes(old,new,references):
    ag,bg=groups(old),groups(new)
    refs=[groups(r) for r in references]
    for key, current in bg.items():
        before=ag.get(key,[])
        supporting=[f for r in refs for f in r.get(key,[])]
        if not before or not supporting:
            continue
        av={f.value for f in before}; bv={f.value for f in current}; rv={f.value for f in supporting}
        if len(av)!=1 or len(bv)!=1 or len(rv)!=1:
            continue
        anchor='UNEXPECTED_CHANGE|'+key_text(key)
        new.checked.append(anchor)
        if av==rv and bv!=rv:
            emit(new,'UNEXPECTED_CHANGE',key_text(key),'이전 버전과 근거자료는 일치하지만 현재 금액만 변경되었습니다.',
                str(current[0].value),str(before[0].value),category='VERSION',severity='HIGH',confidence=.95,
                section=current[0].location,evidence=[f'{f.source} [{f.location}]: {f.value}' for f in before+current+supporting],
                suggestion='변경 사유 및 근거자료의 최신성을 확인하십시오.')
