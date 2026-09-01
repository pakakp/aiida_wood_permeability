"""
Single wood structure generation workflow.
Wraps the structure generator ShellJob for use as a sub-workchain.
"""
import json
import tempfile

from aiida import orm
from aiida.engine import WorkChain, ToContext, calcfunction
from aiida_shell import launch_shell_job


@calcfunction
def parse_dir_name(output_dir_txt):
    """
    Read the directory name written by the structure generator and return
    it as a stored Str node.  A calcfunction is required because AiiDA
    forbids WorkChains from returning bare (unstored) Data nodes.
    """
    with output_dir_txt.open() as f:
        return orm.Str(f.read().strip())


class WoodStructureGeneratorWorkChain(WorkChain):
    """
    Generate a single wood microstructure from a base parameter file.

    Runs the structure generator script and outputs only the directory
    name written to output_dir.txt.  The SaveWood.tar.gz is consumed
    directly by FilterPenetrationWorkChain via the child ShellJob node
    and does not need to be a returned output of this workchain.
    """

    @classmethod
    def define(cls, spec):
        super().define(spec)

        # ── INPUTS ──────────────────────────────────────────────────────
        spec.input('generator_code', valid_type=orm.InstalledCode,
                   help='wood-microstructure generator code (local)')
        spec.input('wood_type', valid_type=orm.Str,
                   help='Wood species label, e.g. "birch" or "spruce"')
        spec.input('base_params', valid_type=orm.SinglefileData,
                   help='Base JSON parameter file for the structure generator')
        spec.input('cellR', valid_type=orm.Int,
                   help='Cell radius')
        spec.input('resolution', valid_type=orm.List,
                   help='Resolution as [x, y, z]')
        spec.input('random_seed', valid_type=orm.Int,
                   help='Random seed for structure generation')

        # ── OUTLINE ─────────────────────────────────────────────────────
        spec.outline(
            cls.setup,
            cls.generate,
            cls.check_result,
        )

        # ── OUTPUTS ─────────────────────────────────────────────────────
        # structure_tar is intentionally NOT exposed as a workchain output.
        # It is accessed directly from the child ShellJob by the parent
        # WoodPenetrationWorkChain via node.called[0].outputs['SaveWood_tar_gz'].
        spec.output('dir_name', valid_type=orm.Str,
                    help='Name of the directory inside the tar archive')

        # ── EXIT CODES ───────────────────────────────────────────────────
        spec.exit_code(401, 'ERROR_GENERATION_FAILED',
                       message='Structure generation job failed')

    def setup(self):
        """Log what we are about to generate."""
        self.report(
            f"Generating {self.inputs.wood_type.value} structure: "
            f"cellR={self.inputs.cellR.value}, "
            f"cellWallThick={self.inputs.cell_wall_thickness.value}, "
            f"resolution={self.inputs.resolution.get_list()}, "
            f"seed={self.inputs.random_seed.value}"
        )

    def generate(self):
        """Build the parameter dict and launch the generator ShellJob."""
        with self.inputs.base_params.open() as f:
            base_data = json.load(f)
        base_params = base_data[0] if isinstance(base_data, list) else base_data

        structure_params = base_params.copy()
        structure_params['cellR'] = self.inputs.cellR.value
        structure_params['cellWallThick'] = self.inputs.cell_wall_thickness.value
        structure_params['sizeVolume']  = self.inputs.resolution.get_list()
        structure_params['random_seed'] = self.inputs.random_seed.value

        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', delete=False
        ) as tmp:
            json.dump([structure_params], tmp)
            json_path = tmp.name

        params_node = orm.SinglefileData(file=json_path)

        _, node = launch_shell_job(
            self.inputs.generator_code,
            arguments=[
                '/home/akpantti/bin/structure_generator.py',
                '{params_json}',
                self.inputs.wood_type.value,
            ],
            nodes={'params_json': params_node},
            filenames={'params_json': 'params.json'},
            outputs=['output_dir.txt', 'SaveWood.tar.gz'],
            metadata={
                'call_link_label': 'generate',
                'options': {
                    'resources': {
                        'num_machines': 1,
                        'num_mpiprocs_per_machine': 1,
                    },
                    'max_wallclock_seconds': 12000,
                    'queue_name': 'gen04_epyc',
                    'custom_scheduler_commands': '#SBATCH --mem=16G',
                    'withmpi': False,
                },
            },
            submit=True,
        )

        node.base.extras.set('wood_type', self.inputs.wood_type.value)
        node.base.extras.set('cellR', self.inputs.cellR.value)
        node.base.extras.set('cellWallThickness', self.inputs.cell_wall_thickness.value)
        node.base.extras.set('resolution', self.inputs.resolution.get_list())
        node.base.extras.set('random_seed', self.inputs.random_seed.value)

        return ToContext(generation=node)

    def check_result(self):
        """Expose outputs or report failure."""
        # Accept 410: ShellJob stderr warnings but outputs were produced successfully
        if self.ctx.generation.exit_status not in [0, 410]:
            self.report(f"ERROR: Generation failed (PK {self.ctx.generation.pk}, "
                        f"exit {self.ctx.generation.exit_status})")
            return self.exit_codes.ERROR_GENERATION_FAILED

        dir_name = parse_dir_name(self.ctx.generation.outputs['output_dir_txt'])
        self.out('dir_name', dir_name)

        tar_pk = self.ctx.generation.outputs['SaveWood_tar_gz'].pk
        self.report(f"✓ Structure generated: {dir_name.value} (tar PK {tar_pk})")
