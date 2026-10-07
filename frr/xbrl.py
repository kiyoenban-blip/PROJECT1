"""XBRL structural checks plus an isolated, offline Arelle validator."""
import json
import re
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import date,datetime
from decimal import InvalidOperation
from pathlib import Path
from lxml import etree
from .models import Fact

NS={'x':'http://www.xbrl.org/2003/instance','d':'http://xbrl.org/2006/xbrldi'}

def qname(value,node):
    value=(value or '').strip()
    if ':' in value:
        prefix,name=value.split(':',1)
        if prefix not in node.nsmap:
            raise ValueError(f'정의되지 않은 namespace: {prefix}')
        return '{'+node.nsmap[prefix]+'}'+name
    return '{'+node.nsmap[None]+'}'+value if None in node.nsmap else value

def canonical_node(node):
    return [node.tag,sorted((k,qname(v,node) if k=='dimension' else v) for k,v in node.attrib.items()),(node.text or '').strip(),[canonical_node(c) for c in node if isinstance(c.tag,str)]]

def context_key(ctx):
    entity=ctx.find('x:entity/x:identifier',NS)
    period=ctx.find('x:period',NS)
    if entity is None or not entity.text or period is None:
        raise ValueError('회사 식별자 또는 기간 누락')
    instant=period.find('x:instant',NS)
    start=period.find('x:startDate',NS); end=period.find('x:endDate',NS)
    if instant is not None and len(period)==1:
        value=(instant.text or '').strip(); datetime.fromisoformat(value.replace('Z','+00:00'))
    elif start is not None and end is not None and len(period)==2:
        a=(start.text or '').strip(); b=(end.text or '').strip()
        if datetime.fromisoformat(a.replace('Z','+00:00'))>datetime.fromisoformat(b.replace('Z','+00:00')):
            raise ValueError('시작일이 종료일보다 늦습니다.')
        value=a+'/'+b
    else:
        raise ValueError('instant 또는 startDate/endDate 기간이 필요합니다.')
    dims=[]
    for e in ctx.xpath('./x:entity/x:segment/* | ./x:scenario/*',namespaces=NS):
        if etree.QName(e).localname=='explicitMember':
            dims.append([qname(e.get('dimension'),e),qname(e.text,e)])
        else:
            dims.append(canonical_node(e))
    return f'{entity.get("scheme", "")}:{entity.text.strip()}',value,json.dumps(sorted(dims,key=str),ensure_ascii=False,separators=(',',':')) if dims else ''

def unit_key(unit):
    direct=unit.findall('x:measure',NS)
    if direct:
        return '*'.join(sorted(qname(c.text,c) for c in direct))
    numerator=unit.findall('x:divide/x:unitNumerator/x:measure',NS)
    denominator=unit.findall('x:divide/x:unitDenominator/x:measure',NS)
    if not numerator or not denominator:
        raise ValueError('유효한 Unit measure/divide가 없습니다.')
    return '*'.join(sorted(qname(c.text,c) for c in numerator))+'/'+ '*'.join(sorted(qname(c.text,c) for c in denominator))

