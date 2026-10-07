"""Read-only review orchestration and evidence-based clearing."""
import hashlib
import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from collections import defaultdict
from .config import ReviewConfig
from .models import Finding,Severity
from .parsers import parse,digest,number
from .rules import key_text,groups,consistency,numeric_structure,calculations
from .versions import changes,unexpected_changes

SCHEMA='frr-review-0.6'
VERSION='0.6.1'


def thresholds(materiality,performance_materiality,trivial_threshold):
    result={}
    for name,value in [('materiality',materiality),('performance_materiality',performance_materiality),('trivial_threshold',trivial_threshold)]:
        if value is not None:
            n=number(value)
            if n<=0:
                raise ValueError(f'{name}는 양수여야 합니다.')
            result[name]=str(n)
    if 'materiality' in result and 'performance_materiality' in result and Decimal(result['performance_materiality'])>Decimal(result['materiality']):
        raise ValueError('PM은 Overall Materiality보다 클 수 없습니다.')
    if 'trivial_threshold' in result and any(Decimal(result['trivial_threshold'])>Decimal(result[k]) for k in ('materiality','performance_materiality') if k in result):
        raise ValueError('Trivial Threshold는 중요성/PM보다 클 수 없습니다.')
    return result


def reconcile(primary,references,config,rule='RECONCILE'):
    lineage=[]; refgroups=[groups(r) for r in references]
    for key,facts in groups(primary).items():
        candidates=[f for g in refgroups for f in g.get(key,[])]
        if not candidates:
            if config.require_references or references:
                primary.logs.append({'rule':rule,'status':'NOT_VERIFIABLE','location':facts[0].location,'detail':'동일 계정/기간/단위/회사/범위/차원의 비교 근거 없음'})
            continue
        actuals={f.value for f in facts}; expected_values={f.value for f in candidates}
        if len(actuals)>1:
            primary.logs.append({'rule':rule,'status':'NOT_VERIFIABLE','location':facts[0].location,'detail':'문서 내 동일 키 금액이 서로 다릅니다. 중복 Fact 검토 필요.'})
            continue
        anchor=rule+'|'+key_text(key)
        primary.checked.append(anchor)
        actual=facts[0].value
        for other in candidates:
            lineage.append({'rule':rule,'concept':key[0],'primary_location':facts[0].location,'primary_value':str(actual),
                'reference':other.source,'reference_location':other.location,'reference_value':str(other.value),'difference':str(actual-other.value),
                'period':key[1],'unit':key[2],'entity':key[3],'scope':key[4],'dimensions':key[5]})
        if len(expected_values)==1 and abs(actual-next(iter(expected_values)))<=config.numeric_tolerance:
            primary.logs.append({'rule':rule,'status':'PASS','location':facts[0].location,'detail':f'{key[0]}: {actual}; 허용오차 {config.numeric_tolerance} 이내'})
            continue
        expected=next(iter(expected_values)) if len(expected_values)==1 else None
        delta=actual-expected if expected is not None else None
        confidence=min([.98]+[f.extraction_confidence for f in facts+candidates]) if expected is not None else .7
        primary.findings.append(Finding(rule_id=rule,category='RECONCILIATION',severity='HIGH',primary_file=primary.path,
            section=facts[0].location,actual=str(actual),expected=str(expected) if expected is not None else '근거자료 상호 불일치',
            difference=str(delta) if delta is not None else None,difference_numeric=delta,unit=key[2],
            message=f'{key[0]} 금액 불일치' if expected is not None else f'{key[0]} 근거자료간 금액 불일치',
            evidence=[f'{f.source} [{f.location}]: {f.value} {f.unit}' for f in facts+candidates],
            reference_file=candidates[0].source,reference_location=candidates[0].location,
            suggestion='근거자료와 보고서의 금액을 확인하십시오. 비교값을 정답으로 확정하지 않습니다.',
            suggested_text=str(expected) if expected is not None else None,confidence=confidence,anchor=anchor))
    return lineage


