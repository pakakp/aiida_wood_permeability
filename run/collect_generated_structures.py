#!/usr/bin/env python3
"""
Collect generated structures (handles both cubic and anisotropic)
"""
import argparse
import json

from aiida import load_profile, orm
from aiida.orm import CalcJobNode, QueryBuilder


# This is here to allow using simpler form for the image resolutions
def extract_resolution(params):
    """
    Extract resolution as [x, y, z] list from various formats.

    Returns [x, y, z] list regardless of input format.
    """
    if 'sizeVolume' in params:
        size_vol = params['sizeVolume']
        if isinstance(size_vol, list):
            return size_vol  # Already [x, y, z]
        else:
            return [size_vol, size_vol, size_vol]  # Convert single to cubic

    if 'resolution' in params:
        res = params['resolution']
        if isinstance(res, list):
            return res  # Already [x, y, z]
        else:
            return [res, res, res]  # Convert single to cubic

    return None

load_profile()

# ── ARGUMENT PARSING ──────────────────────────────────────────────────
parser = argparse.ArgumentParser(description='Collect generated structures from AiiDA')
parser.add_argument('--cellR', nargs='+', type=int,
                   help='Filter by cellR values (e.g., --cellR 14 16 18)')
parser.add_argument('--min-cellR', type=int,
                   help='Minimum cellR value')
parser.add_argument('--max-cellR', type=int,
                   help='Maximum cellR value')
parser.add_argument('--resolutionx', nargs='+', type=int,
                   help='Filter by resolution values')
parser.add_argument('--resolutiony', nargs='+', type=int,
                   help='Filter by resolution values')
parser.add_argument('--resolutionz', nargs='+', type=int,
                   help='Filter by resolution values')
parser.add_argument('--random-seed', nargs='+', type=int,
                   help='Filter by random seed values')
parser.add_argument('--limit', type=int, default=None,
                   help='Limit number of structures to collect (most recent first)')
parser.add_argument('--from-json', action='store_true',
                   help='Use submitted_generation_jobs.json instead of querying AiiDA')
parser.add_argument('--output', default='generated_structures.json',
                   help='Output file name (default: generated_structures.json)')

args = parser.parse_args()

print('=' * 70)
print('Collecting Generated Structures')
print('=' * 70)

# ── COLLECT FROM JSON OR AIIDA ────────────────────────────────────────
if args.from_json:
    # Load from submitted_generation_jobs.json
    try:
        with open('submitted_generation_jobs.json') as f:
            submitted_jobs = json.load(f)
        print(f"\nLoaded {len(submitted_jobs)} jobs from submitted_generation_jobs.json")

        # Get job nodes
        jobs = []
        for job_info in submitted_jobs:
            try:
                node = orm.load_node(job_info['job_pk'])
                if node.is_finished and node.exit_status in [0, 410]:
                    jobs.append(node)
            except:
                pass

    except FileNotFoundError:
        print('ERROR: submitted_generation_jobs.json not found!')
        exit(1)

else:
    # Query AiiDA directly
    try:
        generator_code = orm.load_code('wood-microstructure-tohtori@tohtori-AITW')
    except:
        try:
            generator_code = orm.load_code('wood-microstructure@localhost')
        except:
            print('ERROR: Could not find wood-microstructure code')
            exit(1)

    print(f"\nUsing code: {generator_code.label}@{generator_code.computer.label}")

    # Query jobs
    qb = QueryBuilder()
    qb.append(orm.Code, filters={'id': generator_code.pk}, tag='code')
    qb.append(
        CalcJobNode,
        with_incoming='code',
        filters={'attributes.exit_status': {'in': [0, 410]}},
        tag='job'
    )
    qb.order_by({'job': {'ctime': 'desc'}})

    if args.limit:
        qb.limit(args.limit)

    jobs = qb.all(flat=True)
    print(f"Found {len(jobs)} successful generation jobs")
generated_structures = []

print('\nProcessing jobs...')
for job in jobs:
    try:
        # Get outputs
        tar = job.outputs.SaveWood_tar_gz
        dirname_file = job.outputs.output_dir_txt

        with dirname_file.open() as f:
            dir_name = f.read().strip()

        # Get input parameters
        params_file = job.inputs.nodes.params_json
        with params_file.open() as f:
            params_data = json.load(f)
            params = params_data[0] if isinstance(params_data, list) else params_data

        # Extract parameters
        cellR = params.get('cellR')
        resolution_list = extract_resolution(params)  # Always returns [x, y, z]
        random_seed = params.get('random_seed')

        wood_type = job.base.extras.get('wood_type', 'unknown')

        if resolution_list is None:
            print(f"  failed PK {job.pk}: Could not extract resolution")
            continue
        # Determine if cubic
        is_cubic = (resolution_list[0] == resolution_list[1] == resolution_list[2])
        # Filter by cellR list
        if args.cellR and cellR not in args.cellR:
            continue

        # Filter by cellR range
        if args.min_cellR and cellR < args.min_cellR:
            continue
        if args.max_cellR and cellR > args.max_cellR:
            continue

        # Filter by resolution
        if args.resolutionx and resolution_list[0] not in args.resolutionx:
            continue
        if args.resolutiony and resolution_list[1] not in args.resolutiony:
            continue
        if args.resolutionz and resolution_list[2] not in args.resolutionz:
            continue

        # Filter by random seed
        if args.random_seed and random_seed not in args.random_seed:
            continue

        # Passed all filters
        generated_structures.append({
            'wood_type': wood_type,
            'cellR': cellR,
            'resolution': resolution_list,  # [x, y, z] format
            'is_cubic': is_cubic,  # Flag for filtering
            'random_seed': random_seed,
            'tar_pk': tar.pk,
            'dir_name': dir_name,
            'generation_pk': job.pk,
        })

        res_str = f"{resolution_list[0]}x{resolution_list[1]}x{resolution_list[2]}"
        cubic_str = '(cubic)' if is_cubic else '(anisotropic)'
        print(f"Success PK {job.pk}: {wood_type}, cellR={cellR}, res={res_str} {cubic_str}, seed={random_seed}")

    except Exception as e:
        print(f"Fail: PK {job.pk}: {e}")

# ── SAVE RESULTS ──────────────────────────────────────────────────────
if generated_structures:
    generated_structures.sort(key=lambda x: (x['cellR'], x['resolution'], x['random_seed'], x['wood_type']))

    with open(args.output, 'w') as f:
        json.dump(generated_structures, f, indent=2)

    print(f"\n{'=' * 70}")
    print(f"Collected {len(generated_structures)} structures")
    print(f"Saved to: {args.output}")
    print(f"{'=' * 70}")

    # Summary
    cubic_count = sum(1 for s in generated_structures if s['is_cubic'])
    aniso_count = len(generated_structures) - cubic_count

    print(f"  Cubic: {cubic_count}")
    print(f"  Anisotropic: {aniso_count}")
    print(f"Saved to: generated_structures.json")
    print(f"{'=' * 70}")
    print('\nNext step:')
    print('  python phase2_filter_sweep.py')
else:
    print('\nNo structures matched the filters!')
