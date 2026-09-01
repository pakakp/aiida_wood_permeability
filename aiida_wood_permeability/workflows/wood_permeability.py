"""
Top-level workflow: generate structures, filter them, then sweep permeability
parameters over the cached VTI files.

Phase 1 – generate structures    (WoodStructureGeneratorWorkChain per cellR×res×seed)
Phase 2 – filter structures      (StructureFilterWorkChain per structure×porosity)
Phase 3 – permeability sweep     (SingleStructurePermeabilityWorkChain per VTI×dSolid)
"""
import itertools
import re

from aiida import orm
from aiida.engine import WorkChain, ToContext

from aiida_wood_permeability.workflows.wood_structure_generator import WoodStructureGeneratorWorkChain
from aiida_wood_permeability.workflows.structure_filter import StructureFilterWorkChain
from .single_structure_permeability import SingleStructurePermeabilityWorkChain


# ── DEFAULT FILTER PARAMETERS ────────────────────────────────────────────────
FILTER_DEFAULTS = {
    'threshold': 127,
    'solid_dark': False,
    'down': 1,
    'smooth_low_iters': 0,
    'smooth_sigma': 1.5,
    'thicken': 0,
    'final_smooth_iters': 0,
    'final_smooth_sigma': 1.3,
    'upsample_intermediate': 1,
    'upsample_final': 1,
    'pad': 0,
    'pad_xy_only': False,
    'porosity': None,
    'sdf_sigma': None,
    'adjust_porosity_post': False,
    'allow_boundary_removal': True,
    'majority_filter': 1,
    'min_gradient': 0.2,
    'verbose': False,
}

# ── DEFAULT PERMEABILITY PARAMETERS ──────────────────────────────────────────
PERMEABILITY_DEFAULTS = {
    'arrayname':          'ImageFile',
    'scaling_factor':     5e-7,
    'uout':               1.0,
    'tau':                1.0,
    'pressure_drop':      10.0,
    'kinematicViscosity': 1e-4,
    'fluidDensity':       1.0,
    'tolerance':          1e-6,
    'flowDirection':      1,  # overridden per direction inside SingleStructurePermeabilityWorkChain
    'uniformguozhao':     1,
}


def sanitise_key(s):
    """Replace all characters that are not alphanumeric or underscore with '_'."""
    return re.sub(r'[^a-zA-Z0-9_]', '_', s)


