"""Install FRR into its own venv and append its Codex MCP registration."""
from __future__ import annotations
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import tomllib
from datetime import datetime

SERVER='financial_report_reviewer'
ROOT=Path(__file__).resolve().parents[1]

def register(config_path: Path, python: Path) -> str:
    import json
    original=config_path.read_text(encoding='utf-8') if config_path.exists() else ''
    parsed=tomllib.loads(original)
    existing=parsed.get('mcp_servers',{}).get(SERVER)
    expected={'command':str(python),'args':['-m','frr.server']}
    if existing is not None:
        if all(existing.get(k)==v for k,v in expected.items()) and existing.get('enabled',True):
            return 'Codex MCP registration already exists.'
        raise RuntimeError('An existing financial_report_reviewer MCP entry has different settings. It was preserved; no settings were overwritten.')
    addition='\n\n[mcp_servers.'+SERVER+']\ncommand = '+json.dumps(str(python))+'\nargs = ["-m", "frr.server"]\n'
    updated=original+addition
    tomllib.loads(updated)
    config_path.parent.mkdir(parents=True,exist_ok=True)
    backup=None
    if config_path.exists():
        backup=config_path.with_name(config_path.name+'.frr-backup-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
        shutil.copy2(config_path,backup)
    temp_path=None
    try:
        with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=config_path.parent,delete=False) as f:
            temp_path=Path(f.name)
            f.write(updated)
        # Refuse to clobber changes made by the app while installation was running.
        latest=config_path.read_text(encoding='utf-8') if config_path.exists() else ''
        if latest!=original:
            raise RuntimeError('Codex settings changed during installation. Please run the installer again.')
        if config_path.exists():
            shutil.copymode(config_path,temp_path)
        os.replace(temp_path,config_path)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
    return 'Codex MCP registered.'+(' Original settings backed up to '+str(backup) if backup else '')

def main():
    if sys.version_info < (3,11):
        raise RuntimeError('Python 3.11 or later is required.')
    if not (ROOT/'pyproject.toml').is_file():
        raise RuntimeError('Extract the complete ZIP before running this installer.')
    venv=ROOT/'.venv'
    python=venv/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    if not python.is_file():
        print('Creating an isolated Python environment...',flush=True)
        subprocess.run([sys.executable,'-m','venv',str(venv)],check=True)
    print('Installing Financial Report Reviewer and its dependencies...',flush=True)
    subprocess.run([str(python),'-m','pip','install','-e',str(ROOT)],check=True)
    print('Checking the MCP tools...',flush=True)
    code="import asyncio; from frr.server import mcp; t=asyncio.run(mcp.list_tools()); assert {x.name for x in t} == {'inspect_report_package','recheck_corrected_report','compare_report_versions'}; print('All three MCP tools are available.')"
    subprocess.run([str(python),'-c',code],check=True,cwd=ROOT)
    print('Testing actual MCP communication...',flush=True)
    subprocess.run([str(python),str(ROOT/'tests/smoke_mcp.py')],check=True,cwd=ROOT,timeout=60)
    config=Path(os.environ.get('CODEX_HOME',str(Path.home()/'.codex')))/'config.toml'
    print(register(config,python),flush=True)
    print('\nInstallation complete. Restart Codex and use Financial Report Reviewer.\nKeep this extracted folder: the installed server runs from here.',flush=True)

if __name__=='__main__':
    try:
        main()
    except Exception as exc:
        print('\nInstallation did not complete: '+str(exc),file=sys.stderr)
        sys.exit(1)
