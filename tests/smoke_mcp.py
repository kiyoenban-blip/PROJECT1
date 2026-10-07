"""Real stdio protocol test; needs local asynchronous sockets in sandboxed hosts."""
import asyncio
import json
import sys
import tempfile
from pathlib import Path
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT=Path(__file__).resolve().parents[1]

def payload(response):
    assert not response.isError,response
    return response.structuredContent or json.loads(response.content[0].text)

async def exercise():
    with tempfile.TemporaryDirectory() as tmp:
        async with stdio_client(StdioServerParameters(command=sys.executable,args=['-m','frr.server'])) as (reader,writer):
            async with ClientSession(reader,writer) as client:
                await client.initialize()
                listing=await client.list_tools()
                assert {t.name for t in listing.tools}=={'inspect_report_package','recheck_corrected_report','compare_report_versions'}
                first=payload(await client.call_tool('inspect_report_package',{
                    'primary_file':str(ROOT/'examples/report.json'),'reference_files':[str(ROOT/'examples/tb.json')],
                    'output_path':str(Path(tmp)/'first.xlsx')}))
                assert first['summary']['NEW']==1,first
                second=payload(await client.call_tool('recheck_corrected_report',{
                    'previous_review_file':first['output_file'],'corrected_report':str(ROOT/'examples/corrected.json'),
                    'output_path':str(Path(tmp)/'second.xlsx')}))
                assert second['summary']['RESOLVED']==1,second
                assert second['final_status']=='REVIEW_COMPLETE',second
                third=payload(await client.call_tool('compare_report_versions',{
                    'old_file':str(ROOT/'examples/corrected.json'),'new_file':str(ROOT/'examples/report.json'),
                    'reference_files':[str(ROOT/'examples/tb.json')],'output_path':str(Path(tmp)/'third.xlsx')}))
                assert third['version_changes'],third
                print('PASS: MCP initialization, tool listing, inspect, recheck and compare')

if __name__=='__main__':
    asyncio.run(asyncio.wait_for(exercise(),timeout=30))