def read_xbrl(doc,root,config):
    from .parsers import finding, number
    contexts={}; units={}
    for tag,target in [('context',contexts),('unit',units)]:
        nodes=root.findall('x:'+tag,NS)
        counts=Counter(e.get('id') for e in nodes)
        for e in nodes:
            loc=f'{tag}:{e.get("id")}'
            doc.checked.append('XBRL_ID|'+loc)
            if counts[e.get('id')]>1 or not e.get('id'):
                if not any(f.anchor=='XBRL_ID|'+loc for f in doc.findings):
                    doc.findings.append(finding(doc,'XBRL_ID',loc,'누락 또는 중복 XBRL ID',e.get('id'),category='STRUCTURE',severity='HIGH',confidence=1))
                continue
            target[e.get('id')]=e
    seen=Counter()
    for el in root.iter():
        if not isinstance(el.tag,str) or 'contextRef' not in el.attrib:
            continue
        seen[(el.tag,el.get('contextRef'),el.get('unitRef'))]+=1
        # Duplicate occurrences get unique locations; matching uses semantic facts later.
        loc=f'{el.tag}[context={el.get("contextRef")},unit={el.get("unitRef", "")}]#{seen[(el.tag,el.get("contextRef"),el.get("unitRef"))]}'
        text=(el.text or '').strip(); doc.texts[loc]=text
        ctx=contexts.get(el.get('contextRef')); unit=units.get(el.get('unitRef'))
        doc.checked.append('XBRL_REFERENCE|'+loc)
        if ctx is None or (el.get('unitRef') and unit is None):
            doc.findings.append(finding(doc,'XBRL_REFERENCE',loc,'Context 또는 Unit 참조를 찾을 수 없습니다.',dict(el.attrib),category='STRUCTURE',severity='HIGH',confidence=1))
            continue
        doc.checked.append('XBRL_CONTEXT|'+loc)
        try:
            entity,period,dimensions=context_key(ctx)
        except ValueError as e:
            doc.findings.append(finding(doc,'XBRL_CONTEXT',loc,str(e),etree.tostring(ctx).decode(),category='STRUCTURE',severity='HIGH',confidence=1))
            continue
        if el.get('{http://www.w3.org/2001/XMLSchema-instance}nil') in ('true','1'):
            doc.logs.append({'rule':'XBRL_NIL','status':'NOT_APPLICABLE','location':loc,'detail':'nil Fact: 금액 대사 제외'})
            continue
        if unit is None:
            continue
        doc.checked.append('XBRL_UNIT|'+loc)
        try:
            unit_name=unit_key(unit)
        except ValueError as e:
            doc.findings.append(finding(doc,'XBRL_UNIT',loc,str(e),etree.tostring(unit).decode(),category='STRUCTURE',confidence=1))
            continue
        decimals=el.get('decimals')
        doc.checked.append('XBRL_DECIMALS|'+loc)
        if decimals is not None and decimals!='INF' and not re.fullmatch(r'[+-]?\d+',decimals):
            doc.findings.append(finding(doc,'XBRL_DECIMALS',loc,'유효하지 않은 decimals 속성',decimals,category='STRUCTURE',confidence=1))
        try:
            value=number(text)
        except (ValueError,InvalidOperation):
            doc.findings.append(finding(doc,'XBRL_NUMERIC',loc,'숫자 Fact 형식 오류',text,category='STRUCTURE',confidence=1))
            continue
        doc.facts.append(Fact(concept=el.tag,value=value,period=period,unit=unit_name,entity=entity,
            scope=doc.metadata.get('scope','XBRL'),dimensions=dimensions,location=loc,source=doc.path,decimals=decimals))
    if config.xbrl_validation=='native':
        doc.logs.append({'rule':'XBRL_TAXONOMY','status':'NOT_VERIFIABLE','detail':'native 구조 검사는 완료. 전체 XBRL 검증에는 xbrl_validation=arelle 및 로컬 taxonomy가 필요합니다.'})


def validate_arelle(doc,config):
    """Subprocess isolates Arelle globals. Network is disabled; originals are never saved."""
    from .parsers import finding, digest
    if doc.kind not in ('xbrl','ixbrl'):
        return
    if config.xbrl_validation!='arelle':
        return
    for package in config.taxonomy_packages:
        p=Path(package).resolve(strict=True)
        doc.dependencies[str(p)]=digest(p)
    with tempfile.TemporaryDirectory(prefix='frr-arelle-') as tmp:
        log=Path(tmp)/'validation.json'; manifest=Path(tmp)/'request.json'; result=Path(tmp)/'result.json'
        manifest.write_text(json.dumps({'file':doc.path,'packages':config.taxonomy_packages,'log':str(log),'result':str(result)}))
        try:
            process=subprocess.run([sys.executable,'-m','frr.xbrl_worker',str(manifest)],capture_output=True,text=True,timeout=90)
            if process.returncode or not result.exists():
                raise ValueError((process.stderr or 'Arelle 결과 없음')[-1500:])
            payload=json.loads(result.read_text())
        except (OSError,ValueError,subprocess.TimeoutExpired) as e:
            doc.logs.append({'rule':'XBRL_TAXONOMY','status':'NOT_VERIFIABLE','detail':str(e)})
            return
        errors=payload.get('errors',[])
        complete=payload.get('loaded',False) and not payload.get('missing_resources',False)
        doc.logs.append({'rule':'XBRL_TAXONOMY','status':'PASS' if complete and not errors else 'FINDING' if complete else 'NOT_VERIFIABLE',
            'detail':f'Arelle 오프라인 검증; 오류 {len(errors)}건; 원본 저장 없음'})
        if complete:
            doc.target_signatures.update(payload.get('targets',{}))
        for path in payload.get('dependencies',[]):
            if Path(path).is_file():
                doc.dependencies[str(Path(path).resolve())]=digest(path)
        for i,error in enumerate(errors):
            loc=error.get('location') or f'Arelle:{i}'
            f=finding(doc,'XBRL_VALIDATION',loc,error['message'],error['code'],category='STRUCTURE',severity='HIGH',confidence=1)
            f.anchor='XBRL_VALIDATION|'+error['code']+'|'+loc
            doc.findings.append(f)
        # Broad Arelle PASS is insufficient to clear a removed Fact; handled conservatively in engine.
        if doc.kind=='ixbrl' and payload.get('facts'):
            doc.facts=[Fact(**{**f,'scope':doc.metadata.get('scope',f['scope'])},source=doc.path) for f in payload['facts']]
            doc.calculations=[c for c in doc.calculations if not c.get('inferred')]
            doc.logs=[l for l in doc.logs if l['rule'] not in ('INLINE_XBRL','FACT_EXTRACTION','TABLE_EXTRACTION','TABLE_VALUE')]
