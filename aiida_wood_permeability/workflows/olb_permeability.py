"""
Single structure permeability calculation workflow.
Calculates permeability tensor (X, Y, Z directions) for one wood structure.
Runs three ShellJobs in parallel, one per flow direction.
"""
import copy

from aiida import orm
from aiida.engine import ToContext, calcfunction
from aiida.plugins import CalculationFactory
from aiida_shell import launch_shell_job

from . import utils as utils
from .base import BaseSehllJobChain


@calcfunction
def parse_permeability_tensor(perm_x, perm_y, perm_z):
    """
    Parse the three permeability output files and return a stored Dict node.
    A calcfunction is required because WorkChains may not return bare
    (unstored) Data nodes.
    """
    def read_value(f):
        with f.open() as fh:
            return float(fh.read().strip())

    return orm.Dict(dict={
        'k_x':  read_value(perm_x),
        'k_y':  read_value(perm_y),
        'k_z':  read_value(perm_z),
        'unit': 'm^2',
    })

ShellJob = CalculationFactory('core.shell')

class OLBPermeabilityWorkChain(BaseSehllJobChain):
    """
    Calculate 3D permeability tensor for a single structure.

    Runs the OpenLB permeability solver in X, Y, Z directions in parallel
    and assembles the results into a permeability_tensor Dict.
    """
    shellcode_name = 'code'

    @classmethod
    def define(cls, spec):
        super().define(spec)

        # ── INPUTS ──────────────────────────────────────────────
        spec.input('code', valid_type=orm.InstalledCode, help='OpenLB permeability executable')
        spec.input('vti_file', valid_type=orm.SinglefileData, help='VTI structure file')
        spec.input(
            'parameters', valid_type=orm.Dict,
            help='Base simulation parameters (flowDirection will be overridden per run)'
        )

        spec.expose_inputs(
            ShellJob,
            namespace='shelljob',
            include=('metadata', ),
            namespace_options={
                'required': True,
                'populate_defaults': False,
            }
        )
        spec.input(
            'clean_workdir', valid_type=orm.Bool,
            default=lambda: orm.Bool(False),
            help='If `True`, work directories of all called calculation will be cleaned at the end of execution.'
        )

        # OUTLINE
        spec.outline(
            cls.setup,

            cls.prepare_input,
            cls.submit_lb_permeability,
            cls.inspect_lb_permeability,
        )

        # OUTPUTS
        spec.output('permeability_tensor', valid_type=orm.Dict, help='Permeability tensor with k_x, k_y, k_z')

        # EXIT CODES
        spec.exit_code(
            400, 'ERROR_CALCULATION_FAILED',
            message='One or more OpenLB permeability calculations failed'
        )
        spec.exit_code(
            401, 'ERROR_OUTPUT_MISSING',
            message='permeability.dat file not found or could not be parsed'
        )

    def prepare_input(self):
        """Prepare the input parameters for the OpenLB permeability solver."""
        params = self.inputs.parameters.get_dict()
        keys = [
            'arrayname', 'scaling_factor', 'uout', 'resolution',
            'pressure_drop', 'tau', 'dSolid', 'kinematicViscosity',
            'fluidDensity', 'tolerance', 'flowDirection', 'uniformguozhao'
        ]
        defaults = {
            'arrayname': 'ImageFile',
            'flowDirection': None,
        }

        missing_keys = [key for key in keys if key not in params and key not in defaults]
        if missing_keys:
            raise ValueError(f"Missing required parameters: {missing_keys}")

        self.ctx.input_keys = keys
        self.ctx.input_defaults = defaults

    def submit_lb_permeability(self):
        """Submit the OpenLB permeability solver for X, Y, Z directions in parallel."""
        self.report('Submitting OpenLB permeability calculations for X, Y, Z directions in parallel')

        report = ''
        params = self.inputs.parameters.get_dict()
        directions = ['X', 'Y', 'Z']
        calcs = {}

        for i,direction in enumerate(directions):
            metadata = copy.deepcopy(self.ctx.parall_metadata)
            metadata['call_link_label'] = f'openlb_permeability_{direction}'

            defaults = self.ctx.input_defaults.copy()
            defaults['flowDirection'] = i

            input_lst = [str(params.get(key, defaults.get(key))) for key in self.ctx.input_keys]

            _, node = launch_shell_job(
                self.inputs.code,
                arguments=['{vti_file}', *input_lst],
                nodes={'vti_file': self.inputs.vti_file},
                outputs=['permeability.dat'],
                metadata=metadata,
                submit=True,
            )

            calcs[f'calc_dir_{i}'] = node
            report += f" - {direction} <{node.pk}>"

        self.report(f"Submitted OpenLB permeability calculations{report}")

        return ToContext(**calcs)

    def inspect_lb_permeability(self):
        """Inspect the results of the OpenLB permeability calculations and collect the tensor."""
        failed = False
        for direction in [0, 1, 2]:
            calc_node = self.ctx[f'calc_dir_{direction}']
            if not calc_node.is_finished_ok:
                failed = True
                self.report(f"Calculation in direction {direction} failed (PK {calc_node.pk}, exit {calc_node.exit_status})")
        if failed:
            return self.exit_codes.ERROR_CALCULATION_FAILED

        try:
            perm_x = self.ctx['calc_dir_0'].outputs['permeability_dat']
            perm_y = self.ctx['calc_dir_1'].outputs['permeability_dat']
            perm_z = self.ctx['calc_dir_2'].outputs['permeability_dat']
        except Exception as e:
            self.report(f"Failed to find permeability output files: {e}")
            return self.exit_codes.ERROR_OUTPUT_MISSING

        try:
            tensor = parse_permeability_tensor(perm_x, perm_y, perm_z)
        except Exception as e:
            self.report(f"Failed to parse permeability values: {e}")
            return self.exit_codes.ERROR_OUTPUT_MISSING

        self.out('permeability_tensor', tensor)
        t = tensor.get_dict()
        self.report(f"✓ Permeability tensor calculated:")
        self.report(f"  k_x = {t['k_x']:.3e} m²")
        self.report(f"  k_y = {t['k_y']:.3e} m²")
        self.report(f"  k_z = {t['k_z']:.3e} m²")
