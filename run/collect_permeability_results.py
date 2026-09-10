#!/usr/bin/env python3
"""
Collect permeability results into permeability_results.json and sweep_results.csv.
Merges with any existing file, deduplicating by workchain_pk.
"""
import json
import os

from aiida import load_profile, orm

load_profile()

print('=' * 70)
print('Collecting permeability results')
print('=' * 70)

with open('submitted_permeability_sweep.json') as f:
    submitted = json.load(f)

print(f"\nChecking {len(submitted)} submitted jobs...")

output_file = 'permeability_results.json'
if os.path.exists(output_file):
    with open(output_file) as f:
        existing = json.load(f)
    existing_pks = {e['workchain_pk'] for e in existing}
    print(f"Found {len(existing)} existing entries in {output_file}")
else:
    existing = []
    existing_pks = set()

new_entries = []
n_ok = n_fail = n_running = n_already = 0

for job in submitted:
    pk = job['workchain_pk']
    if pk in existing_pks:
        n_already += 1
        continue

    node = orm.load_node(pk)

    if not node.is_finished:
        print(f"Still running: PK {pk} (cellR={job['cellR']}, seed={job['random_seed']}, "
              f"por={job['porosity']}, dSolid={job['d_solid']})")
        n_running += 1
        continue

    if not node.is_finished_ok:
        print(f"Failed: PK {pk} (cellR={job['cellR']}, seed={job['random_seed']}, "
              f"por={job['porosity']}, dSolid={job['d_solid']}) exit={node.exit_status}")
        n_fail += 1
        continue

    tensor = node.outputs.permeability_tensor.get_dict()
    entry  = dict(job)
    entry['permeability_tensor'] = tensor
    entry['k_x']   = tensor['k_x']
    entry['k_y']   = tensor['k_y']
    entry['k_z']   = tensor['k_z']
    entry['k_avg'] = (tensor['k_x'] + tensor['k_y'] + tensor['k_z']) / 3
    new_entries.append(entry)

    print(f"PK {pk}: cellR={job['cellR']}, seed={job['random_seed']}, "
          f"por={job['porosity']}, dSolid={job['d_solid']} → "
          f"k_avg={entry['k_avg']:.3e} m²")
    n_ok += 1

merged = existing + new_entries
with open(output_file, 'w') as f:
    json.dump(merged, f, indent=2)

print(f"\n{'=' * 70}")
print(f"Newly collected : {n_ok}")
print(f"Already present : {n_already}")
print(f"Failed          : {n_fail}")
print(f"Still running   : {n_running}")
print(f"Total in file   : {len(merged)}")
print(f"Saved to        : {output_file}")
print(f"{'=' * 70}")

if merged:
    # ── CSV summary ───────────────────────────────────────────────
    try:
        import pandas as pd
        rows = [{
            'workflow_pk':     e['workchain_pk'],
            'wood_type':       e.get('wood_type', ''),
            'cellR':           e['cellR'],
            'resolution':      'x'.join(str(r) for r in e['resolution']),
            'random_seed':     e['random_seed'],
            'target_porosity': e['porosity'],
            'actual_porosity': e['actual_porosity'],
            'd_solid':         e['d_solid'],
            'k_x':             e['k_x'],
            'k_y':             e['k_y'],
            'k_z':             e['k_z'],
            'k_avg':           e['k_avg'],
        } for e in merged]

        df = pd.DataFrame(rows).sort_values(
            ['cellR', 'random_seed', 'actual_porosity', 'd_solid']
        )
        csv_file = 'sweep_results.csv'
        df.to_csv(csv_file, index=False)
        print(f"\nCSV saved to: {csv_file}")
        print(f"\n{df[['cellR','resolution','random_seed','actual_porosity','d_solid','k_x','k_y','k_z','k_avg']].to_string(index=False)}")
    except ImportError:
        print('\n(Install pandas for CSV output: pip install pandas)')
        print(f"\n{'cellR':>6} {'seed':>6} {'porosity':>9} {'actual_por':>10} "
              f"{'dSolid':>8} {'k_x':>12} {'k_y':>12} {'k_z':>12} {'k_avg':>12}")
        print('-' * 90)
        for e in sorted(merged, key=lambda x: (x['cellR'], x['random_seed'], x['porosity'], x['d_solid'])):
            print(f"  {e['cellR']:>4} {e['random_seed']:>6} {e['porosity']:>9.3f} "
                  f"{e['actual_porosity']:>10.4f} {e['d_solid']:>8.3f} "
                  f"{e['k_x']:>12.3e} {e['k_y']:>12.3e} {e['k_z']:>12.3e} {e['k_avg']:>12.3e}")

if n_running:
    print('\nSome jobs still running — re-run this script when they finish.')
