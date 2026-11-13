import copy
import json
import unittest

from urd.analysis import analyze


def session(times, *, phases=None, gaps=None, **kwargs):
    frames = []
    clock = 0
    for index, duration in enumerate(times):
        clock += (gaps or {}).get(index, 0)
        frame = {'frame_id': index, 't_ns': clock, 'frame_ms': duration}
        if phases:
            frame['phase'] = phases[index]
        frames.append(frame)
        clock += round(duration * 1_000_000)
    return {'schema_version': 1, 'session_id': 'synthetic-test', 'synthetic': True,
            'metadata': {'clock_domain': 'session_monotonic'}, 'frames': frames,
            'events': [], 'captures': [], 'warnings': [], 'provenance': [], **kwargs}


class AnalysisTests(unittest.TestCase):
    def test_sustained_slowdown_uses_preceding_baseline(self):
        data = session([10] * 30 + [40] * 90 + [10] * 10)
        result = analyze(data)
        self.assertEqual(result['status'], 'incidents_detected')
        self.assertTrue(result['synthetic'])
        self.assertEqual(len(result['incidents']), 1)
        incident = result['incidents'][0]
        self.assertEqual(incident['frame_ids'], list(range(30, 120)))
        self.assertEqual(incident['baseline_ms'], 10)
        self.assertEqual(incident['peak_ms'], 40)
        self.assertEqual(incident['end_ns'], data['frames'][120]['t_ns'])

    def test_stable_slow_hardware_is_not_relative_anomaly(self):
        result = analyze(session([100] * 100))
        self.assertEqual(result['status'], 'no_anomaly')
        self.assertEqual(result['incidents'], [])

    def test_isolated_spike_and_small_absolute_jitter(self):
        result = analyze(session([10] * 30 + [40] + [10] * 20))
        self.assertEqual(result['incidents'][0]['frame_ids'], [30])
        self.assertEqual(analyze(session([1] * 30 + [2] + [1] * 20))['status'], 'no_anomaly')

    def test_high_variance_baseline_does_not_flag_normal_jitter(self):
        self.assertEqual(analyze(session([10, 20] * 60))['status'], 'no_anomaly')

    def test_excluded_phases_do_not_train_or_trigger_baseline(self):
        data = session([100] * 20 + [10] * 30 + [100] * 20 + [40] * 15,
                       phases=['warmup'] * 20 + ['gameplay'] * 30 + ['loading'] * 20 + ['gameplay'] * 15)
        self.assertEqual(analyze(data)['status'], 'no_anomaly')
        self.assertEqual(analyze(session([100] * 20, phases=['menu'] * 20))['status'], 'insufficient_data')

    def test_sparse_startup_cannot_establish_slowdown(self):
        self.assertEqual(analyze(session([10] * 3 + [40] * 3))['status'], 'insufficient_data')
        self.assertTrue(analyze(session([40] * 3))['limitations'])

    def test_gap_does_not_transfer_old_baseline_to_new_segment(self):
        data = session([10] * 30 + [40] * 30, gaps={30: 1_000_000_000})
        self.assertEqual(analyze(data)['status'], 'no_anomaly')

    def test_gap_splits_incidents_and_does_not_extend_duration(self):
        data = session([10] * 30 + [40] * 3 + [10] * 30 + [40] * 3,
                       gaps={33: 1_000_000_000})
        incidents = analyze(data)['incidents']
        self.assertEqual(len(incidents), 2)
        self.assertEqual(incidents[0]['end_ns'], data['frames'][32]['t_ns'] + 40_000_000)

    def test_frame_counter_reset_breaks_baseline_even_with_monotonic_time(self):
        data = session([10] * 30 + [40] * 30)
        for index, frame in enumerate(data['frames'][30:]):
            frame['frame_id'] = index
        self.assertEqual(analyze(data)['status'], 'no_anomaly')

    def test_exact_join_without_clock_and_no_untimed_guess(self):
        data = session([10] * 30 + [40])
        data['metadata']['clock_domain'] = 'unknown'
        data['events'] = [
            {'id': 'exact', 'kind': 'compile', 'message': 'compiling', 'frame_id': 30, 't_ns': None},
            {'id': 'untimed', 'kind': 'compile', 'message': 'compiling', 'frame_id': None, 't_ns': None},
            {'id': 'time', 'kind': 'compile', 'message': 'compiling', 'frame_id': None, 't_ns': 300_000_000},
        ]
        incident = analyze(data)['incidents'][0]
        self.assertEqual([row['event']['id'] for row in incident['events']], ['exact'])
        self.assertEqual(incident['events'][0]['association'], 'exact_frame')

    def test_contradictory_frame_time_not_joined(self):
        data = session([10] * 30 + [40])
        data['events'] = [{'id': 'bad', 'kind': 'compile', 'message': 'compile', 'frame_id': 30, 't_ns': 0}]
        data['captures'] = [{'path': '/local/bad.png', 'frame_id': 30, 't_ns': 0, 'uncertainty_ns': 0}]
        result = analyze(data)
        self.assertEqual(result['incidents'][0]['events'], [])
        self.assertEqual(result['incidents'][0]['captures'], [])
        self.assertTrue(any('disagree' in warning for warning in result['warnings']))

    def test_event_interval_starting_before_incident_overlaps(self):
        data = session([10] * 30 + [40])
        data['events'] = [{'id': 'long', 'kind': 'compile', 'message': 'compile', 'frame_id': 29,
                           't_ns': 290_000_000, 'duration_ms': 30}]
        row = analyze(data)['incidents'][0]['events'][0]
        self.assertEqual(row['event']['id'], 'long')
        self.assertEqual(row['association'], 'timestamp_overlap')

    def test_capture_uncertainty_is_explicit_and_boundary_is_half_open(self):
        data = session([10] * 30 + [40])
        data['captures'] = [
            {'path': '/local/uncertain.png', 'frame_id': None, 't_ns': 299_000_000, 'uncertainty_ns': 2_000_000},
            {'path': '/local/end.png', 'frame_id': None, 't_ns': 340_000_000, 'uncertainty_ns': 0},
        ]
        rows = analyze(data)['incidents'][0]['captures']
        self.assertEqual(len(rows), 1)
        self.assertIn('uncertain', rows[0]['association'])

    def test_correlations_remain_hypotheses_and_missing_gpu_stays_unknown(self):
        data = session([10] * 30 + [40])
        data['events'] = [{'id': 'compile', 'kind': 'shader_compile', 'message': 'compile', 'frame_id': 30, 't_ns': None}]
        incident = analyze(data)['incidents'][0]
        self.assertTrue(incident['hypotheses'])
        for hypothesis in incident['hypotheses']:
            self.assertEqual(hypothesis['status'], 'hypothesis')
            self.assertIn(hypothesis['confidence'], ['low', 'medium'])
            self.assertTrue(hypothesis['evidence_ids'])
            self.assertTrue(hypothesis['next_test'])
        self.assertTrue(any('GPU' in limitation for limitation in incident['limitations']))

    def test_uncertainty_window_includes_its_boundary(self):
        data = session([10] * 30 + [40])
        data['captures'] = [{'path': '/local/boundary.png', 'frame_id': None,
                             't_ns': 299_000_000, 'uncertainty_ns': 1_000_000}]
        rows = analyze(data)['incidents'][0]['captures']
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['association'], 'timestamp_uncertain')

    def test_frame_timestamp_uncertainty_is_honored(self):
        data = session([10] * 30 + [40])
        data['frames'][30]['uncertainty_ns'] = 50_500
        data['captures'] = [{'path': '/local/frame-edge.png', 'frame_id': 30,
                             't_ns': 299_980_000, 'uncertainty_ns': 0}]
        row = analyze(data)['incidents'][0]['captures'][0]
        self.assertIn('uncertain', row['association'])

    def test_deterministic_json_serializable_and_input_unchanged(self):
        data = session([10] * 30 + [40])
        before = copy.deepcopy(data)
        self.assertEqual(json.dumps(analyze(data), sort_keys=True, allow_nan=False),
                         json.dumps(analyze(data), sort_keys=True, allow_nan=False))
        self.assertEqual(data, before)

    def test_malformed_samples_cannot_poison_statistics(self):
        data = session([10] * 31 + [40] * 30)
        data['frames'][30]['frame_ms'] = float('nan')
        result = analyze(data)
        self.assertEqual(result['status'], 'no_anomaly')
        json.dumps(result, allow_nan=False)
        self.assertTrue(result['warnings'])


if __name__ == '__main__':
    unittest.main()
