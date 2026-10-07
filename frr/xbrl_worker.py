"""Private offline Arelle entry point. It writes only to the supplied temp paths."""
import json
import sys
from pathlib import Path

def main():
    from arelle.CntlrCmdLine import parseAndRun
    request=json.loads(Path(sys.argv[1]).read_text())
    args=['--file',request['file'],'--validate','--internetConnectivity','offline',
        '--logFile','logToBuffer','--logLevel','info','--keepOpen','--disablePersistentConfig','--calc','c10']
    if request['packages']:
        args+=['--packages','|'.join(request['packages'])]
    controller=parseAndRun(args)
    model=controller.modelManager.modelXbrl
    loaded=bool(model and model.modelDocument)
    data=json.loads(controller.logHandler.getJson())
    entries=data.get('log',[]) if isinstance(data,dict) else data
    errors=[]
    for item in entries:
        if item.get('level','').lower() not in ('error','critical','fatal','inconsistency','warning'):
            continue
        refs=item.get('refs',[])
        location=';'.join(str(r.get('href','')).split('#',1)[-1] for r in refs)
        message=item.get('message',{})
        errors.append({'code':str(item.get('code','')),'message':message.get('text',str(message)) if isinstance(message,dict) else str(message),'location':location})
    missing=any(any(term in e['code'].lower() for term in ('ioerror','filenotloadable','importerror','notfound','schemaimportmissing')) for e in errors)
    dependencies=[]; facts=[]; targets={}
    if loaded:
        from arelle import XmlUtil
        targets={XmlUtil.elementFragmentIdentifier(e):json.dumps([e.tag, sorted(e.attrib.items())]) for e in model.modelDocument.xmlRootElement.iter() if isinstance(e.tag,str)}
        dependencies=[d.filepath for d in model.urlDocs.values() if d.filepath and Path(d.filepath).is_file()]
        for f in model.factsInInstance:
            if not f.isNumeric or f.isNil or f.context is None or f.unit is None:
                continue
            c=f.context
            from .xbrl import canonical_node
            dims=sorted(([k.clarkNotation,v.memberQname.clarkNotation] if v.isExplicit else canonical_node(v.typedMember) for k,v in c.qnameDims.items()),key=str)
            if c.isInstantPeriod:
                period=c.instantDatetime.date().isoformat()
                # Arelle models instants/end dates as the following midnight.
                from datetime import timedelta
                period=(c.instantDatetime-timedelta(days=1)).date().isoformat()
            elif c.isStartEndPeriod:
                from datetime import timedelta
                period=c.startDatetime.date().isoformat()+'/'+(c.endDatetime-timedelta(days=1)).date().isoformat()
            else:
                continue
            measures=f.unit.measures
            unit='*'.join(str(q.clarkNotation) for q in measures[0])
            if measures[1]:
                unit+='/'+'*'.join(str(q.clarkNotation) for q in measures[1])
            try:
                value=str(f.xValue)
                from decimal import Decimal
                if not Decimal(value).is_finite():
                    continue
            except Exception:
                continue
            facts.append({'concept':f.qname.clarkNotation,'value':value,'period':period,'unit':unit,
                'entity':':'.join(c.entityIdentifier),'scope':'XBRL','dimensions':json.dumps(dims,ensure_ascii=False,separators=(',',':')) if dims else '',
                'location':f'fact:{f.id or f.objectIndex}','decimals':f.decimals})
    Path(request['result']).write_text(json.dumps({'loaded':loaded,'missing_resources':missing,'errors':errors,'dependencies':dependencies,'facts':facts,'targets':targets}))
    controller.close()

if __name__=='__main__':
    main()
