from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from .engine import inspect_report_package, recheck_corrected_report, compare_report_versions

mcp = FastMCP('Financial Report Reviewer v0.6.1')
# Tools create separate review artifacts, but never modify source files.
annotations=ToolAnnotations(readOnlyHint=False,destructiveHint=False,idempotentHint=False,openWorldHint=False)
mcp.tool(annotations=annotations)(inspect_report_package)
mcp.tool(annotations=annotations)(recheck_corrected_report)
mcp.tool(annotations=annotations)(compare_report_versions)

def main():
    mcp.run(transport='stdio')

if __name__ == '__main__':
    main()
