"""Document/archive readers. No extraction to input directories and no network."""
import io
import json
import tempfile
from pathlib import Path, PurePosixPath
from zipfile import ZipFile
from lxml import etree, html
from .models import Document

class NoExternal(etree.Resolver):
    def resolve(self, url, pubid, context):
        raise ValueError('외부 XML 리소스를 로드하지 않습니다.')

def xml_root(data):
    parser=etree.XMLParser(resolve_entities=False,no_network=True,load_dtd=False,huge_tree=False)
    parser.resolvers.add(NoExternal())
    root=etree.fromstring(data,parser)
    if root.getroottree().docinfo.doctype:
        raise ValueError('DTD가 포함된 XML은 지원하지 않습니다.')
    return root

def local(el):
    return el.tag.rsplit('}',1)[-1].split(':')[-1].lower() if isinstance(el.tag,str) else ''

def markup(doc,data,xml=False):
    if xml:
        root=xml_root(data)
    else:
        try:
            text=data.decode('utf-8-sig')
        except UnicodeDecodeError:
            text=data.decode('cp949')
        root=html.fromstring(text,parser=html.HTMLParser(no_network=True))
    # Preserve paragraphs/headings for semantics and stable content matching.
    for i,el in enumerate(root.iter()):
        tag=local(el)
        if tag in ('p','title','h1','h2','h3','h4','tu','te','td','th'):
            if any(local(c) in ('p','td','th','te','tu') for c in el.iterdescendants()):
                continue
            text=' '.join(''.join(el.itertext()).split())
            if text:
                doc.texts[f'{tag}:{el.get("id") or i}']=text
    if not doc.texts:
        doc.texts['document']=' '.join(' '.join(root.itertext()).split())
    for index,tab in enumerate(e for e in root.iter() if local(e)=='table'):
        rows=[]; spans={}
        for r,tr in enumerate(e for e in tab.iter() if local(e)=='tr'):
            # Skip nested tables (they are parsed separately).
            ancestor=next((a for a in tr.iterancestors() if local(a)=='table'),None)
            if ancestor is not tab:
                continue
            cells=[]; col=0
            for td in (e for e in tr if local(e) in ('td','th','te','tu')):
                while (r,col) in spans:
                    cells.append(spans[(r,col)]); col+=1
                text=' '.join(''.join(td.itertext()).split())
                cs=int(td.get('colspan',td.get('COLSPAN','1')))
                rs=int(td.get('rowspan',td.get('ROWSPAN','1')))
                if not 1<=cs<=100 or not 1<=rs<=100:
                    raise ValueError('표 병합 범위가 제한을 초과합니다.')
                for dc in range(cs):
                    cells.append(text if dc==0 else '')
                    for dr in range(1,rs):
                        spans[(r+dr,col+dc)]=text
                col+=cs
            while (r,col) in spans:
                cells.append(spans[(r,col)]); col+=1
            rows.append(cells)
        doc.tables.append({'location':f'table:{index+1}','rows':rows})
    return root

def archive(doc,data,config,read_bytes):
    with ZipFile(io.BytesIO(data)) as z:
        members=z.infolist()
        if len(members)>config.max_archive_members or sum(m.file_size for m in members)>config.max_archive_bytes:
            raise ValueError('압축파일 제한 초과')
        seen=set(); supported=0
        for entry in members:
            name=entry.filename
            if name in seen:
                raise ValueError('중복 압축파일 경로')
            seen.add(name)
            path=PurePosixPath(name)
            if path.is_absolute() or '..' in path.parts or '\\' in name:
                raise ValueError('안전하지 않은 압축파일 경로')
            if entry.is_dir():
                continue
            suffix=path.suffix.lower()
            if suffix not in ('.xml','.xbrl','.html','.htm','.xhtml','.txt','.csv','.json'):
                doc.logs.append({'rule':'ARCHIVE_MEMBER','status':'NOT_APPLICABLE','location':name,'detail':'검토 대상 형식이 아닌 부속 파일'})
                continue
            supported+=1
            child=Document(path=doc.path,sha256=doc.sha256,metadata=dict(doc.metadata))
            try:
                read_bytes(child,z.read(entry),suffix,config)
            except (ValueError, etree.XMLSyntaxError, json.JSONDecodeError) as e:
                doc.parse_complete=False
                doc.logs.append({'rule':'ARCHIVE_MEMBER','status':'FAILED','location':name,'detail':str(e)})
                continue
            if child.kind in ('xbrl','ixbrl') and config.xbrl_validation=='arelle':
                # Work on a bounded temporary copy, preserving relative taxonomy links.
                from .xbrl import validate_arelle
                with tempfile.TemporaryDirectory(prefix='frr-archive-') as tmp:
                    base=Path(tmp)
                    for member in members:
                        member_path=PurePosixPath(member.filename)
                        if member_path.is_absolute() or '..' in member_path.parts or '\\' in member.filename:
                            raise ValueError('안전하지 않은 압축파일 경로')
                        if not member.is_dir():
                            target=base.joinpath(*member_path.parts)
                            target.parent.mkdir(parents=True,exist_ok=True)
                            target.write_bytes(z.read(member))
                    virtual_path=child.path
                    child.path=str(base.joinpath(*path.parts))
                    validate_arelle(child,config)
                    for finding in child.findings:
                        finding.primary_file=virtual_path
                        finding.evidence=[e.replace(str(base)+ '/',virtual_path+'::') for e in finding.evidence]
                        finding.message=finding.message.replace(str(base)+ '/',virtual_path+'::')
                    for fact in child.facts:
                        fact.source=virtual_path
                    child.dependencies={p:h for p,h in child.dependencies.items() if not Path(p).is_relative_to(base)}
                    child.path=virtual_path
            prefix=name+'::'
            for f in child.facts:
                f.location=prefix+f.location
            for f in child.findings:
                f.section=';'.join(prefix+part for part in (f.section or '').split(';')) if f.rule_id=='XBRL_VALIDATION' else prefix+(f.section or '')
                f.anchor=prefix+f.anchor
                f.evidence.insert(0,f'압축파일 멤버: {name}')
            for t in child.tables:
                t['location']=prefix+t['location']
            for calc in child.calculations:
                calc['id']=prefix+str(calc['id']); calc['total']=prefix+calc['total']
                calc['components']=[prefix+c if isinstance(c,str) else {**c,'location':prefix+c['location']} for c in calc['components']]
            doc.facts.extend(child.facts); doc.findings.extend(child.findings)
            doc.texts.update({prefix+k:v for k,v in child.texts.items()})
            doc.checked.extend(prefix+k for k in child.checked)
            doc.tables.extend(child.tables); doc.calculations.extend(child.calculations)
            doc.logs.extend({**l,'member':name} for l in child.logs)
            doc.dependencies.update(child.dependencies)
            doc.target_signatures.update({prefix+k:v for k,v in child.target_signatures.items()})
            doc.target_counts.update({prefix+k:v for k,v in child.target_counts.items()})
        if not supported:
            raise ValueError('검토 가능한 문서가 압축파일에 없습니다.')
