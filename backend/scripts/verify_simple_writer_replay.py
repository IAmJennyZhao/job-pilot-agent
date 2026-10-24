"""Offline v6 compatibility/layout replay of saved comparison writer outputs.

No model calls, no production DB access, no approvals. Artifacts go into a new
subdirectory of the supplied private comparison directory; originals are untouched.
"""
import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import get_settings
from app.services import resume_v6, resume_layout, resume_compiler


def main(root):
    root = root.resolve()
    output = root / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-v6-offline')
    output.mkdir()
    get_settings().asset_storage_dir = str(output / 'assets')
    compiler, _ = resume_compiler.compiler()
    results = []
    with sqlite3.connect((root / 'evaluation.db').as_uri() + '?mode=ro', uri=True) as db:
        for path in sorted(root.glob('*/writer-output.json')):
            snapshot = json.loads((path.parent / 'snapshot.json').read_text(encoding='utf-8'))
            bank = json.loads(db.execute('SELECT bank FROM tailoring_source_versions WHERE id = ?', (snapshot['source_id'],)).fetchone()[0])
            plan = resume_v6.WriterPlan.model_validate_json(path.read_text(encoding='utf-8'))
            draft = resume_v6.compile_plan(plan, {'approved_evidence': snapshot['projection']})
            snapshot['generation_version'] = 6
            content = resume_v6.assemble(draft, snapshot)
            validation = resume_v6.report(draft, snapshot)
            metadata = resume_layout.presentation_metadata(content, snapshot, bank)
            tex, text = resume_layout.exports(resume_layout.document(content, snapshot, metadata))
            pdf, warnings = resume_compiler.compile_pdf(tex, compiler)
            layout = resume_compiler.inspect_pdf(pdf, text, warnings)
            folder = output / path.parent.name
            folder.mkdir()
            for name, value in [('content', content), ('validation', validation), ('layout', layout)]:
                (folder / f'{name}.json').write_text(json.dumps(value, indent=2), encoding='utf-8')
            (folder / 'resume.tex').write_text(tex, encoding='utf-8')
            (folder / 'resume.txt').write_text(text, encoding='utf-8')
            (folder / 'resume.pdf').write_bytes(pdf)
            results.append({'case': path.parent.name, 'local_checks_valid': validation['valid'],
                'layout_valid': layout['valid'], 'pages': layout['pages']})
    report = {'kind': 'offline replay of existing outputs, not fresh model evaluation', 'provider_calls': 0, 'cases': results}
    (output / 'results.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
    print('ARTIFACT_DIRECTORY ' + str(output))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('comparison_directory', type=Path)
    main(parser.parse_args().comparison_directory)