def finalize(result):
    result['summary']={s:sum(f['clearing']==s for f in result['findings']) for s in ('RESOLVED','UNRESOLVED','NEW','NOT_VERIFIABLE')}
    if any(l['status']=='FAILED' for l in result['logs']):
        result['final_status']='VALIDATION_FAILED'
    elif any(l['status']=='NOT_VERIFIABLE' for l in result['logs']) or result['summary']['NOT_VERIFIABLE']:
        result['final_status']='REVIEW_REQUIRED'
    elif any(f['clearing']!='RESOLVED' for f in result['findings']):
        result['final_status']='REVIEW_COMPLETE_WITH_OPEN_ITEMS'
    else:
        result['final_status']='REVIEW_COMPLETE'
    result['coverage']={s:sum(l['status']==s for l in result['logs']) for s in ('PASS','FINDING','NOT_APPLICABLE','NOT_VERIFIABLE','FAILED')}


def inspect_report_package(primary_file: str, reference_files: list[str] | None = None,
        prior_file: str | None = None, previous_version: str | None = None,
        materiality: float | None = None, performance_materiality: float | None = None,
        trivial_threshold: float | None = None, export_excel: bool = True, output_path: str | None = None,
        review_config: dict | None = None):
    """원본을 읽기만 하고 근거·수정 제안과 Excel을 생성한다. 메타데이터 및 검사 범위는 review_config로 지정한다."""
    config=ReviewConfig.model_validate(review_config or {})
    limits=thresholds(materiality,performance_materiality,trivial_threshold)
    primary_path=str(Path(primary_file).resolve())
    refpaths=[str(Path(p).resolve()) for p in reference_files or []]
    if len(set([primary_path]+refpaths))!=len(refpaths)+1:
        raise ValueError('검토 파일과 근거 파일은 중복될 수 없습니다.')
    roles={primary_path:'PRIMARY'}
    for p in refpaths:
        roles[p]=config.reference_roles.get(p,config.reference_roles.get(Path(p).name,p))
    if len(set(roles.values()))!=len(roles):
        raise ValueError('reference_roles는 고유해야 하며 PRIMARY를 사용할 수 없습니다.')
    cfg=config.model_dump(mode='json')
    result={'schema':SCHEMA,'engine_version':VERSION,'review_id':str(uuid.uuid4()),'created_at':datetime.now(timezone.utc).isoformat(),
        'primary_file':primary_path,'reference_files':refpaths,'prior_file':str(Path(prior_file).resolve()) if prior_file else None,
        'previous_version':str(Path(previous_version).resolve()) if previous_version else None,
        'review_config':cfg,'thresholds':limits,'input_hashes':{},'source_roles':roles,'findings':[],
        'logs':[],'passes':[],'lineage':[],'facts':[],'checked':[],'checks_by_source':{},'target_signatures':{},'target_counts':{},'version_changes':[],'prior_changes':[]}
    docs={}
    paths=list(dict.fromkeys([primary_path]+refpaths+[p for p in [result['prior_file'],result['previous_version']] if p]))
    for path in paths:
        try:
            doc=parse(path,config)
            docs[path]=doc
            result['input_hashes'][path]=doc.sha256
        except Exception as e:
            # File-format/parser failures remain reviewable. Caller/config errors above still raise.
            result['logs'].append({'rule':'DOCUMENT_PARSE','status':'FAILED','file':path,'detail':f'{type(e).__name__}: {e}'})
            if Path(path).is_file():
                result['input_hashes'][path]=digest(path)
    primary=docs.get(primary_path)
    references=[docs[p] for p in refpaths if p in docs]
    from .xbrl import validate_arelle
    from .tables import normalize_facts
    for path in [primary_path]+refpaths:
        doc=docs.get(path)
        if doc is None:
            continue
        validate_arelle(doc,config)
        if doc.kind=='ixbrl':
            # Arelle appends raw facts after the initial HTML parse.
            raw=[f for f in doc.facts if f.raw_value is None]
            existing=doc.facts; doc.facts=raw; normalize_facts(doc,config); doc.facts=existing
        consistency(doc,config); numeric_structure(doc,config); calculations(doc,config)
    if primary:
        if len(references)==len(refpaths):
            result['lineage']=reconcile(primary,references,config)
        else:
            primary.logs.append({'rule':'RECONCILE','status':'NOT_VERIFIABLE','detail':'일부 근거파일을 읽지 못해 대사를 완료하지 못했습니다.'})
        if result['previous_version'] in docs:
            old=docs[result['previous_version']]
            result['version_changes']=changes(old,primary)
            unexpected_changes(old,primary,references)
        if result['prior_file'] in docs:
            prior=docs[result['prior_file']]
            result['prior_changes']=changes(prior,primary)
            shared=set(groups(prior))&set(groups(primary))
            if shared:
                # Only the same periods (report comparative columns) are reconciled.
                selected=primary.model_copy(deep=True)
                selected.facts=[f for f in primary.facts if f.key() in shared]
                selected.findings=[]; selected.checked=[]; selected.logs=[]
                result['lineage'].extend(reconcile(selected,[prior],config,'PRIOR_PERIOD'))
                primary.findings.extend(selected.findings); primary.checked.extend(selected.checked); primary.logs.extend(selected.logs)
            else:
                primary.logs.append({'rule':'PRIOR_PERIOD','status':'NOT_VERIFIABLE','detail':'전기 보고서와 동일 기간의 비교표시 Fact가 없습니다. 기간 매핑을 확인하십시오.'})
    allfacts=[f for p in [primary_path]+refpaths if p in docs for f in docs[p].facts]
    units={f.unit for f in allfacts}
    threshold_unit=config.materiality_unit or (next(iter(units)) if len(units)==1 else None)
    result['materiality_unit']=threshold_unit
    for p in [primary_path]+refpaths:
        if p not in docs:
            continue
        doc=docs[p]
        if any(l['status'] in ('NOT_VERIFIABLE','FAILED') and l['rule'] in ('FACT_PARSE','PDF_TEXT','TABLE_VALUE','ARCHIVE_MEMBER') for l in doc.logs):
            doc.parse_complete=False
        result['target_counts'][roles[p]]=doc.target_counts
        result['checks_by_source'][roles[p]]=sorted(set(doc.checked)) if doc.parse_complete else []
        result['target_signatures'][roles[p]]=doc.target_signatures
        for f in doc.findings:
            if f.difference_numeric is not None and limits:
                if f.unit==threshold_unit:
                    for k,v in limits.items():
                        setattr(f,k+'_ratio',abs(f.difference_numeric)/Decimal(v))
                    if f.materiality_ratio is not None and f.materiality_ratio>=1:
                        f.severity=Severity.CRITICAL
                else:
                    doc.logs.append({'rule':'MATERIALITY','status':'NOT_VERIFIABLE','location':f.section,'detail':f'Finding 단위 {f.unit}와 중요성 단위 {threshold_unit}를 확인하십시오.'})
            # Match key includes role so reference files have independent identity.
            f.match_key=key_text([roles[p],f.anchor])
            f.finding_id=str(uuid.uuid4())
            f.issue_id=f'FRR-{datetime.now(timezone.utc).year}-{len(result["findings"])+1:06d}'
            result['findings'].append(f.model_dump(mode='json'))
        result['logs'].extend({**l,'file':p} for l in doc.logs)
        result['facts'].extend(f.model_dump(mode='json') for f in doc.facts)
    if primary:
        result['checked']=sorted(set(primary.checked))
    result['passes']=[l for l in result['logs'] if l['status']=='PASS']
    for doc in docs.values():
        result['input_hashes'].update(doc.dependencies)
    for path,expected in result['input_hashes'].items():
        if not Path(path).is_file() or digest(path)!=expected:
            result['logs'].append({'rule':'INPUT_INTEGRITY','status':'FAILED','file':path,'detail':'검사 중 입력 파일 변경 또는 삭제'})
    # This fingerprint covers mappings/expectations, not source filenames.
    semantic_cfg={k:v for k,v in cfg.items() if k not in ('reference_roles','document_metadata')}
    result['scope_fingerprint']=hashlib.sha256(key_text([semantic_cfg,limits]).encode()).hexdigest()
    finalize(result)
    if export_excel:
        from .workbook import write_review
        result['output_file']=write_review(result,output_path)
    return result


