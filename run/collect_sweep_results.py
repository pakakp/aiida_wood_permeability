#!/usr/bin/env python3
"""
Collect results from parameter sweep.
Reads submitted_sweep.json and extracts permeability tensors.
"""
import json

from aiida import load_profile, orm
import pandas as pd

load_profile()

print('=' * 70)
print('Collecting Sweep Results')
print('=' * 70)

# ── LOAD SUBMISSION INFO ──────────────────────────────────────────────
submitted_file = 'submitted_sweep.json'

try:
    with open(submitted_file) as f:
        submitted = json.load(f)
except FileNotFoundError:
    print(f"\nERROR: {submitted_file} not found!")
    print('Run phase2_filter_sweep.py first')
    exit(1)

print(f"\nLoaded {len(submitted)} submitted workflows")

# ── COLLECT RESULTS ───────────────────────────────────────────────────
results = []
failed = []

for job in submitted:
    pk = job['workflow_pk']

    try:
        wc = orm.load_node(pk)
    except:
        print(f"  PK {pk}: Cannot load node - skipping")
        failed.append(job)
        continue

    if not (wc.exit_status == 0  or wc.exit_status == 410):
        status = wc.process_state if hasattr(wc, 'process_state') else 'unknown'
        print(f"  PK {pk}: State={status} - skipping")
        failed.append(job)
        continue

    # Get outputs
    try:
        tensor = wc.outputs.permeability_tensor.get_dict()
        actual_porosity = wc.outputs.actual_porosity.value
        vti_pk = wc.outputs.vti_file.pk

        results.append({
            'workflow_pk': pk,
            'cell_radius': job['cell_radius'],
            'resolution': job.get('resolution', 'N/A'),
            'random_seed': job.get('random_seed', 'N/A'),  #
            'target_porosity': job['porosity'],  #
            'actual_porosity': actual_porosity,  #
            'dSolid': job['dSolid'],
            'k_x': tensor['k_x'],
            'k_y': tensor['k_y'],
            'k_z': tensor['k_z'],
            'k_avg': (tensor['k_x'] + tensor['k_y'] + tensor['k_z']) / 3,
            'vti_file_pk': vti_pk,
            'structure_tar_pk': job['structure_tar_pk'],
            'dir_name': job['dir_name'],
        })

        print(f"PK {pk}: cellR={job['cell_radius']}, "
              f"target_por={job['porosity']:.2f}, "
              f"actual_por={actual_porosity:.4f}, "
              f"dSolid={job['dSolid']:.2f}")

    except Exception as e:
        print(f"PK {pk}: Error extracting results: {e}")
        failed.append(job)

# ── SAVE RESULTS ──────────────────────────────────────────────────────
if results:
    df = pd.DataFrame(results)

    # Sort by cell_radius, then actual_porosity, then dSolid
    df = df.sort_values(['cell_radius', 'actual_porosity', 'dSolid'])

    # Save to CSV
    csv_file = 'sweep_results.csv'
    df.to_csv(csv_file, index=False)

    print(f"\n{'=' * 70}")
    print('Results Summary:')
    print('=' * 70)
    print(df[['cell_radius', 'resolution', 'random_seed',
              'target_porosity', 'actual_porosity', 'dSolid',
              'k_x', 'k_y', 'k_z', 'k_avg']].to_string(index=False))

    print(f"\n{'=' * 70}")
    print(f"Collected: {len(results)}/{len(submitted)} workflows")
    print(f"Failed: {len(failed)} workflows")
    print(f"Saved to: {csv_file}")
    print(f"{'=' * 70}")

    # Summary statistics
    print('\nSummary by Cell Radius:')
    summary = df.groupby('cell_radius')['k_avg'].agg(['mean', 'std', 'min', 'max'])
    print(summary)

    print('\nSummary by Actual Porosity:')
    summary = df.groupby('actual_porosity')['k_avg'].agg(['mean', 'std', 'min', 'max'])
    print(summary)

    print('\nSummary by dSolid:')
    summary = df.groupby('dSolid')['k_avg'].agg(['mean', 'std', 'min', 'max'])
    print(summary)


else:
    print('\nNo completed workflows found!')

if failed:
    print(f"\nFailed workflows ({len(failed)}):")
    for job in failed:
        print(f"PK {job['workflow_pk']}: cellR={job['cell_radius']}, "
              f"por={job['porosity']}, dSolid={job['dSolid']}")

print('\n' + '=' * 70)
print('To retrieve VTI files:')
print('  verdi node repo cat <vti_file_pk> > structure.vti')
print('=' * 70)