class WoodPermeabilityWorkChain(WorkChain):
    """
    Fully automated wood structure generation, filtering, and permeability sweep.

    Outline
    -------
    1. generate_structures  – one WoodStructureGeneratorWorkChain per (cellR, res, seed)
    2. collect_structures   – gather successful tars; skip failures
    3. filter_structures    – one StructureFilterWorkChain per structure × porosity
    4. collect_filtered     – gather successful VTIs; skip failures
    5. submit_permeability  – one SingleStructurePermeabilityWorkChain per VTI × dSolid
    6. collect_results      – gather successful results; skip failures
    """

    @classmethod
    def define(cls, spec):
        super().define(spec)

        # ── CODES ────────────────────────────────────────────────────────
        spec.input('generator_code', valid_type=orm.InstalledCode,
                   help='wood-microstructure generator (local)')
        spec.input('filter_code', valid_type=orm.InstalledCode,
                   help='filter.py code (local)')
        spec.input('permeability_code', valid_type=orm.InstalledCode,
                   help='OpenLB permeability solver (HPC)')

        # ── PHASE 1: GENERATION ──────────────────────────────────────────
        spec.input('wood_type', valid_type=orm.Str,
                   help='Wood species label, e.g. "birch" or "spruce"')
        spec.input('base_params', valid_type=orm.SinglefileData,
                   help='Base JSON parameter file for the structure generator')
        spec.input('cell_radii', valid_type=orm.List,
                   help='Cell radii to sweep, e.g. [12, 14]')
        spec.input('wall_thicks', valid_type=orm.List,
                   help='Cell-wall thicknesses to sweep')
        spec.input('resolutions', valid_type=orm.List,
                   help='Resolutions to sweep; each entry int or [x,y,z]')
        spec.input('random_seeds', valid_type=orm.List,
                   help='Random seeds to sweep')

        # ── PHASE 2: FILTERING ───────────────────────────────────────────
        spec.input('sigmas', valid_type=orm.List,
                   help='SDF sigma values to sweep')
        spec.input('filter_overrides', valid_type=orm.Dict, required=False,
                   help='Optional overrides merged with filter defaults')

        # ── PHASE 3: PERMEABILITY ────────────────────────────────────────
        spec.input('d_solids', valid_type=orm.List,
                   help='dSolid values to sweep')
        spec.input('guozhaos', valid_type=orm.List,
                   help='uniformguozhao values to sweep')
        spec.input('permeability_overrides', valid_type=orm.Dict, required=False,
                   help='Optional overrides merged with permeability defaults')
        spec.input('metadata_options', valid_type=orm.Dict, required=False,
                   help='HPC resource options for permeability jobs')

        # ── OUTLINE ──────────────────────────────────────────────────────
        spec.outline(
            cls.generate_structures,
            cls.collect_structures,
            cls.filter_structures,
            cls.collect_filtered,
            cls.submit_permeability,
            cls.collect_results,
        )

        # ── OUTPUTS ──────────────────────────────────────────────────────
        spec.output('results', valid_type=orm.Dict,
                    help='All successful results keyed by run label')
        spec.output_namespace('vti_files', valid_type=orm.SinglefileData,
                              dynamic=True,
                              help='VTI files from successful filter runs')

        # ── EXIT CODES ───────────────────────────────────────────────────
        spec.exit_code(410, 'ERROR_ALL_GENERATION_FAILED',
                       message='Every structure generation job failed')
        spec.exit_code(420, 'ERROR_ALL_FILTERING_FAILED',
                       message='Every structure filtering job failed')
        spec.exit_code(430, 'ERROR_ALL_PERMEABILITY_FAILED',
                       message='Every permeability calculation failed')

    # ── HELPERS ──────────────────────────────────────────────────────────────

    def _build_filter_params(self, sigma):
        params = dict(FILTER_DEFAULTS)
        #params['upsample-final'] = self.inputs.upsample_final.value
        #params['porosity']       = porosity
        if 'filter_overrides' in self.inputs:
            params.update(self.inputs.filter_overrides.get_dict())
        params['sdf_sigma'] = sigma
        return orm.Dict(dict=params)

    def _build_permeability_params(self, d_solid, guozhao, resolution):
        params = dict(PERMEABILITY_DEFAULTS)
        if 'permeability_overrides' in self.inputs:
            params.update(self.inputs.permeability_overrides.get_dict())
        params['dSolid'] = d_solid
        params['resolution'] = resolution
        params['uniformguozhao'] = guozhao
        return orm.Dict(dict=params)

    # ── PHASE 1: GENERATION ──────────────────────────────────────────────────

    def generate_structures(self):
        cell_radii  = self.inputs.cell_radii.get_list()
        wall_thicks = self.inputs.wall_thicks.get_list()
        resolutions = self.inputs.resolutions.get_list()
        seeds       = self.inputs.random_seeds.get_list()

        combinations = list(itertools.product(cell_radii, wall_thicks, resolutions, seeds))
        self.report(
            f"Phase 1: submitting {len(combinations)} generation workchains "
            f"for wood_type={self.inputs.wood_type.value}"
        )

        self.ctx.generation_keys = []

        for cellR, wall_thick, res, seed in combinations:
            resolution_list = [res, res, res] if isinstance(res, int) else list(res)
            key = sanitise_key(
                f"gen_cR{cellR}_wt{wall_thick}"
                f"_r{'x'.join(str(r) for r in resolution_list)}"
                f"_s{seed}"
            )

            future = self.submit(
                WoodStructureGeneratorWorkChain,
                generator_code=self.inputs.generator_code,
                wood_type=self.inputs.wood_type,
                base_params=set_wall_thickness(
                    self.inputs.base_params, orm.Int(wall_thick)
                ),
                cellR=orm.Int(cellR),
                resolution=orm.List(list=resolution_list),
                random_seed=orm.Int(seed),
            )

            self.ctx.generation_keys.append({
                'key':         key,
                'cellR':       cellR,
                'cellWallThickness': wall_thick,
                'resolution':  resolution_list,
                'random_seed': seed,
            })
            self.ctx[key] = future

        return ToContext(**{m['key']: self.ctx[m['key']] for m in self.ctx.generation_keys})

    def collect_structures(self):
        self.ctx.structures = []
        n_ok = n_fail = 0

        for meta in self.ctx.generation_keys:
            node = self.ctx[meta['key']]
            if not node.is_finished_ok:
                self.report(
                    f"Generation failed: cellR={meta['cellR']}, "
                    f"res={meta['resolution']}, seed={meta['random_seed']} "
                    f"(PK {node.pk}) — skipping"
                )
                n_fail += 1
                continue

            self.ctx.structures.append({
                'workchain_pk':   node.pk,
                'workchain_uuid': str(node.uuid),
                'generator_code': self.inputs.generator_code.full_label,
                'tar_node':       node.base.links.get_outgoing(
                                      link_label_filter='generate'
                                  ).one().node.outputs['SaveWood_tar_gz'],
                'dir_name':       node.outputs.dir_name.value,
                'wood_type':      self.inputs.wood_type.value,
                'cellR':          meta['cellR'],
                'cellWallThickness': meta['cellWallThickness'],
                'resolution':     meta['resolution'],
                'random_seed':    meta['random_seed'],
            })
            n_ok += 1

        self.report(f"Phase 1 complete: {n_ok} structures collected, {n_fail} failed")
        if n_ok == 0:
            return self.exit_codes.ERROR_ALL_GENERATION_FAILED

    # ── PHASE 2: FILTERING ───────────────────────────────────────────────────

    def filter_structures(self):
        sigmas = self.inputs.sigmas.get_list()

        n_total = len(self.ctx.structures) * len(sigmas)
        self.report(
            f"Phase 2: submitting {n_total} filter workchains "
            f"({len(self.ctx.structures)} structures × {len(sigmas)} sigmas)"
        )

        self.ctx.filter_keys = []

        for struct in self.ctx.structures:
            for sigma in sigmas:
                filter_params = self._build_filter_params(sigma)
                key = sanitise_key(
                    f"flt_cR{struct['cellR']}"
                    f"_r{'x'.join(str(r) for r in struct['resolution'])}"
                    f"_s{struct['random_seed']}"
                    f"_wt{struct['cellWallThickness']}_sig{sigma}"
                )

                future = self.submit(
                    StructureFilterWorkChain,
                    filter_code=self.inputs.filter_code,
                    structure_tar=struct['tar_node'],
                    structure_dir_name=orm.Str(struct['dir_name']),
                    filter_params=filter_params,
                )

                self.ctx.filter_keys.append({
                    'key':                key,
                    'filter_params_pk':   filter_params.pk,
                    'filter_code':        self.inputs.filter_code.full_label,
                    'gen_workchain_pk':   struct['workchain_pk'],
                    'gen_workchain_uuid': struct['workchain_uuid'],
                    'wood_type':          struct['wood_type'],
                    'cellR':              struct['cellR'],
                    'cellWallThickness':  struct['cellWallThickness'],
                    'resolution':         struct['resolution'],
                    'random_seed':        struct['random_seed'],
                    'dir_name':           struct['dir_name'],
                    'sdf_sigma':          sigma,
                    'filter_params':      filter_params.get_dict(),
                })
                self.ctx[key] = future

        return ToContext(**{m['key']: self.ctx[m['key']] for m in self.ctx.filter_keys})

    def collect_filtered(self):
        self.ctx.filtered = []
        n_ok = n_fail = 0

        for meta in self.ctx.filter_keys:
            node = self.ctx[meta['key']]
            if not node.is_finished_ok:
                self.report(
                    f"Filter failed: cellR={meta['cellR']}, "
                    f"seed={meta['random_seed']}, sigma={meta['sdf_sigma']} "
                    f"(PK {node.pk}) — skipping"
                )
                n_fail += 1
                continue

            self.ctx.filtered.append({
                **meta,
                'filter_workchain_pk':   node.pk,
                'filter_workchain_uuid': str(node.uuid),
                'vti_node':              node.outputs.vti_file,
                'actual_porosity':       node.outputs.actual_porosity.value,
            })
            n_ok += 1

        self.report(f"Phase 2 complete: {n_ok} VTIs collected, {n_fail} failed")
        if n_ok == 0:
            return self.exit_codes.ERROR_ALL_FILTERING_FAILED

    # ── PHASE 3: PERMEABILITY ─────────────────────────────────────────────────

    def submit_permeability(self):
        d_solids = self.inputs.d_solids.get_list()
        guozhaos = self.inputs.guozhaos.get_list()

        if 'metadata_options' in self.inputs:
            metadata_options = self.inputs.metadata_options
        else:
            metadata_options = orm.Dict(dict={
                'options': {
                    'resources': {
                        'num_machines': 1,
                        'num_mpiprocs_per_machine': 32,
                    },
                    'max_wallclock_seconds': 272800,
                    'withmpi': True,
                }
            })

        n_total = len(self.ctx.filtered) * len(d_solids) * len(guozhaos)
        self.report(
            f"Phase 3: submitting {n_total} permeability workchains "
            f"({len(self.ctx.filtered)} VTIs × {len(d_solids)} dSolid × {len(guozhaos)} guozhao)"
        )

        self.ctx.permeability_keys = []

        for flt in self.ctx.filtered:
            resolution_for_solver = min(flt['resolution']) / 1

            for d_solid, guozhao in itertools.product(d_solids, guozhaos):
                permeability_params = self._build_permeability_params(
                    d_solid, guozhao, resolution_for_solver
                )

                key = sanitise_key(
                    f"perm_cR{flt['cellR']}"
                    f"_r{'x'.join(str(r) for r in flt['resolution'])}"
                    f"_s{flt['random_seed']}"
                    f"_wt{flt['cellWallThickness']}_sig{flt['sdf_sigma']}"
                    f"_ds{d_solid}_gz{guozhao}"
                )

                future = self.submit(
                    SingleStructurePermeabilityWorkChain,
                    code=self.inputs.permeability_code,
                    vti_file=flt['vti_node'],
                    parameters=permeability_params,
                    metadata_options=metadata_options,
                )

                self.ctx.permeability_keys.append({
                    'key':                      key,
                    'workchain_uuid':            str(future.uuid),
                    'permeability_params_pk':    permeability_params.pk,
                    'permeability_code':         self.inputs.permeability_code.full_label,
                    'filter_workchain_pk':       flt['filter_workchain_pk'],
                    'filter_workchain_uuid':     flt['filter_workchain_uuid'],
                    'filter_params_pk':          flt['filter_params_pk'],
                    'filter_params':             flt['filter_params'],
                    'gen_workchain_pk':          flt['gen_workchain_pk'],
                    'gen_workchain_uuid':        flt['gen_workchain_uuid'],
                    'wood_type':                 flt['wood_type'],
                    'cellR':                     flt['cellR'],
                    'resolution':                flt['resolution'],
                    'random_seed':               flt['random_seed'],
                    'cellWallThickness':         flt['cellWallThickness'],
                    'sdf_sigma':                  flt['sdf_sigma'],
                    'actual_porosity':            flt['actual_porosity'],
                    'resolution_solver':         resolution_for_solver,
                    'd_solid':                   d_solid,
                    'uniformguozhao':            guozhao,
                    'permeability_params':       permeability_params.get_dict(),
                })
                self.ctx[key] = future

        return ToContext(**{m['key']: self.ctx[m['key']] for m in self.ctx.permeability_keys})

    def collect_results(self):
        result_nodes = {}
        vti_outs     = {}
        n_ok = n_fail = 0

        for meta in self.ctx.permeability_keys:
            node = self.ctx[meta['key']]

            if not node.is_finished_ok:
                self.report(
                    f" Permeability failed: cellR={meta['cellR']}, "
                    f"seed={meta['random_seed']}, sigma={meta['sdf_sigma']}, "
                    f"dSolid={meta['d_solid']}, guozhao={meta['uniformguozhao']} (PK {node.pk}) — skipping"
                )
                n_fail += 1
                continue

            tensor = node.outputs.permeability_tensor.get_dict()
            entry = dict(meta)
            entry['workchain_pk']       = node.pk
            entry['permeability_tensor'] = tensor
            entry['k_avg'] = (tensor['k_x'] + tensor['k_y'] + tensor['k_z']) / 3
            result_nodes[meta['key']] = entry

            flt_wc = next(
                f for f in self.ctx.filtered
                if f['filter_workchain_pk'] == meta['filter_workchain_pk']
            )
            vti_outs[meta['key']] = flt_wc['vti_node']
            n_ok += 1

        self.report(f"Phase 3 complete: {n_ok} results collected, {n_fail} failed")

        if n_ok == 0:
            return self.exit_codes.ERROR_ALL_PERMEABILITY_FAILED

        self.out('results', orm.Dict(dict=result_nodes).store())
        for label, vti in vti_outs.items():
            self.out(f'vti_files.{label}', vti)

        self.report("=" * 50)
        self.report("WoodPermeabilityWorkChain complete!")
        self.report(f"  {n_ok} successful runs, {n_fail} skipped")
        self.report("=" * 50)