def recheck_corrected_report(previous_review_file: str, corrected_report: str,
        reference_files: list[str] | None = None, output_path: str | None = None):
    """이전 규칙·기준·근거자료로 전체 재검사한다. 미검출만으로 해결 처리하지 않는다."""
    from .workbook import read_review,write_review
    previous=read_review(previous_review_file)
    refs=previous['reference_files'] if reference_files is None else reference_files
    config=previous.get('review_config',{})
    # Keep per-primary metadata even if a corrected file uses a new name.
    cfg=json.loads(json.dumps(config))
    dm=cfg.setdefault('document_metadata',{})
    oldp=previous['primary_file']; newp=str(Path(corrected_report).resolve())
    primary_meta=dm.get(oldp,dm.get(Path(oldp).name))
    if primary_meta is not None:
        dm[newp]=primary_meta
    result=inspect_report_package(corrected_report,refs,prior_file=previous.get('prior_file'),previous_version=previous.get('previous_version'),
        export_excel=False,review_config=cfg,**{k:Decimal(v) for k,v in previous['thresholds'].items()})
    def identity(f,review):
        if f.get('match_key'):
            return f['match_key']
        role='PRIMARY' if f['primary_file']==review['primary_file'] else f['primary_file']
        return key_text([role,f['anchor']])
    old=defaultdict(list)
    for f in previous['findings']:
        old[identity(f,previous)].append(f)
    used=set(); new=[]
    for f in result['findings']:
        matches=old.get(identity(f,result),[])
        if len(matches)==1 and matches[0]['issue_id'] not in used:
            prior=matches[0]; used.add(prior['issue_id'])
            f['issue_id']=prior['issue_id']; f['clearing']='UNRESOLVED'
            f['verification']='동일 규칙과 대상에서 오류 재검출'
            for k in ('status','owner','reviewer','memo'):
                f[k]=prior.get(k,'')
        else:
            new.append(f)
    seq=max((int(f['issue_id'].rsplit('-',1)[-1]) for f in previous['findings'] if f['issue_id'].rsplit('-',1)[-1].isdigit()),default=0)
    for f in new:
        seq+=1; f['issue_id']=f'FRR-{datetime.now(timezone.utc).year}-{seq:06d}'
    same_scope=not previous.get('scope_fingerprint') or previous['scope_fingerprint']==result['scope_fingerprint']
    old_roles=set(previous.get('source_roles',{p:p for p in previous['reference_files']}).values())-{'PRIMARY'}
    current_roles=set(result['source_roles'].values())-{'PRIMARY'}
    successful=result['final_status']!='VALIDATION_FAILED'
    for prior in previous['findings']:
        if prior['issue_id'] in used:
            continue
        f=dict(prior); match=identity(prior,previous)
        role,anchor=json.loads(match)
        checked=anchor in result['checks_by_source'].get(role,[])
        if prior['rule_id']=='TERM':
            targets=result.get('target_signatures',{}).get(role,{})
            contexts=prior.get('target_contexts',[])
            checked=checked and bool(contexts) and all('TEXT|'+hashlib.sha256(t.encode()).hexdigest() in targets for t in contexts)
        if prior['rule_id']=='EXPECTATION':
            old_count=previous.get('target_counts',{}).get(role,{}).get(anchor,0)
            new_count=result.get('target_counts',{}).get(role,{}).get(anchor,0)
            checked=checked and old_count>0 and new_count>=old_count
        if prior['rule_id']=='XBRL_VALIDATION':
            locs=(prior.get('section') or '').split(';')
            old_targets=previous.get('target_signatures',{}).get(role,{})
            new_targets=result.get('target_signatures',{}).get(role,{})
            checked=bool(locs) and all(t in old_targets and new_targets.get(t)==old_targets[t] for t in locs)
        evidence_preserved=not (prior['rule_id'] in ('RECONCILE','UNEXPECTED_CHANGE') and not old_roles.issubset(current_roles))
        resolved=successful and same_scope and checked and evidence_preserved
        f['clearing']='RESOLVED' if resolved else 'NOT_VERIFIABLE'
        f['verification']='동일 대상 재평가 완료, 오류 없음' if resolved else '대상·검사범위·비교근거를 동일 조건으로 재확인할 수 없음'
        f['finding_id']=str(uuid.uuid4()); f['match_key']=match
        f['primary_file']=newp if role=='PRIMARY' else next((p for p,r in result['source_roles'].items() if r==role),f['primary_file'])
        result['findings'].append(f)
    result['previous_issue_count']=len(previous['findings'])
    result['previous_review_id']=previous['review_id']
    result['input_hashes'][str(Path(previous_review_file).resolve())]=digest(previous_review_file)
    finalize(result)
    assert result['previous_issue_count']==sum(result['summary'][s] for s in ('RESOLVED','UNRESOLVED','NOT_VERIFIABLE'))
    result['output_file']=write_review(result,output_path)
    return result


def compare_report_versions(old_file: str, new_file: str, reference_files: list[str] | None = None,
        review_config: dict | None = None, output_path: str | None = None):
    """숫자·문구·날짜·회사명·주석·표 및 추가/삭제/동일 내용 이동을 비교한다."""
    return inspect_report_package(new_file,reference_files,previous_version=old_file,review_config=review_config,output_path=output_path)
