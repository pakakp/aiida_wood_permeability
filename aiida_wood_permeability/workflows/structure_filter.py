"""
Structure filtering workflow for pre-generated wood structures.
Converts a tiff stack (SaveWood.tar.gz) to VTI format using filter.py.
"""
import copy
import os

from aiida import orm
from aiida.engine import ToContext, calcfunction
from aiida.plugins import CalculationFactory
from aiida_shell import launch_shell_job

from . import utils as utils
from .base import BaseSehllJobChain

ShellJob = CalculationFactory('core.shell')


@calcfunction
def extract_porosity_from_params(params_node: orm.Dict) -> orm.Float:
    """Extract the final porosity from the output parameters of the filtering process."""
    params = params_node.get_dict()
    actual_porosity = params.get('final_porosity', None)
    if actual_porosity is None:
        raise ValueError("The 'actual_porosity' key was not found in the output parameters.")
    return orm.Float(actual_porosity)


class StructureFilterWorkChain(BaseSehllJobChain):
    """Filter pre-generated structure to adapt for LB calculation."""
    shellcode_name = 'wood_ms_code'

    @classmethod
    def define(cls, spec):
        super().define(spec)

        # ── INPUTS ──────────────────────────────────────────────
        spec.input(
            'wood_ms_code', valid_type=orm.InstalledCode,
            help='filter.py code (local)'
        )
        spec.input(
            'wood_structure', valid_type=orm.SinglefileData,
            help='The wood structure as a 3D file to be fitlered'
        )
        spec.input(
            'input_params', valid_type=orm.Dict,
            help='Parameter dict for the structure generator'
        )

        # ── OUTLINE ──────────────────────────────────────────────
        spec.outline(
            cls.setup,

            cls.prepare_input,
            cls.submit_filter,
            cls.inspect_filter
        )

        # ── OUTPUTS ──────────────────────────────────────────────
        spec.output('structure', valid_type=orm.SinglefileData, help='Generated VTI file')
        spec.output('parsed_params', valid_type=orm.Dict, help='Parsed filter parameters used')
        spec.output('params', valid_type=orm.Dict, help='Output parameters from the filtering process')
        spec.output('actual_porosity', valid_type=orm.Float, help='Measured porosity after filtering')

        # ── EXIT CODES ────────────────────────────────────────────
        spec.exit_code(401, 'ERROR_FILTER_FAILED', message='filtering failed')

    def prepare_input(self):
        """Prepare the input parameters for the structure filter, applying any overrides from the WC inputs."""
        params = self.inputs.input_params.get_dict()
        self.ctx.input_file = utils.dict_to_json_file(params)

        self.ctx.outdir_name = 'fit_porosity_0'
        self.ctx.parsed_params_fname = 'params.json'
        self.ctx.output_params_fname = 'output_params.json'
        self.ctx.output_struct_fname = 'fit_porosity_volume.vti'

    def submit_filter(self):
        """Run the structure filtering process"""
        self.report('Submitting structure filtering process...')

        metadata = copy.deepcopy(self.ctx.serial_metadata)
        metadata['call_link_label'] = 'filter'

        _, node = launch_shell_job(
            self.inputs.wood_ms_code,
            arguments=(
                'postproc filter-porosity --config-file {input_params} --input_file {structure}'
            ),
            nodes={
                'structure': self.inputs.wood_structure,
                'input_params': self.ctx.input_file,
            },
            outputs=[
                self.ctx.outdir_name,
                os.path.join(self.ctx.outdir_name, self.ctx.parsed_params_fname),
                os.path.join(self.ctx.outdir_name, self.ctx.output_params_fname),
                os.path.join(self.ctx.outdir_name, self.ctx.output_struct_fname),
            ],
            metadata=metadata,
            submit=True,
        )

        self.report(f"Submitted structure filtering process: PK <{node.pk}>")

        return ToContext(filtering=node)

    def inspect_filter(self):
        """Inspect the results of the structure filtering process and expose outputs"""
        calc = self.ctx.filtering
        if not calc.is_finished_ok:
            self.report(f"ERROR: Structure filtering failed! Check: verdi process report {calc.pk}")
            return self.exit_codes.ERROR_FILTER_FAILED

        res = calc.outputs

        pp_node = res[self.ctx.parsed_params_fname.replace('.', '_')]
        op_node = res[self.ctx.output_params_fname.replace('.', '_')]
        st_node = res[self.ctx.output_struct_fname.replace('.', '_')]

        pp_node_dct = utils.json_file_to_dict(pp_node)
        op_node_dct = utils.json_file_to_dict(op_node)

        self.out('parsed_params', pp_node_dct)
        self.out('params', op_node_dct)
        self.out('structure', st_node)

        final_porosity = extract_porosity_from_params(op_node_dct)
        self.out('actual_porosity', final_porosity)

        self.report(f"✓ Structure filtering complete! Actual porosity: {final_porosity.value:.4f}")
