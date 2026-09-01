#!/usr/bin/env python3
"""
Submit the fully automated generation + filter + permeability sweep.
"""
from aiida import load_profile, orm
from aiida.engine import submit
from aiida_wood_permeability.workflows.wood_permeability import WoodPermeabilityWorkChain

from wood_config import load_config, resolve_metadata_options

load_profile()
cfg = load_config()

print("=" * 70)
print("Wood Permeability: Automated Generation + Filter + Permeability Sweep")
print("=" * 70)

# ── WOOD TYPE AND BASE PARAMETERS ─────────────────────────────────────
wood_type = cfg['wood_type']
base_params = orm.SinglefileData(
    file=cfg['paths']['base_json_template'].format(wood_type=wood_type)
)

# ── CODES ─────────────────────────────────────────────────────────────
generator_code    = orm.load_code(cfg['codes']['generator'])
filter_code       = orm.load_code(cfg['codes']['filter'])
permeability_code = orm.load_code(cfg['codes']['permeability'])

pl = cfg['pipeline']

# ── PHASE 1: STRUCTURE GENERATION ─────────────────────────────────────
cell_radii   = orm.List(list=pl['cell_radii'])
wall_thicks  = orm.List(list=pl['wall_thicks'])
resolutions  = orm.List(list=pl['resolutions'])
random_seeds = orm.List(list=pl['random_seeds'])

# ── PHASE 2: STRUCTURE FILTERING ──────────────────────────────────────
sigmas = orm.List(list=pl['sigmas'])

filter_defaults  = orm.Dict(dict=pl['filter_defaults'])
filter_overrides = orm.Dict(dict=pl['filter_overrides'])

# ── PHASE 3: PERMEABILITY ─────────────────────────────────────────────
d_solids = orm.List(list=pl['d_solids'])
guozhaos = orm.List(list=pl['guozhaos'])

permeability_defaults  = orm.Dict(dict=pl['permeability_defaults'])
permeability_overrides = orm.Dict(dict=pl['permeability_overrides'])

# ── PHASE 3 RESOURCES ─────────────────────────────────────────────────
metadata_options = orm.Dict(dict=resolve_metadata_options(pl['metadata_options']))

# ── EXPECTED SWEEP SIZE ───────────────────────────────────────────────
n_structures = (
    len(cell_radii.get_list())
    * len(wall_thicks.get_list())
    * len(resolutions.get_list())
    * len(random_seeds.get_list())
)
n_filter = n_structures * len(sigmas.get_list())
n_perm = n_filter * len(d_solids.get_list()) * len(guozhaos.get_list())

print(f"\nWood type           : {wood_type}")
print(f"Generation jobs     : {n_structures}")
print(f"Filter jobs         : {n_filter}")
print(f"Permeability jobs   : {n_perm}  (each runs 3 ShellJobs: X, Y, Z)")
print()

wc = submit(
    WoodPermeabilityWorkChain,
    generator_code=generator_code,
    filter_code=filter_code,
    permeability_code=permeability_code,
    wood_type=orm.Str(wood_type),
    base_params=base_params,
    cell_radii=cell_radii,
    wall_thicks=wall_thicks,
    resolutions=resolutions,
    random_seeds=random_seeds,
    sigmas=sigmas,
    filter_defaults=filter_defaults,
    filter_overrides=filter_overrides,
    d_solids=d_solids,
    guozhaos=guozhaos,
    permeability_defaults=permeability_defaults,
    permeability_overrides=permeability_overrides,
    metadata_options=metadata_options,
)

print(f"Submitted WoodPermeabilityWorkChain -> PK {wc.pk}")
print("\nMonitor:")
print(f"  verdi process report {wc.pk}")
print("  verdi process list -a | grep WoodPermeability")
