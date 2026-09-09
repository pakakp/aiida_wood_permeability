"""
Single wood structure generation workflow.
Wraps the structure generator ShellJob for use as a sub-workchain.
"""
import copy
import os

from aiida import orm
from aiida.engine import ToContext
from aiida.plugins import CalculationFactory
from aiida_shell import launch_shell_job

from . import utils as utils
from .base import BaseSehllJobChain

ShellJob = CalculationFactory('core.shell')


class WoodStructureGeneratorWorkChain(BaseSehllJobChain):
    """
    Generate a single wood microstructure from a base parameter file.

    Runs the structure generator script and outputs only the directory
    name written to output_dir.txt.
    The SaveWood.tar.gz is consumed
    directly by FilterPenetrationWorkChain via the child ShellJob node
    and does not need to be a returned output of this workchain.
    """
    shellcode_name = 'wood_ms_code'

    @classmethod
    def define(cls, spec):
        super().define(spec)

        # ── INPUTS ──────────────────────────────────────────────────────
        spec.input(
            'wood_ms_code', valid_type = orm.InstalledCode,
            help = 'wood-microstructure generator code'
        )
        spec.input(
            'wood_type', valid_type = orm.Str,
            help = 'Wood species label, e.g. "birch" or "spruce"'
        )
        spec.input(
            'input_params', valid_type = orm.Dict,
            help='Parameter dict for the structure generator'
        )

        spec.input('cellR', valid_type=orm.Int, required=False, help='Cell radius')
        spec.input('cell_wall_thickness', valid_type=orm.Float, required=False, help='Cell wall thickness')
        spec.input('resolution', valid_type=orm.List, required=False, help='Resolution as [x, y, z]')
        spec.input('random_seed', valid_type=orm.Int, required=False, help='Random seed for structure generation')
        spec.input(
            'save_local_dist', valid_type=orm.Bool, required=False,
            help='Whether to save local distribution data'
        )
        spec.input(
            'save_global_dist', valid_type=orm.Bool, required=False,
            help='Whether to save global distribution data'
        )

        # ── OUTLINE ─────────────────────────────────────────────────────
        spec.outline(
            cls.setup,

            cls.prepare_input,
            cls.submit_generation,
            cls.inspect_generation,
        )

        # ── OUTPUTS ─────────────────────────────────────────────────────
        spec.output(
            'parsed_params', valid_type=orm.Dict,
            help='Parsed parameters used for the structure generation'
        )
        spec.output_namespace(
            'volume',
            valid_type=orm.SinglefileData,
            dynamic=True,
            help='Final generated volume as a single file'
        )
        spec.output(
            'distortion', valid_type=orm.ArrayData, required=False,
            help='Local/Global deformation data (if saved)'
        )

        # ── EXIT CODES ───────────────────────────────────────────────────
        spec.exit_code(
            401, 'ERROR_GENERATION_FAILED',
            message='Structure generation job failed'
        )

    def prepare_input(self):
        """Prepare the input parameters for the structure generator, applying any overrides from the WC inputs."""
        params = self.inputs.input_params.get_dict()
        overrides = {}
        # if self.inputs.cellR:
        if 'cellR' in self.inputs and self.inputs.cellR:
            params.pop('cellR', None)
            params.pop('cell_r', None)
            overrides['cell_r'] = self.inputs.cellR
        # if self.inputs.cell_wall_thickness:
        if 'cell_wall_thickness' in self.inputs and self.inputs.cell_wall_thickness:
            params.pop('cellWallThick', None)
            params.pop('cell_wall_thickness', None)
            overrides['cell_wall_thickness'] = self.inputs.cell_wall_thickness
        # if self.inputs.resolution:
        if 'resolution' in self.inputs and self.inputs.resolution:
            params.pop('sizeVolume', None)
            params.pop('size_volume', None)
            overrides['size_volume'] = self.inputs.resolution
        # if self.inputs.random_seed:
        if 'random_seed' in self.inputs and self.inputs.random_seed:
            params.pop('random_seed', None)
            overrides['random_seed'] = self.inputs.random_seed

        if 'save_local_dist' in self.inputs and self.inputs.save_local_dist:
            params.pop('writeLocalDeformData', None)
            params.pop('save_local_dist', None)
            overrides['save_local_dist'] = self.inputs.save_local_dist
        if 'save_global_dist' in self.inputs and self.inputs.save_global_dist:
            params.pop('writeGlobalDeformData', None)
            params.pop('save_global_dist', None)
            overrides['save_global_dist'] = self.inputs.save_global_dist

        self.ctx.save_local_dist = bool(
            overrides.get('save_local_dist',
            params.get('save_local_dist', params.get('writeLocalDeformData', False)))
        )
        self.ctx.save_global_dist = bool(
            overrides.get('save_global_dist',
            params.get('save_global_dist', params.get('writeGlobalDeformData', False)))
        )

        params.pop('writeLocalDeformData', None)
        params.pop('writeGlobalDeformData', None)
        params['save_slices_as_2d'] = False
        params['save_volume_as_3d'] = True
        params['save_volume_format'] = 'vti'

        wood = self.inputs.wood_type.value.capitalize()

        self.ctx.json_input = utils.dict_to_json_file(params, **overrides)
        self.ctx.outdir_name = f'Save{wood}_0'
        self.ctx.parsed_params_fname = 'params.json'

    def submit_generation(self):
        """Run the structure generator script as a ShellJob and store the node in context."""
        self.report(f"Submitting structure generation job for {self.inputs.wood_type.value}...")

        metadata = copy.deepcopy(self.ctx.serial_metadata)
        metadata['call_link_label'] = 'generate'

        _, node = launch_shell_job(
            self.inputs.wood_ms_code,
            arguments='generate {wood_type} --config-file {params_json}',
            nodes={
                'params_json': self.ctx.json_input,
                'wood_type': self.inputs.wood_type,
            },
            outputs=[
                self.ctx.outdir_name,
                os.path.join(self.ctx.outdir_name, self.ctx.parsed_params_fname)
            ],
            metadata=metadata,
            submit=True,
        )

        self.report(f"Submitted structure generation job (PK {node.pk})")

        return ToContext(generate_calc=node)

    def inspect_generation(self):
        """Expose outputs or report failure."""

        calc = self.ctx.generate_calc
        if not calc.is_finished_ok:
            self.report(f"ERROR: Generation failed (PK {calc.pk}, exit {calc.exit_status})")
            return self.exit_codes.ERROR_GENERATION_FAILED

        res = calc.outputs

        folder: orm.FolderData = res[self.ctx.outdir_name]
        volumes = utils.extract_volumes_3d(folder)

        self.out('volume', volumes)
        pp_file = res[self.ctx.parsed_params_fname.replace('.', '_')]
        pp_dict = utils.json_file_to_dict(pp_file)
        self.out('parsed_params', pp_dict)

        if self.ctx.save_local_dist or self.ctx.save_global_dist:
            dist_node = utils.extract_distortion_data(folder)
            self.out('distortion', dist_node)
