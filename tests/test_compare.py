import copy
import json
import unittest

from urd.compare import compare_sessions


def run(values, **metadata):
    common = {
        'scenario': 'fixed-scene', 'hardware': {'cpu': 'one', 'gpu': 'two'},
        'settings': {'resolution': '1920x1080', 'vsync': False},
        'run_group': 'controlled-A', 'collector': 'fixed-v1', 'sample_kind': 'game',
        'cache_state': 'warm', 'driver': '1.0', 'power_profile': 'fixed',
        'frame_generation': False, 'replay': 'input-v1',
        'scenario_frame_range': [0, len(values) - 1], 'scenario_duration_ms': 1000,
        'clock_domain': 'unknown', 'build': 'A', **metadata,
    }
    clock = 0
    frames = []
    for index, value in enumerate(values):
        frames.append({'frame_id': index, 't_ns': clock, 'frame_ms': value, 'phase': 'gameplay'})
        clock += round(value * 1_000_000)
    return {'schema_version': 1, 'session_id': 'run', 'synthetic': True,
            'metadata': common, 'frames': frames, 'events': [], 'captures': [], 'warnings': []}


class CompareTests(unittest.TestCase):
    def test_controlled_improvement_allows_different_builds_and_clocks(self):
        result = compare_sessions(run([20] * 60, build='A'), run([15] * 60, build='B', clock_domain='different'))
        self.assertEqual(result['status'], 'improvement')
        self.assertTrue(result['comparable'])
        self.assertEqual(result['metrics']['p50']['delta_ms'], -5)
        self.assertEqual(result['metrics']['p50']['delta_pct'], -25)
        self.assertEqual(result['statistical_significance'], 'not_established')

    def test_regression_and_small_changes(self):
        self.assertEqual(compare_sessions(run([10] * 60), run([15] * 60))['status'], 'regression')
        self.assertEqual(compare_sessions(run([10] * 60), run([10.2] * 60))['status'], 'no_material_change')
        self.assertEqual(compare_sessions(run([1] * 60), run([1.5] * 60))['status'], 'no_material_change')

    def test_every_required_condition_is_checked(self):
        keys = ['scenario', 'hardware', 'settings', 'run_group', 'collector', 'sample_kind',
                'cache_state', 'driver', 'power_profile', 'frame_generation', 'replay']
        for key in keys:
            with self.subTest(key=key):
                before, after = run([10] * 60), run([15] * 60)
                del after['metadata'][key]
                result = compare_sessions(before, after)
                self.assertEqual(result['status'], 'inconclusive')
                self.assertTrue(any(key in reason for reason in result['reasons']))
                self.assertEqual(result['metrics'], {})
                after['metadata'][key] = 'different'
                self.assertEqual(compare_sessions(before, after)['status'], 'inconclusive')

    def test_missing_coverage_and_different_duration_are_inconclusive(self):
        before, after = run([10] * 60), run([15] * 60)
        del after['metadata']['scenario_frame_range']
        self.assertEqual(compare_sessions(before, after)['status'], 'inconclusive')
        after = run([15] * 60, scenario_duration_ms=2000)
        self.assertEqual(compare_sessions(before, after)['status'], 'inconclusive')
        after = run([15] * 60, scenario_frame_range=[60, 119])
        self.assertEqual(compare_sessions(before, after)['status'], 'inconclusive')

    def test_unequal_or_insufficient_samples_cannot_be_regression(self):
        self.assertEqual(compare_sessions(run([10] * 60), run([15] * 30))['status'], 'inconclusive')
        self.assertEqual(compare_sessions(run([10] * 10), run([15] * 10))['status'], 'inconclusive')
        after = run([15] * 60)
        after['frames'].pop()
        self.assertEqual(compare_sessions(run([10] * 60), after)['status'], 'inconclusive')

    def test_loading_menu_warmup_not_pooled(self):
        before, after = run([10] * 60), run([15] * 60)
        for data in [before, after]:
            extras = [{'frame_id': 100 + i, 't_ns': 10_000_000_000 + i * 100_000_000,
                       'frame_ms': 100, 'phase': phase}
                      for i, phase in enumerate(['loading', 'menu', 'warmup'])]
            data['frames'].extend(extras)
        result = compare_sessions(before, after)
        self.assertEqual(result['status'], 'regression')
        self.assertEqual(result['coverage']['before']['samples'], 60)
        self.assertEqual(result['metrics']['p99']['before_ms'], 10)

    def test_interrupted_gameplay_is_inconclusive(self):
        before, after = run([10] * 60), run([15] * 60)
        after['frames'][30]['phase'] = 'loading'
        self.assertEqual(compare_sessions(before, after)['status'], 'inconclusive')
        after = run([15] * 60)
        for frame in after['frames'][30:]:
            frame['t_ns'] += 1_000_000_000
        self.assertEqual(compare_sessions(before, after)['status'], 'inconclusive')

    def test_nonfinite_or_nonpositive_sample_is_not_silently_dropped(self):
        for value in [float('nan'), float('inf'), 0, -1, True]:
            with self.subTest(value=value):
                after = run([15] * 60)
                after['frames'][30]['frame_ms'] = value
                result = compare_sessions(run([10] * 60), after)
                self.assertEqual(result['status'], 'inconclusive')
                json.dumps(result, allow_nan=False)

    def test_real_and_synthetic_never_compared_as_valid(self):
        before, after = run([10] * 60), run([15] * 60)
        after['synthetic'] = False
        result = compare_sessions(before, after)
        self.assertEqual(result['status'], 'inconclusive')
        self.assertIsNone(result['synthetic'])

    def test_frame_generation_modes_not_combined(self):
        self.assertEqual(compare_sessions(run([10] * 60), run([15] * 60, frame_generation=True))['status'], 'inconclusive')
        self.assertEqual(compare_sessions(run([10] * 60), run([15] * 60, sample_kind='display'))['status'], 'inconclusive')

    def test_noisy_pair_gets_explicit_variance_and_repetition_caveats(self):
        result = compare_sessions(run([10, 40] * 30), run([11, 45] * 30))
        self.assertTrue(any('variab' in text.lower() for text in result['limitations']))
        self.assertTrue(any('repeat' in text.lower() for text in result['limitations']))
        self.assertEqual(result['statistical_significance'], 'not_established')

    def test_percentiles_are_interpolated_and_tail_uncertainty_explicit(self):
        result = compare_sessions(run(list(range(1, 61))), run(list(range(1, 61))))
        self.assertEqual(result['metrics']['p50']['before_ms'], 30.5)
        self.assertAlmostEqual(result['metrics']['p95']['before_ms'], 57.05)
        self.assertTrue(any('p99' in text for text in result['limitations']))

    def test_mixed_median_improvement_and_tail_regression_is_explicit(self):
        result = compare_sessions(run([10] * 60), run([8] * 59 + [40]))
        self.assertEqual(result['status'], 'mixed_change')
        self.assertLess(result['metrics']['p50']['delta_ms'], 0)
        self.assertGreater(result['metrics']['p99']['delta_ms'], 0)

    def test_overflowing_effect_size_is_inconclusive_json(self):
        before = run([1e-307] * 60)
        for index, frame in enumerate(before['frames']):
            frame['t_ns'] = index
        result = compare_sessions(before, run([10] * 60))
        self.assertEqual(result['status'], 'inconclusive')
        json.dumps(result, allow_nan=False)

    def test_deterministic_and_no_input_mutation(self):
        before, after = run([10] * 60), run([15] * 60)
        original = copy.deepcopy((before, after))
        self.assertEqual(json.dumps(compare_sessions(before, after), sort_keys=True, allow_nan=False),
                         json.dumps(compare_sessions(before, after), sort_keys=True, allow_nan=False))
        self.assertEqual((before, after), original)


if __name__ == '__main__':
    unittest.main()
