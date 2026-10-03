"""Run offline checks with fresh benchmark state, retain reproducible evidence."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / 'artifacts'


def run(arguments):
    environment = {**os.environ, 'LLM_MODE': 'offline', 'PYTHONIOENCODING': 'utf-8'}
    result = subprocess.run([sys.executable, *arguments], cwd=ROOT, env=environment,
                            capture_output=True, encoding='utf-8', timeout=120)
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    return result.stdout


def main():
    ARTIFACTS.mkdir(exist_ok=True)
    first = run(['src/benchmark.py'])
    first_json = (ARTIFACTS / 'benchmark_results.json').read_bytes()
    second = run(['src/benchmark.py'])
    second_json = (ARTIFACTS / 'benchmark_results.json').read_bytes()
    if first != second or first_json != second_json:
        raise AssertionError('Benchmark results differ on repeated clean runs')
    (ARTIFACTS / 'benchmark_output.txt').write_text(second, encoding='utf-8')
    required = run(['-m', 'pytest', 'src/test_agents.py', '-v'])
    full = run(['-m', 'pytest', 'src', '-v'])
    (ARTIFACTS / 'pytest_output.txt').write_text(full, encoding='utf-8')
    expected = json.loads((ARTIFACTS / 'benchmark_results.json').read_text(encoding='utf-8'))
    dataset_hashes = {}
    source = json.loads((ROOT / 'docs' / 'source_manifest.json').read_text(encoding='utf-8'))
    for path in (ROOT / 'data').glob('*.json'):
        current = path.read_bytes()
        digest = hashlib.sha256(current).hexdigest()
        if digest != source['dataset_sha256'][path.name]:
            raise AssertionError(f'Dataset modified: {path.name}')
        if (ROOT / '.git').exists():
            original = subprocess.check_output(['git', 'show', f"{source['commit']}:data/{path.name}"], cwd=ROOT)
            if original != current:
                raise AssertionError(f'Dataset differs from upstream commit: {path.name}')
        dataset_hashes[path.name] = digest
    for name, suite in expected['suites'].items():
        baseline, advanced = suite['rows']
        assert advanced['recall_score'] > baseline['recall_score'], name
        assert baseline['memory_growth_bytes'] == 0
        if 'Stress' in name:
            assert advanced['compactions'] > 0
            assert advanced['prompt_tokens_processed'] < baseline['prompt_tokens_processed']
            assert suite['no_compact']['compactions'] == 0
            assert suite['no_compact']['prompt_tokens_processed'] > advanced['prompt_tokens_processed']
    receipt = {'verified_at': datetime.now(UTC).isoformat(), 'mode': 'offline',
               'required_tests': required.strip().splitlines()[-1],
               'all_tests': full.strip().splitlines()[-1], 'reproducible': True,
               'dataset_unchanged': True, 'dataset_sha256': dataset_hashes,
               'live_api_calls': 0, 'verification_scope': 'local code, datasets and reproducibility'}
    (ARTIFACTS / 'verification.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
