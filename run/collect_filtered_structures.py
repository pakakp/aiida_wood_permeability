#!/usr/bin/env python3
"""
Collect filter results into filtered_structures.json.
Merges with any existing file, deduplicating by workchain_pk.
"""
import json
import os

from aiida import load_profile, orm

load_profile()

print('=' * 70)
print('Collecting filtered structure results')
print('=' * 70)

with open('submitted_filter_jobs.json') as f:
    submitted = json.load(f)

print(f"\nChecking {len(submitted)} submitted jobs...")

output_file = 'filtered_structures.json'
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
        print(f"  Still running: PK {pk} (cellR={job['cellR']}, seed={job['random_seed']}, por={job['porosity']})")
        n_running += 1
        continue

    if not node.is_finished_ok:
        print(f"  Failed: PK {pk} (cellR={job['cellR']}, seed={job['random_seed']}, por={job['porosity']}) exit={node.exit_status}")
        n_fail += 1
        continue

    vti_node        = node.outputs.vti_file
    actual_porosity = node.outputs.actual_porosity.value

    entry = dict(job)
    entry['vti_pk']          = vti_node.pk
    entry['vti_uuid']        = str(vti_node.uuid)
    entry['actual_porosity'] = actual_porosity
    new_entries.append(entry)

    print(f" PK {pk}: cellR={job['cellR']}, seed={job['random_seed']}, "
          f"por={job['porosity']} → actual_por={actual_porosity:.4f}, vti_pk={vti_node.pk}")
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
if n_running:
    print('\nSome jobs still running — re-run this script when they finish.')
elif n_ok > 0 or n_already > 0:
    print('\nRun next step:')
    print('  python phase3_permeability.py')
