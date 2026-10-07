"""Evidence-backed consistency rules; no document mutation or semantic approval."""
import hashlib
import json
import re
from collections import defaultdict
from decimal import Decimal
from .models import Finding
from .tables import DATE


def key_text(key):
    return json.dumps(key,ensure_ascii=False,separators=(',',':'))

def groups(doc):
    result=defaultdict(list)
    for f in doc.facts:
        result[f.key()].append(f)
    return result

def emit(doc,rule,anchor,message,actual,expected=None,category='CONSISTENCY',severity='MEDIUM',confidence=.9,evidence=None,**kw):
    from .parsers import finding
    f=finding(doc,rule,kw.pop('section',anchor),message,actual,expected,category=category,severity=severity,confidence=confidence,**kw)
    f.anchor=rule+'|'+anchor
    if evidence:
        f.evidence=evidence
    doc.findings.append(f)
    return f

def consistency(doc,config):
    if not doc.texts:
        doc.logs.append({'rule':'TEXT_CONSISTENCY','status':'NOT_APPLICABLE','detail':'텍스트 본문 없음'})
        return
    for text in doc.texts.values():
        doc.target_signatures['TEXT|'+hashlib.sha256(text.encode()).hexdigest()]=text
    for bad,good in config.terminology.items():
        if not bad:
            continue
        anchor='TERM|'+bad
        doc.checked.append(anchor)
        hits=[(loc,t) for loc,t in doc.texts.items() if bad in t]
        if hits:
            emit(doc,'TERM',bad,'용어 표기 불일치',bad,good,severity='LOW',confidence=.96,
                evidence=[f'{doc.path} [{loc}]: {t}' for loc,t in hits],suggested_text=good,
                target_contexts=[t.replace(bad,good) for _,t in hits],recommendation_type='LIKELY_FIX',suggestion=f'“{good}” 표기로 통일할지 확인하십시오.',section=hits[0][0])
    for rule in config.expectations:
        hits=[(loc,t) for loc,t in doc.texts.items() if rule.selector in t]
        anchor='EXPECTATION|'+rule.id
        doc.target_counts[anchor]=len(hits)
        if not hits:
            doc.logs.append({'rule':'EXPECTATION','status':'NOT_VERIFIABLE','location':rule.id,'detail':'기대 문구를 확인할 대상 문단을 찾지 못했습니다.'})
            continue
        doc.checked.append(anchor)
        def includes(text):
            if rule.kind=='date':
                def norm(t):
                    return DATE.sub(lambda m:f'{m[1]}-{int(m[2]):02d}-{int(m[3]):02d}',t)
                return norm(rule.expected) in norm(text)
            return rule.expected in text
        incorrect=[(loc,t) for loc,t in hits if not includes(t)]
        if incorrect:
            emit(doc,'EXPECTATION',rule.id,f'{rule.label}: 기준 정보와 불일치','\n'.join(t for _,t in incorrect),rule.expected,
                severity='HIGH',confidence=.95,section=incorrect[0][0],
                evidence=[f'{doc.path} [{loc}]: {t}' for loc,t in incorrect]+[f'검토 설정 {rule.id}: {rule.expected}'],
                suggestion='기준 회사명/날짜/문구와 대조 후 수정 여부를 확인하십시오.')
    if config.check_note_references:
        definitions=set()
        refs=defaultdict(list)
        for loc,text in doc.texts.items():
            definition=re.match(r'^\s*(?:주석\s*)?(\d{1,3})[.)]\s*\D',text)
            if definition:
                definitions.add(definition[1])
            for match in re.finditer(r'주석\s*(\d{1,3})(?!\d)',text):
                # "주석12. 제목" is a definition, not a reference.
                if definition and match.start()<3 and match[1]==definition[1]:
                    continue
                refs[match[1]].append((loc,text))
        if refs and not definitions:
            doc.logs.append({'rule':'NOTE_REFERENCE','status':'NOT_VERIFIABLE','detail':'주석 참조는 있으나 주석 제목 목록을 식별하지 못했습니다.'})
        elif definitions:
            for note,hits in refs.items():
                doc.checked.append('NOTE_REFERENCE|'+note)
                if note not in definitions:
                    emit(doc,'NOTE_REFERENCE',note,'참조하는 주석 번호를 찾을 수 없습니다.',note,','.join(sorted(definitions)),
                        confidence=.85,evidence=[f'{doc.path} [{loc}]: {t}' for loc,t in hits],section=hits[0][0])
        else:
            doc.logs.append({'rule':'NOTE_REFERENCE','status':'NOT_APPLICABLE','detail':'식별 가능한 주석 참조 없음'})
    doc.logs.append({'rule':'TEXT_CONSISTENCY','status':'PASS','detail':'용어/설정된 기대 정보/주석 참조 검사 실행 완료; 회계적 적정성 판정은 포함하지 않음'})


