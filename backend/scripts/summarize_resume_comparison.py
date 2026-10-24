"""Offline measurements and a private review packet for compare_resume_pipelines.py."""
import argparse
import json
from pathlib import Path


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def main(root):
    root = root.resolve()
    assert root.is_relative_to(Path(__file__).resolve().parents[1] / 'storage' / 'writing-evaluation')
    integrity = read(root / 'integrity.json')
    assert integrity['production_unchanged']
    results = read(root / 'results.json')
    rows = []
    packet = ['# Resume pipeline comparison — private review packet', '',
              'Experimental drafts only. None is human-approved. Model reviewer verdicts are not ground truth.', '',
              'Compare factual support, relevance, concision, repetition and how much editing you would need.']
    for case in results:
        folder = root / case['case']
        packet += ['', '## ' + case['case'], '']
        for arm in ('current', 'writer', 'reviewed'):
            row = {'case': case['case'], 'pipeline': arm, **case.get(arm, {})}
            if arm == 'current':
                run = read(folder / 'current-run.json')
                metadata = [s['metadata'] for s in run['stages']]
            else:
                names = ['writer'] if arm == 'writer' else ['writer', 'review', 'repair', 'recheck']
                metadata = [read(folder / (name + '-metadata.json')) for name in names if (folder / (name + '-metadata.json')).exists()]
                row['calls'] = len(metadata) + sum((folder / (name + '-failure.json')).exists() and not (folder / (name + '-metadata.json')).exists() for name in names)
            row['input_tokens'] = sum((m.get('usage') or {}).get('input_tokens', 0) for m in metadata)
            row['output_tokens'] = sum((m.get('usage') or {}).get('output_tokens', 0) for m in metadata)
            row['cached_input_tokens'] = sum(((m.get('usage') or {}).get('input_tokens_details') or {}).get('cached_tokens', 0) for m in metadata)
            row['total_tokens'] = row['input_tokens'] + row['output_tokens']
            packet += ['### ' + arm, '', 'Status: ' + row.get('state', 'not run'), '']
            content_path = folder / arm / 'content.json'
            if content_path.exists():
                content = read(content_path)
                bullets = content['draft']['bullets']
                row['bullets'] = len(bullets)
                row['bullet_words'] = sum(len(b['text'].split()) for b in bullets)
                row['mean_bullet_words'] = round(row['bullet_words'] / max(1, len(bullets)), 1)
                row['records'] = len(content['records'])
                row['skills'] = len(content['draft']['skills'])
                pdf = folder / arm / 'resume.pdf'
                if pdf.exists():
                    packet += [f'[Open PDF]({pdf.as_posix()})', '']
                    import pymupdf
                    with pymupdf.open(pdf) as document:
                        row['margin_findings'] = []
                        for index, page in enumerate(document):
                            page.get_pixmap(matrix=pymupdf.Matrix(1.1, 1.1)).save(folder / arm / f'page-{index+1}.png')
                            for block in page.get_text('dict')['blocks']:
                                for line in block.get('lines', []):
                                    for span in line['spans']:
                                        x0, y0, x1, y1 = span['bbox']
                                        if x0 < 41 or x1 > 571 or y0 < 24 or y1 > 768:
                                            row['margin_findings'].append({'page': index+1, 'text': span['text'], 'bbox': span['bbox']})
                packet += [f"- **{b['record_id']}**: {b['text']}" for b in bullets]
                packet += ['', 'Skills: ' + ', '.join(s['name'] for s in content['draft']['skills']), '']
            rows.append(row)
    output = {'integrity': integrity, 'rows': rows,
              'note': 'Reviewed totals include the shared writer call. Do not sum all arms to infer actual billed calls/tokens. Single sample per case; timings exclude PDF rendering.'}
    (root / 'measurements.json').write_text(json.dumps(output, indent=2), encoding='utf-8')
    (root / 'review-packet.md').write_text('\n'.join(packet), encoding='utf-8')
    print(json.dumps(output))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    main(parser.parse_args().root)
