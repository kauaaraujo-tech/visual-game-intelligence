"""Readable previews must preserve the complete machine-readable evidence."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from urd.report import markdown, write_report


def synthetic_report(event_count=10000):
    events = [
        {'association': 'exact_frame', 'event': {
            'id': f'event-{index:05d}', 'kind': 'pipe_wait_ms',
            'frame_id': 1000, 'duration_ms': index % 20,
            'source': {'file': 'SYNTHETIC.csv', 'line': index + 2},
            'message': 'SYNTHETIC measured wait',
        }}
        for index in range(event_count)
    ]
    frame_ids = list(range(1000, 9000, 2))
    return {
        'schema_version': 1, 'session_id': 'SYNTHETIC-long-report', 'synthetic': True,
        'status': 'incidents_detected', 'metadata': {}, 'provenance': [],
        'limitations': [], 'warnings': [],
        'incidents': [{
            'id': 'incident-0001', 'start_ns': 0, 'end_ns': 100000000,
            'frame_ids': frame_ids, 'baseline_ms': 16, 'peak_ms': 80, 'threshold_ms': 24,
            'events': events, 'captures': [], 'limitations': [],
            'hypotheses': [{
                'claim': 'SYNTHETIC correlation requires a controlled test.', 'confidence': 'low',
                'evidence_ids': [row['event']['id'] for row in events]
                                + [f'frame:{frame}' for frame in frame_ids],
                'next_test': 'Repeat the controlled synthetic input.',
            }],
        }],
        'source_correlations': [
            {'evidence_id': row['event']['id'], 'metric': 'pipe_wait_ms',
             'url': 'https://example.invalid/SYNTHETIC-source#L10'}
            for row in events
        ],
        'session_context': {'events': [row['event'] for row in events], 'captures': []},
        'reproduction': {'command': 'python -m vgi analyze SYNTHETIC.json',
                         'requirements': 'Synthetic fixture only'},
    }


class ReportPreviewTests(unittest.TestCase):
    def test_long_report_has_bounded_previews_and_explicit_omissions(self):
        report = synthetic_report()
        before = copy.deepcopy(report)
        text = markdown(report)
        self.assertLess(len(text.encode('utf-8')), 20000)
        self.assertLess(max(map(len, text.splitlines())), 4000)
        event_lines = [line for line in text.splitlines() if ' — pipe\\_wait\\_ms;' in line]
        self.assertEqual(len(event_lines), 8)
        self.assertIn('9992 evento(s) omitido(s)', text)
        self.assertIn('3988 omitido(s)', text)
        self.assertIn('13988 omitido(s)', text)
        self.assertIn('10000 referência(s)', text)
        self.assertIn('9988 omitido(s)', text)
        self.assertEqual(text.count('https://example.invalid/SYNTHETIC-source#L10'), 1)
        self.assertIn('report.json', text)
        self.assertIn('não indica causa', text)
        self.assertIn('8998', text)
        self.assertNotIn('frame:5000', text)
        self.assertEqual(report, before)
        self.assertEqual(markdown(report), text)

    def test_event_preview_uses_measured_duration_with_stable_ties(self):
        report = synthetic_report(12)
        rows = report['incidents'][0]['events']
        for row, duration in zip(rows, [None, 2, 20, 5, 20, 1, 30, 4, 3, 6, 40, None]):
            row['event']['duration_ms'] = duration
        text = markdown(report)
        lines = [line for line in text.splitlines() if ' — pipe\\_wait\\_ms;' in line]
        self.assertEqual([line.split()[1] for line in lines],
                         ['event-00010', 'event-00006', 'event-00002', 'event-00004',
                          'event-00009', 'event-00003', 'event-00007', 'event-00008'])
        self.assertIn('40.000 ms', lines[0])
        self.assertIn('4 evento(s) omitido(s)', text)

    def test_source_groups_keep_distinct_metrics_and_targets(self):
        report = synthetic_report(4)
        refs = report['source_correlations']
        refs[2]['metric'] = 'gpu_behind_ms'
        refs[3]['url'] = 'https://example.invalid/SYNTHETIC-other#L20'
        text = markdown(report)
        source_section = text.split('## Referências no código')[1].split('## Contexto da sessão')[0]
        self.assertEqual(source_section.count('https://example.invalid/SYNTHETIC-source#L10'), 2)
        self.assertEqual(source_section.count('https://example.invalid/SYNTHETIC-other#L20'), 1)
        self.assertIn('2 referência(s)', source_section)
        for index in range(4):
            self.assertIn(f'event-{index:05d}', source_section)
        self.assertIn('não identificam código defeituoso', source_section)

    def test_small_lists_are_complete_and_json_keeps_all_large_evidence(self):
        small = synthetic_report(2)
        small['incidents'][0]['frame_ids'] = [1000, 1002, 1004]
        small['incidents'][0]['hypotheses'][0]['evidence_ids'] = ['event-00000', 'event-00001']
        text = markdown(small)
        self.assertIn(r'Quadros: \[1000, 1002, 1004\]', text)
        self.assertNotIn('omitido(s)', text)
        report = synthetic_report()
        with tempfile.TemporaryDirectory() as directory:
            write_report(report, directory)
            saved = json.loads((Path(directory) / 'report.json').read_text(encoding='utf-8'))
            self.assertEqual(saved, report)
            saved_text = (Path(directory) / 'report.md').read_text(encoding='utf-8')
            self.assertLess(len(saved_text.encode('utf-8')), 20000)


if __name__ == '__main__':
    unittest.main()
