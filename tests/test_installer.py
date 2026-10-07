import tempfile
import tomllib
import unittest
from pathlib import Path
from installer.install_local import register

class InstallerTests(unittest.TestCase):
    def test_preserves_existing_settings_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);config=root/'config.toml'
            original='model = "example"\n[mcp_servers.other]\ncommand = "other-tool"\n'
            config.write_text(original)
            executable=root/'한글 경로'/'python.exe'
            register(config,executable)
            data=tomllib.loads(config.read_text())
            self.assertEqual(data['mcp_servers']['other']['command'],'other-tool')
            self.assertEqual(data['mcp_servers']['financial_report_reviewer']['command'],str(executable))
            backups=list(root.glob('config.toml.frr-backup-*'))
            self.assertEqual(len(backups),1)
            self.assertEqual(backups[0].read_text(),original)
            installed=config.read_text();register(config,executable)
            self.assertEqual(config.read_text(),installed)
    def test_conflicting_server_is_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            config=Path(temp)/'config.toml'
            original='[mcp_servers.financial_report_reviewer]\ncommand = "existing"\n'
            config.write_text(original)
            with self.assertRaises(RuntimeError):register(config,Path(temp)/'python.exe')
            self.assertEqual(config.read_text(),original)
    def test_invalid_config_is_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            config=Path(temp)/'config.toml';config.write_text('[broken')
            with self.assertRaises(tomllib.TOMLDecodeError):register(config,Path(temp)/'python.exe')
            self.assertEqual(config.read_text(),'[broken')
    def test_new_config_and_windows_path_encoding(self):
        with tempfile.TemporaryDirectory() as temp:
            config=Path(temp)/'new'/'config.toml'
            exe=Path('C:\\Tools\\Financial Reviewer\\.venv\\Scripts\\python.exe')
            register(config,exe)
            self.assertEqual(tomllib.loads(config.read_text())['mcp_servers']['financial_report_reviewer']['command'],str(exe))

if __name__=='__main__':unittest.main()
