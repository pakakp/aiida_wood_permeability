#!/usr/bin/env python3
"""
Phase 2: Filter structures from generated_structures.json.
Submits one StructureFilterWorkChain per structure combination.
Writes filtered_structures.json for use by phase3_permeability.py.
"""
import json

from aiida import load_profile, orm
from aiida.engine import submit
from aiida_wood_penetration.workflows.structure_filter import StructureFilterWorkChain
from wood_config import load_config

load_profile()
cfg = load_config()

print('=' * 70)
print('Phase 2: Structure Filtering Sweep')
print('=' * 70)

# ── LOAD STRUCTURES ───────────────────────────────────────────────────
with open('generated_structures.json') as f:
    generated_structures = json.load(f)

print(f"\nLoaded {len(generated_structures)} structures")

# ── LOAD CODE ─────────────────────────────────────────────────────────
filter_code = orm.load_code(cfg['codes']['filter'])

# ── FILTER SWEEP ──────────────────────────────────────────────────────
p2 = cfg['phase2']
sigmas            = p2['sigmas']
filter_overrides  = p2['overrides']
FILTER_DEFAULTS   = p2['defaults']

submitted = []
print(f"\nSubmitting {len(generated_structures)} filter jobs...")

for struct in generated_structures:
    structure_tar = orm.load_node(struct['tar_pk'])

    for sigma in sigmas:
        params = dict(FILTER_DEFAULTS)
        params['sdf_sigma'] = sigma
        params.update(filter_overrides)

        filter_params = orm.Dict(dict=params)

        wc = submit(
            StructureFilterWorkChain,
            filter_code=filter_code,
            structure_tar=structure_tar,
            structure_dir_name=orm.Str(struct['dir_name']),
            filter_params=filter_params,
        )

        print(f"  Submitted: cellR={struct['cellR']}, "
              f"seed={struct['random_seed']}, Wallthickness={struct['cellWallThickness']} → PK {wc.pk}")

        submitted.append({
            # AiiDA provenance
            'workchain_pk':       wc.pk,
            'workchain_uuid':     str(wc.uuid),
            'filter_params_pk':   filter_params.pk,
            'filter_code':        filter_code.full_label,
            # Structure back-reference
            'tar_pk':             struct['tar_pk'],
            'dir_name':           struct['dir_name'],
            'job_pk':             struct.get('job_pk'),
            'job_uuid':           struct.get('job_uuid'),
            'wood_type':          struct['wood_type'],
            'cellR':              struct['cellR'],
            'cellWallThickness':  struct['cellWallThickness'],
            'resolution':         struct['resolution'],
            'random_seed':        struct['random_seed'],
            # Filter params
            'filter_params':      params,
        })

# ── SAVE ──────────────────────────────────────────────────────────────
output_file = 'submitted_filter_jobs.json'
with open(output_file, 'w') as f:
    json.dump(submitted, f, indent=2)

print(f"\n{'=' * 70}")
print(f"Total filter jobs submitted: {len(submitted)}")
print(f"Saved to: {output_file}")
print(f"{'=' * 70}")
print('\nMonitor:')
print('  verdi process list -a | grep StructureFilter')
print('\nCollect results when done:')
print('  python collect_filtered_structures.py')
