"""Create review workbooks from fictional, immutable sample inputs."""
import argparse
import json
from pathlib import Path
from uuid import uuid4
from frr import inspect_report_package,recheck_corrected_report

root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--output-dir',type=Path,default=root/'output'/('demo_'+uuid4().hex[:8]))
args=parser.parse_args()
args.output_dir.mkdir(parents=True,exist_ok=True)
first=inspect_report_package(str(root/'examples/report.json'),[str(root/'examples/tb.json')],
    materiality=500,performance_materiality=350,trivial_threshold=25,output_path=str(args.output_dir/'ABC_2026_Review.xlsx'))
final=recheck_corrected_report(first['output_file'],str(root/'examples/corrected.json'),output_path=str(args.output_dir/'ABC_2026_Final_Review.xlsx'))
pdf=inspect_report_package(str(root/'examples/tables/report.pdf'),review_config={'metadata':{'entity':'ABC','scope':'separate','unit':'KRW'},'require_references':False},
    output_path=str(args.output_dir/'PDF_Table_Review.xlsx'))
xbrl=inspect_report_package(str(root/'examples/xbrl/report.xbrl'),review_config={'require_references':False},output_path=str(args.output_dir/'XBRL_Review.xlsx'))
for result in (first,final,pdf,xbrl):
    print(json.dumps({k:result[k] for k in ('output_file','final_status','summary')},ensure_ascii=False))
