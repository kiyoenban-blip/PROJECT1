"""Local CLI for the same three MCP workflows."""
import argparse
import json
from pathlib import Path
from .engine import inspect_report_package,recheck_corrected_report,compare_report_versions


def main():
    parser=argparse.ArgumentParser(description='원본을 수정하지 않는 Financial Report Reviewer')
    subs=parser.add_subparsers(dest='command',required=True)
    inspect=subs.add_parser('inspect');inspect.add_argument('primary_file')
    inspect.add_argument('--prior');inspect.add_argument('--previous-version')
    inspect.add_argument('--materiality',type=float);inspect.add_argument('--performance-materiality',type=float)
    inspect.add_argument('--trivial-threshold',type=float)
    recheck=subs.add_parser('recheck');recheck.add_argument('previous_review_file');recheck.add_argument('corrected_report')
    compare=subs.add_parser('compare');compare.add_argument('old_file');compare.add_argument('new_file')
    for p in (inspect,recheck,compare):
        p.add_argument('--reference',action='append',default=None)
        p.add_argument('--output')
    for p in (inspect,compare):
        p.add_argument('--config',help='ReviewConfig JSON 파일')
    args=parser.parse_args()
    config=json.loads(Path(args.config).read_text(encoding='utf-8-sig')) if getattr(args,'config',None) else None
    if args.command=='inspect':
        result=inspect_report_package(args.primary_file,args.reference,prior_file=args.prior,previous_version=args.previous_version,
            materiality=args.materiality,performance_materiality=args.performance_materiality,trivial_threshold=args.trivial_threshold,
            review_config=config,output_path=args.output)
    elif args.command=='recheck':
        result=recheck_corrected_report(args.previous_review_file,args.corrected_report,args.reference,output_path=args.output)
    else:
        result=compare_report_versions(args.old_file,args.new_file,args.reference,review_config=config,output_path=args.output)
    print(json.dumps({k:result[k] for k in ('review_id','final_status','summary','output_file')},ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
