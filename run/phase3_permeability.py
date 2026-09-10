#!/usr/bin/env python3
"""
Phase 3: Permeability sweep over filtered_structures.json.
Writes submitted_permeability_sweep.json.
"""
import itertools
import json

from aiida import load_profile, orm
from aiida.engine import submit
from wood_config import load_config, resolve_metadata_options

from aiida_wood_permeability.workflows.olb_permeability import OLBPermeabilityWorkChain

load_profile()
cfg = load_config()

print('=' * 70)
print('Phase 3: Permeability Tensor Sweep')
print('=' * 70)

with open('filtered_structures.json') as f:
    filtered_structures = json.load(f)

print(f"\nLoaded {len(filtered_structures)} filtered structures")

permeability_code = orm.load_code(cfg['codes']['permeability'])

# ── PERMEABILITY SWEEP ────────────────────────────────────────────────
p3 = cfg['phase3']
d_solids               = p3['d_solids']
guozhaos               = p3['guozhaos']
permeability_overrides = p3['overrides']
PERMEABILITY_DEFAULTS  = p3['defaults']

metadata_options = orm.Dict(dict=resolve_metadata_options(p3['metadata_options']))

submitted = []
param_combos = list(itertools.product(d_solids, guozhaos))
print(f"\nSubmitting {len(filtered_structures)} × {len(d_solids)} × {len(guozhaos)} permeability jobs...")

for flt in filtered_structures:
    vti_file = orm.load_node(flt['vti_pk'])
    resolution_for_solver = min(flt['resolution']) / 1

    for (d_solid, guozhao) in param_combos:
        params = dict(PERMEABILITY_DEFAULTS)
        params.update(permeability_overrides)   # applied first, so swept values below always win
        params['dSolid']         = d_solid
        params['resolution']     = resolution_for_solver
        params['uniformguozhao'] = guozhao

        permeability_params = orm.Dict(dict=params)

        wc = submit(
            OLBPermeabilityWorkChain,
            code=permeability_code,
            vti_file=vti_file,
            parameters=permeability_params,
            metadata_options=metadata_options,
        )

        print(f"  Submitted: "
              f"cellR={flt['cellR']}, cellwallthickness={flt['cellWallThickness']}, seed={flt['random_seed']}, "
              f"dSolid={d_solid}, uniformguozhao={guozhao} → PK {wc.pk}")

        submitted.append({
            'workchain_pk':            wc.pk,
            'workchain_uuid':          str(wc.uuid),
            'permeability_params_pk':  permeability_params.pk,
            'permeability_code':       permeability_code.full_label,
            'filter_workchain_pk':     flt['workchain_pk'],
            'filter_workchain_uuid':   flt['workchain_uuid'],
            'filter_params_pk':        flt['filter_params_pk'],
            'filter_params':           flt['filter_params'],
            'vti_pk':                  flt['vti_pk'],
            'actual_porosity':         flt['actual_porosity'],
            'tar_pk':                  flt.get('tar_pk'),
            'job_pk':                  flt.get('job_pk'),
            'job_uuid':                flt.get('job_uuid'),
            'wood_type':               flt.get('wood_type', cfg['wood_type']),
            'cellR':                   flt['cellR'],
            'cellWallThickness':       flt['cellWallThickness'],
            'resolution':              flt['resolution'],
            'random_seed':             flt['random_seed'],
            'resolution_solver':       resolution_for_solver,
            'upsample_final':          flt['filter_params']['upsample_final'],
            'porosity':                flt['filter_params']['porosity'],
            'd_solid':                 d_solid,
            'uniformguozhao':          guozhao,
            'permeability_params':     params,
        })

output_file = 'submitted_permeability_sweep.json'
with open(output_file, 'w') as f:
    json.dump(submitted, f, indent=2)

print(f"\n{'=' * 70}")
print(f"Total permeability jobs submitted: {len(submitted)}")
print(f"Saved to: {output_file}")
print(f"{'=' * 70}")
print('\nMonitor:')
print('  verdi process list -a | grep SingleStructurePermeability')
print('\nCollect results when done:')
print('  python collect_permeability_results.py')
