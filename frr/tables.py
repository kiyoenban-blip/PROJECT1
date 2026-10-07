"""Conservative table extraction using explicit period headers and metadata."""
import re
from decimal import Decimal, InvalidOperation
from .models import Fact

NUMERIC = re.compile(r'^\(?[+−-]?\d[\d,]*(?:\.\d+)?\)?$')
DATE = re.compile(r'(20\d{2})[.\-/년]\s*(\d{1,2})[.\-/월]\s*(\d{1,2})일?')

def compact(value):
    return re.sub(r'\s+', ' ', str(value if value is not None else '')).strip()

def parse_number(value):
    text = compact(value).replace('−','-').replace('△','-')
    if not NUMERIC.fullmatch(text):
        return None
    if text.startswith('(') and text.endswith(')'):
        text = '-'+text[1:-1]
    try:
        return Decimal(text.replace(',',''))
    except InvalidOperation:
        return None

def period(text, meta):
    t = compact(text)
    date = DATE.search(t)
    if date:
        y,m,d = date.groups()
        return f'{y}-{int(m):02d}-{int(d):02d}'
    years = re.findall(r'(?<!\d)20\d{2}(?!\d)', t)
    if len(set(years))==1:
        return years[0]
    if re.search(r'당기|당\s*연도|current',t,re.I):
        return meta.get('period')
    if re.search(r'전기|전\s*연도|prior|previous',t,re.I):
        return meta.get('prior_period')
    return None

def extract_tables(doc, config):
    for table in doc.tables:
        rows = table['rows']
        meta = dict(doc.metadata); meta.update(table.get('metadata', {}))
        header = None; columns = {}
        for i,row in enumerate(rows[:8]):
            cols = {j:period(v,meta) for j,v in enumerate(row) if j>0 and period(v,meta)}
            if cols:
                header, columns = i, cols
                break
        if header is None or not all(meta.get(k) for k in ['entity','scope','unit']):
            doc.logs.append({'rule':'TABLE_EXTRACTION','status':'NOT_VERIFIABLE','location':table['location'],
                'detail':'명확한 기간 열 및 회사/entity·범위/scope·단위/unit가 필요합니다.'})
            continue
        since_total = {j:[] for j in columns}
        for i,row in enumerate(rows[header+1:],header+1):
            if not row or not compact(row[0]):
                continue
            label=compact(row[0])
            for j, per in columns.items():
                if j>=len(row):
                    continue
                value=parse_number(row[j])
                if value is None:
                    doc.logs.append({'rule':'TABLE_VALUE','status':'NOT_VERIFIABLE',
                        'location':f'{table["location"]}:R{i+1}C{j+1}','detail':f'숫자 해석 불가(공란/대시도 0으로 추정하지 않음): {row[j]}'})
                    since_total[j]=[]
                    continue
                loc=table.get('cells',{}).get(f'{i},{j}',f'{table["location"]}:R{i+1}C{j+1}')
                doc.facts.append(Fact(concept=label,value=value,period=per,unit=meta['unit'],entity=meta['entity'],
                    scope=meta['scope'],source=doc.path,location=loc,extraction_confidence=.9))
                if config.infer_table_totals and label.replace(' ','').lower() in ('합계','총계','total','subtotal','소계'):
                    if len(since_total[j])>=2:
                        doc.calculations.append({'id':f'table:{table["location"]}:{label}:{per}:{i}',
                            'total':loc,'components':list(since_total[j]),'inferred':True})
                    since_total[j]=[]
                else:
                    since_total[j].append(loc)

def normalize_facts(doc, config):
    for f in doc.facts:
        f.raw_value = str(f.value); f.raw_unit = f.unit
        f.concept = config.concept_aliases.get(f.concept, f.concept)
        f.period = config.period_mappings.get(f.period,f.period)
        f.entity = config.entity_aliases.get(f.entity,f.entity)
        f.scope = config.scope_aliases.get(f.scope,f.scope)
        mapping = config.unit_mappings.get(f.unit)
        if mapping:
            f.value *= mapping.multiplier; f.unit = mapping.unit