def numeric_structure(doc,config):
    for key,facts in groups(doc).items():
        anchor='DUPLICATE_FACT|'+key_text(key)
        doc.checked.append(anchor)
        values={f.value for f in facts}
        if len(values)>1:
            emit(doc,'DUPLICATE_FACT',key_text(key),'동일 계정·기간·단위·범위의 금액이 문서 내에서 다릅니다.',
                ', '.join(map(str,sorted(values))),category='RECONCILIATION',severity='HIGH',confidence=.95,
                evidence=[f'{f.source} [{f.location}]: {f.value} {f.unit}' for f in facts],section=facts[0].location)
        constraint=config.sign_constraints.get(key[0])
        if constraint:
            doc.checked.append('SIGN|'+key_text(key))
            bad=[f for f in facts if (f.value<0 if constraint=='nonnegative' else f.value>0)]
            if bad:
                emit(doc,'SIGN',key_text(key),'설정된 부호 제약 위반',str(bad[0].value),constraint,category='STRUCTURE',
                    severity='HIGH',confidence=.95,evidence=[f'{f.source} [{f.location}]: {f.value}' for f in bad]+[f'설정 sign_constraints: {constraint}'])


def calculations(doc,config):
    byloc=defaultdict(list)
    for fact in doc.facts:
        byloc[fact.location].append(fact)
    ids=[str(c.get('id','')) for c in doc.calculations]
    for calc in doc.calculations:
        cid=str(calc.get('id',''))
        try:
            if not cid or ids.count(cid)!=1:
                raise ValueError('합계관계 id가 없거나 중복되었습니다.')
            parts=calc['components']
            locations=[c if isinstance(c,str) else c['location'] for c in parts]
            if not parts or len(set(locations))!=len(locations) or calc['total'] in locations:
                raise ValueError('구성요소 누락/중복/자기 참조')
            if any(len(byloc[loc])!=1 for loc in [calc['total']]+locations):
                raise ValueError('합계 또는 구성요소를 유일하게 식별할 수 없습니다.')
            total=byloc[calc['total']][0]; facts=[byloc[p][0] for p in locations]
            if any(f.key()[1:]!=total.key()[1:] for f in facts):
                raise ValueError('기간/단위/회사/범위/차원이 다릅니다.')
            weights=[Decimal(1) if isinstance(c,str) else Decimal(str(c.get('weight',1))) for c in parts]
            if any(not w.is_finite() for w in weights):
                raise ValueError('유효하지 않은 합계 가중치')
            expected=sum((f.value*w for f,w in zip(facts,weights)),Decimal(0))
            rule='CROSS_FOOTING' if calc.get('cross') else 'FOOTING'
            # Definition changes must never silently clear the old issue.
            basis=hashlib.sha256(key_text([total.key(),[(f.key(),str(w)) for f,w in zip(facts,weights)]]).encode()).hexdigest()[:16]
            anchor=cid+'|'+basis
            doc.checked.append(rule+'|'+anchor)
            if abs(total.value-expected)>config.numeric_tolerance:
                f=emit(doc,rule,anchor,'합계관계 불일치'+(' (표 구조에서 추론한 후보)' if calc.get('inferred') else ''),
                    str(total.value),str(expected),category='FOOTING',severity='HIGH',confidence=.8 if calc.get('inferred') else 1,
                    difference=str(total.value-expected),difference_numeric=total.value-expected,unit=total.unit,section=total.location,
                    evidence=[f'{total.source} [{total.location}]: {total.value}']+[f'{f.source} [{f.location}]: {f.value} × {w}' for f,w in zip(facts,weights)])
            else:
                doc.logs.append({'rule':rule,'status':'PASS','location':total.location,'detail':f'{total.value} = {expected}'})
        except (ValueError,KeyError,ArithmeticError,TypeError) as e:
            doc.logs.append({'rule':'FOOTING','status':'NOT_VERIFIABLE','location':cid,'detail':str(e)})
    if not doc.calculations:
        doc.logs.append({'rule':'FOOTING','status':'NOT_APPLICABLE','detail':'정의되거나 명확히 추론 가능한 합계관계 없음'})
