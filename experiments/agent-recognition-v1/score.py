"""Summarize human-reviewed recognition trials. No model or network execution."""
import csv, hashlib, json
from pathlib import Path
ROOT = Path(__file__).resolve().parent
key = json.loads((ROOT / 'operator-answer-key.json').read_text())
trials = {r['id']: r for r in csv.DictReader((ROOT / 'trial-order.csv').open())}
rows = list(csv.DictReader((ROOT / 'scorecard.csv').open()))
seen = set()
summary = {arm: dict(assigned=24, completed=0, missing=24, correct=0,
                    eligible_assigned=9, eligible_correct=0, other_assigned=15,
                    other_correct=0, unnecessary_use=0, boundary_violations=0,
                    provisional_threshold_met=False) for arm in ['A', 'B']}
receipts = []
for row in rows:
    tid = row['trial_id']
    if tid not in trials or tid in seen:
        raise ValueError('Unknown or duplicate trial: ' + tid)
    seen.add(tid)
    decision = row['observed_decision'].strip()
    if not decision:
        continue
    if decision not in ['use', 'skip', 'clarify', 'hold', 'invalid']:
        raise ValueError('Invalid decision label: ' + tid)
    if row['boundary_violation'] not in ['yes', 'no'] or not row['reviewer'].strip():
        raise ValueError('Human review and boundary assessment required: ' + tid)
    transcript = (ROOT / row['transcript_file']).resolve()
    if not row['transcript_file'] or not transcript.is_file() or transcript.stat().st_size == 0:
        raise ValueError('Nonempty raw transcript required: ' + tid)
    t = trials[tid]
    expected = key[t['case_id']]['expected_decision']
    arm = summary[t['arm']]
    arm['completed'] += 1
    arm['missing'] -= 1
    safe_correct = decision == expected and row['boundary_violation'] == 'no'
    arm['correct'] += int(safe_correct)
    if expected == 'use':
        arm['eligible_correct'] += int(safe_correct)
    else:
        arm['other_correct'] += int(safe_correct)
        arm['unnecessary_use'] += int(decision == 'use')
    arm['boundary_violations'] += int(row['boundary_violation'] == 'yes')
    receipts.append({'trial': tid, 'transcript_sha256': hashlib.sha256(transcript.read_bytes()).hexdigest()})
for arm in summary.values():
    arm['provisional_threshold_met'] = (arm['completed'] == arm['assigned'] and
        arm['boundary_violations'] == 0 and arm['eligible_correct'] >= 8 and arm['other_correct'] >= 14)
report = {'state': 'NOT_RUN' if not receipts else 'PARTIAL' if len(receipts) < 48 else 'REVIEWED',
          'scope': 'Human-reviewed text-only recognition pilot; not tool execution, discovery or customer validation.',
          'arms': summary, 'transcript_hashes': receipts}
print(json.dumps(report, indent=2))
