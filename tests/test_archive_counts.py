import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml


class ArchiveCountsTest(unittest.TestCase):
    def test_workflow_counts_successful_semantic_scholar_digest(self):
        root = Path(__file__).resolve().parents[1]
        workflow = yaml.safe_load((root / '.github/workflows/daily.yml').read_text())
        step = next(s for s in workflow['jobs']['send-digest']['steps']
                    if s['name'] == 'Update docs/daily/index.json')
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            (work / 'docs/daily').mkdir(parents=True)
            (work / 'preview.html').write_text(
                (root / 'docs/daily/2026/10/2026-10-13.html').read_text())
            subprocess.run(['bash', '-e', '-c', step['run']], cwd=work,
                           env={**os.environ, 'DATE': '2026-10-13'}, check=True,
                           capture_output=True, text=True)
            entry = json.loads((work / 'docs/daily/index.json').read_text())[0]
            self.assertEqual(entry['papers'], 10)
            self.assertEqual(entry['notes'], 10)
