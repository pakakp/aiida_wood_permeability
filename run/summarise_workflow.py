#!/usr/bin/env python3
"""
Print a summary table of results from a completed WoodPermeabilityWorkChain.

Usage:
    python summarise_workflow.py <workchain_pk>
"""
import sys, json
from aiida import load_profile, orm

load_profile()

if len(sys.argv) != 2:
    print("Usage: python summarise_workflow.py <wc_pk>")
    sys.exit(1)

pk = int(sys.argv[1])
wc = orm.load_node(pk)

print("=" * 70)
print(f"WoodPermeabilityWorkChain PK {pk}")
print(f"State    : {wc.process_state.value}")
print(f"Exit code: {wc.exit_status}")
print("=" * 70)

if wc.exit_status == 430:
    print("\nAll permeability jobs failed — no results to show.")
    print(f"Check: verdi process report {pk}")
    sys.exit(1)

if not wc.is_finished_ok:
    print(f"\nWorkchain finished with errors (exit code {wc.exit_status}).")
    print("Attempting to read partial results...")

try:
    results = wc.outputs.results.get_dict()
except Exception:
    print("No results output found.")
    print(f"Check: verdi process report {pk}")
    sys.exit(1)

if not results:
    print("\nNo results found in output.")
    sys.exit(0)

all_wcs  = wc.called_descendants
gen_wcs  = [n for n in all_wcs if 'WoodStructureGenerator'      in n.process_label]
flt_wcs  = [n for n in all_wcs if 'StructureFilter'             in n.process_label]
perm_wcs = [n for n in all_wcs if 'SingleStructurePermeability' in n.process_label]

print(f"\nGeneration workchains   : {len(gen_wcs)}")
print(f"Filter workchains       : {len(flt_wcs)}")
print(f"Permeability workchains : {len(perm_wcs)}  (each ran 3 ShellJobs)")
print(f"Successful results      : {len(results)}")

print(f"\n{'cellR':>6} {'seed':>6} {'porosity':>9} {'actual_por':>10} "
      f"{'dSolid':>8} {'k_x':>12} {'k_y':>12} {'k_z':>12} {'k_avg':>12}")
print("-" * 88)

rows = sorted(
    results.values(),
    key=lambda x: (x['cellR'], x['random_seed'], x['porosity'], x['d_solid'])
)

for r in rows:
    t = r['permeability_tensor']
    k_avg = (t['k_x'] + t['k_y'] + t['k_z']) / 3
    print(f"  {r['cellR']:>4} {r['random_seed']:>6} "
          f"{r['porosity']:>9.3f} {r['actual_porosity']:>10.4f} "
          f"{r['d_solid']:>8.3f} "
          f"{t['k_x']:>12.3e} {t['k_y']:>12.3e} {t['k_z']:>12.3e} {k_avg:>12.3e}")

print("-" * 88)
print(f"Total: {len(rows)} runs")

output_file = f'results_wc{pk}.json'
with open(output_file, 'w') as f:
    json.dump(list(results.values()), f, indent=2)
print(f"\nFull results saved to: {output_file}")
