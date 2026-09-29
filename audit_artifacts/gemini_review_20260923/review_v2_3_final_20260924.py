"""Re-use independent probes, changing only their now-repaired expectations."""
from pathlib import Path

HERE = Path(__file__).resolve().parent
source_path = HERE / 'review_v2_3_followup_20260924.py'
source = source_path.read_text(encoding='utf-8')
replacements = {
    "OUT = HOME / 'v2_3_followup_review_20260924'": "OUT = HOME / 'v2_3_final_review_20260924'",
    "assert boundaries[1]['result']['top_miss_rate'] == 100": "assert boundaries[1]['result']['top_miss_rate'] == 0",
    "assert boundaries[4]['result']['bottom_miss_rate'] == 100": "assert boundaries[4]['result']['bottom_miss_rate'] == 0",
    "# Explicit re-run of repaired regression scenarios and mutation assertions.": """assert evidence['incorrect_mode_a_first_fill_rows'] == 0
    assert sum(r['reported_actual_deposit_dt'] == 'INHERITED' for r in timestamp_checks) == 24
    assert all(x['result']['top_miss_rate'] == 0 and x['result']['bottom_miss_rate'] == 0 for x in boundaries)
    evidence['final_two_repairs_passed'] = True

    # Explicit re-run of repaired regression scenarios and mutation assertions.""",
}
for old, new in replacements.items():
    assert source.count(old) == 1, old
    source = source.replace(old, new)
exec(compile(source, str(source_path), 'exec'), {'__file__': str(source_path), '__name__': '__main__'})
