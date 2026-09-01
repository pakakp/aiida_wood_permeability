#!/usr/bin/env python3
"""
Phase 1: Generate wood structures (cubic and anisotropic dimensions)
"""
from aiida import load_profile, orm
from aiida_shell import launch_shell_job
import json
import tempfile
import itertools

from wood_config import load_config

load_profile()
cfg = load_config()

print("=" * 70)
print("Phase 1: Generate Wood Structures")
print("=" * 70)

wood_type = cfg['wood_type']

generator_code = orm.load_code(cfg['codes']['generator'])

BASE_JSON = cfg['paths']['base_json_template'].format(wood_type=wood_type)
with open(BASE_JSON) as f:
    base_data = json.load(f)
    base_structure_params = base_data[0] if isinstance(base_data, list) else base_data

print(f"\nBase parameters from: {BASE_JSON}")

# ── STRUCTURE VARIATIONS ──────────────────────────────────────────────
p1 = cfg['phase1']
cell_radii   = p1['cell_radii']
wall_thicks  = p1['wall_thicks']
resolutions  = p1['resolutions']
random_seeds = p1['random_seeds']

submitted_jobs = []
combinations   = list(itertools.product(cell_radii, wall_thicks, resolutions, random_seeds))

print(f"\nWood type: {wood_type}")
print(f"Submitting {len(combinations)} structure generation jobs...")

for cellR, wall_thick, res, seed in combinations:
    if isinstance(res, int):
        resolution_list = [res, res, res]
        res_label = f"{res}"
    else:
        resolution_list = list(res)
        res_label = f"{res[0]}x{res[1]}x{res[2]}"

    print(f"\n  Submitting: cellR={cellR}, res={res_label}, seed={seed}...")

    structure_params = base_structure_params.copy()
    structure_params['cellR']         = cellR
    structure_params['cellWallThick'] = wall_thick
    structure_params['sizeVolume']    = resolution_list
    structure_params['random_seed']   = seed

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump([structure_params], f)
        json_path = f.name

    structure_params_node = orm.SinglefileData(file=json_path)

    _, node = launch_shell_job(
        generator_code,
        arguments=[cfg['paths']['structure_generator_script'], '{params_json}', wood_type],
        nodes={'params_json': structure_params_node},
        filenames={'params_json': 'params.json'},
        outputs=['output_dir.txt', 'SaveWood.tar.gz'],
        metadata={'options': p1['metadata_options']},
        submit=True,
    )

    node.base.extras.set('wood_type', wood_type)
    node.base.extras.set('cellR', cellR)
    node.base.extras.set('resolution', resolution_list)
    node.base.extras.set('random_seed', seed)
    node.base.extras.set('cellWallThick', wall_thick)

    print(f"    Submitted as PK {node.pk}")

    submitted_jobs.append({
        'job_pk':           node.pk,
        'job_uuid':         str(node.uuid),
        'params_node_pk':   structure_params_node.pk,
        'generator_code':   generator_code.full_label,
        'base_json_path':   BASE_JSON,
        'wood_type':        wood_type,
        'cellR':            cellR,
        'cellWallThick':    wall_thick,
        'resolution':       resolution_list,
        'random_seed':      seed,
        'structure_params': structure_params,
    })

output_file = 'submitted_generation_jobs.json'
with open(output_file, 'w') as f:
    json.dump(submitted_jobs, f, indent=2)

print(f"\n{'=' * 70}")
print(f"Submitted {len(submitted_jobs)} jobs to daemon")
print(f"Saved to: {output_file}")
print(f"{'=' * 70}")
print("\nMonitor progress:")
print("  verdi process list -a | grep wood-microstructure")
print("\nCollect results when done:")
print("  python collect_generated_structures.py")
