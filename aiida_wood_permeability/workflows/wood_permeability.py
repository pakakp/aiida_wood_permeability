"""
Top-level workflow: generate structures, filter them, then sweep permeability
parameters over the cached VTI files.

Phase 1 – generate structures    (WoodStructureGeneratorWorkChain per cellR×res×seed)
Phase 2 – filter structures      (StructureFilterWorkChain per structure×porosity)
Phase 3 – permeability sweep     (OLBPermeabilityWorkChain per VTI×dSolid)
"""

from aiida import orm
from aiida.engine import ToContext, WorkChain
from aiida.plugins import CalculationFactory

from .base import BaseSehllJobChain
from .olb_permeability import OLBPermeabilityWorkChain
from .structure_filter import StructureFilterWorkChain
from .wood_structure_generator import WoodStructureGeneratorWorkChain

ShellJob = CalculationFactory('core.shell')


class WoodPermeabilityWorkChain(BaseSehllJobChain):
    """Full workflow for wood permeability calculations.
    - Generate wood structure
    - Filter structure to VTI format
    - Sweep permeability parameters over the filtered VTI file
    """
    shellcode_name = 'permeability_code'

    @classmethod
    def define(cls, spec):
        super().define(spec)

        # ── CODES ────────────────────────────────────────────────────────
        spec.input('wood_ms_code', valid_type=orm.InstalledCode, help='wood-microstructure generator')
        spec.input('permeability_code', valid_type=orm.InstalledCode, help='OpenLB permeability solver')

        # ── PHASE 1: GENERATION ──────────────────────────────────────────
        spec.expose_inputs(
            WoodStructureGeneratorWorkChain,
            namespace='generator',
            exclude=('wood_ms_code', 'clean_workdir', 'shelljob'),
        )

        # ── PHASE 2: FILTERING ───────────────────────────────────────────
        spec.expose_inputs(
            StructureFilterWorkChain,
            namespace='filter',
            exclude=('wood_ms_code', 'clean_workdir', 'wood_structure', 'shelljob'),
        )

        # ── PHASE 3: PERMEABILITY ────────────────────────────────────────
        spec.expose_inputs(
            OLBPermeabilityWorkChain,
            namespace='permeability',
            exclude=('code', 'vti_file', 'clean_workdir', 'shelljob')
        )

        # ── OUTLINE ──────────────────────────────────────────────────────
        spec.outline(
            cls.setup,

            cls.prepare_generation_input,
            cls.submit_generation,
            cls.inspect_generation,

            cls.prepare_filter_input,
            cls.submit_filter,
            cls.inspect_filter,

            cls.prepare_permeability_input,
            cls.submit_permeability,
            cls.inspect_permeability,

            # cls.results,
        )

        # ── OUTPUTS ──────────────────────────────────────────────────────
        spec.expose_outputs(WoodStructureGeneratorWorkChain, namespace='generator')
        spec.expose_outputs(StructureFilterWorkChain, namespace='filter')
        spec.expose_outputs(OLBPermeabilityWorkChain, namespace='permeability')

        # ── EXIT CODES ───────────────────────────────────────────────────
        spec.exit_code(410, 'ERROR_GENERATOR_FAILED', message='Structure generation job failed')
        spec.exit_code(420, 'ERROR_FILTERING_FAILED', message='Structure filtering job failed')
        spec.exit_code(430, 'ERROR_PERMEABILITY_FAILED', message='Permeability calculation failed')

    # ── PHASE 1: GENERATION ──────────────────────────────────────────────────

    def prepare_generation_input(self):
        """Prepare the input parameters for the structure generator, applying any overrides from the WC inputs."""
        self.ctx.base_params = self.inputs.generator.input_params.get_dict()

        inputs = self.exposed_inputs(WoodStructureGeneratorWorkChain, namespace='generator')
        inputs['wood_ms_code'] = self.inputs.wood_ms_code
        inputs['clean_workdir'] = self.inputs.clean_workdir

        inputs.setdefault('shelljob', {})['metadata'] = self.ctx.serial_metadata

        self.ctx.generator_inputs = inputs

    def submit_generation(self):
        """Submit the structure generation workchains for all combinations of parameters."""
        self.report('Submitting structure generation workchains...')

        running = self.submit(WoodStructureGeneratorWorkChain, **self.ctx.generator_inputs)

        self.report(f"Submitted structure generation workchain (PK {running.pk})")

        return ToContext(generation_workchain=running)

    def inspect_generation(self):
        """Inspect the results of the structure generation workchains."""
        workchain = self.ctx.generation_workchain
        if not workchain.is_finished_ok:
            self.report(f"Structure generation failed (PK {workchain.pk})")
            return self.exit_codes.ERROR_GENERATOR_FAILED

        self.ctx.generated_structure = workchain.outputs.volume['final']

        self.out_many(
            self.exposed_outputs(workchain, WoodStructureGeneratorWorkChain, namespace='generator')
        )

    # ── PHASE 2: FILTERING ───────────────────────────────────────────────────
    def prepare_filter_input(self):
        """Prepare the input parameters for the structure filter, applying any overrides from the WC inputs."""
        inputs = self.exposed_inputs(StructureFilterWorkChain, namespace='filter')
        inputs['wood_ms_code'] = self.inputs.wood_ms_code
        inputs['clean_workdir'] = self.inputs.clean_workdir
        inputs['wood_structure'] = self.ctx.generated_structure

        # inputs['shelljob'].metadata = self.ctx.serial_metadata
        inputs.setdefault('shelljob', {})['metadata'] = self.ctx.serial_metadata

        self.ctx.filter_inputs = inputs

    def submit_filter(self):
        """Submit the structure filtering workchain."""
        self.report('Submitting structure filtering workchain...')

        running = self.submit(StructureFilterWorkChain, **self.ctx.filter_inputs)

        self.report(f"Submitted structure filtering workchain (PK {running.pk})")

        return ToContext(filter_workchain=running)

    def inspect_filter(self):
        """Inspect the results of the structure filtering workchain."""
        workchain = self.ctx.filter_workchain
        if not workchain.is_finished_ok:
            self.report(f"Structure filtering failed (PK {workchain.pk})")
            return self.exit_codes.ERROR_FILTERING_FAILED

        self.ctx.filtered_structure = workchain.outputs.structure

        self.out_many(
            self.exposed_outputs(workchain, StructureFilterWorkChain, namespace='filter')
        )

    # ── PHASE 3: PERMEABILITY ─────────────────────────────────────────────────
    def prepare_permeability_input(self):
        """Prepare the input parameters for the permeability calculations, applying any overrides from the WC inputs."""
        inputs = self.exposed_inputs(OLBPermeabilityWorkChain, namespace='permeability')
        inputs['code'] = self.inputs.permeability_code
        inputs['vti_file'] = self.ctx.filtered_structure
        inputs['clean_workdir'] = self.inputs.clean_workdir

        # inputs['shelljob'].metadata = self.ctx.parall_metadata
        inputs.setdefault('shelljob', {})['metadata'] = self.ctx.parall_metadata

        self.ctx.permeability_inputs = inputs

    def submit_permeability(self):
        """Submit the permeability workchain."""
        self.report('Submitting permeability workchain...')

        running = self.submit(OLBPermeabilityWorkChain, **self.ctx.permeability_inputs)

        self.report(f"Submitted permeability workchain (PK {running.pk})")

        return ToContext(permeability_workchain=running)

    def inspect_permeability(self):
        """Inspect the results of the permeability workchain."""
        workchain = self.ctx.permeability_workchain
        if not workchain.is_finished_ok:
            self.report(f"Permeability calculation failed (PK {workchain.pk})")
            return self.exit_codes.ERROR_PERMEABILITY_FAILED

        self.out_many(
            self.exposed_outputs(workchain, OLBPermeabilityWorkChain, namespace='permeability')
        )

    # def results(self):
    #     """Collect the results from all phases and output them."""
    #     results = {
    #         'generated_structure': self.ctx.generated_structure,
    #         'filtered_structure': self.ctx.filtered_structure,
    #         'permeability_results': self.exposed_outputs(
    #             self.ctx.permeability_workchain, OLBPermeabilityWorkChain, namespace='permeability'
    #         ),
    #     }

    #     self.out('results', orm.Dict(dict=results))
