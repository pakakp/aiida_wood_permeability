"""
Single structure permeability calculation workflow.
Calculates permeability tensor (X, Y, Z directions) for one wood structure.
Runs three ShellJobs in parallel, one per flow direction.
"""
from aiida import orm
from aiida.engine import WorkChain, ToContext, calcfunction
from aiida_shell import launch_shell_job


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


class SingleStructurePermeabilityWorkChain(WorkChain):
    """
    Calculate 3D permeability tensor for a single structure.

    Runs the OpenLB permeability solver in X, Y, Z directions in parallel
    and assembles the results into a permeability_tensor Dict.
    """

    @classmethod
    def define(cls, spec):
        super().define(spec)

        # ── INPUTS ──────────────────────────────────────────────
        spec.input('code', valid_type=orm.InstalledCode,
                   help='OpenLB permeability executable')
        spec.input('vti_file', valid_type=orm.SinglefileData,
                   help='VTI structure file')
        spec.input('parameters', valid_type=orm.Dict,
                   help='Base simulation parameters (flowDirection will be overridden per run)')
        spec.input('metadata_options', valid_type=orm.Dict, required=False,
                   help='Computational resources and options')
        
        # OUTLINE
        spec.outline(
            cls.setup,
            cls.submit_three_directions,
            cls.collect_tensor,
        )
        
        # OUTPUTS
        spec.output('permeability_tensor', valid_type=orm.Dict,
                   help='Permeability tensor with k_x, k_y, k_z')
        
        # EXIT CODES
        spec.exit_code(400, 'ERROR_CALCULATION_FAILED',
                       message='One or more OpenLB permeability calculations failed')
        spec.exit_code(401, 'ERROR_OUTPUT_MISSING',
                       message='permeability.dat file not found or could not be parsed')

    def setup(self):
        self.report("Setting up 3-direction permeability calculation")

    def submit_three_directions(self):
        """Submit X, Y, Z calculations in parallel."""
        params = self.inputs.parameters.get_dict()

        if 'metadata_options' in self.inputs:
            comp_options = self.inputs.metadata_options.get_dict()
        else:
            comp_options = {
                'options': {
                    'resources': {
                        'num_machines': 1,
                        'num_mpiprocs_per_machine': 32,
                    },
                    'max_wallclock_seconds': 15000,
                    'withmpi': True,
                }
            }

        direction_names = ['X', 'Y', 'Z']
        calcs = {}
        
        for direction in [0, 1, 2]:
            # Copy parameters and set direction
            direction_params = params.copy()
            direction_params['flowDirection'] = direction

            # Positional arguments matching the OpenLB permeability solver CLI
            arguments = [
                '{vti_file}',
                direction_params.get('arrayname', 'ImageFile'),
                str(direction_params['scaling_factor']),
                str(direction_params['uout']),
                str(direction_params['resolution']),
                str(direction_params['pressure_drop']),
                str(direction_params['tau']),
                str(direction_params['dSolid']),
                str(direction_params['kinematicViscosity']),
                str(direction_params['fluidDensity']),
                str(direction_params['tolerance']),
                str(direction_params['flowDirection']),
                str(direction_params['uniformguozhao'])
            ]
            
            # Prepare metadata
            metadata = comp_options.copy()
            metadata['call_link_label'] = f'openlb_{direction_names[direction]}'

            self.report(f"Submitting OpenLB calculation for {direction_names[direction]} direction")

            _, node = launch_shell_job(
                self.inputs.code,
                arguments=arguments,
                nodes={'vti_file': self.inputs.vti_file},
                filenames={'vti_file': 'structure.vti'},
                outputs=['permeability.dat'],
                metadata=metadata,
                submit=True,
            )

            calcs[f'calc_dir_{direction}'] = node

        self.report("Submitted 3 OpenLB calculations (X, Y, Z) in parallel")
        return ToContext(**calcs)

    def collect_tensor(self):
        """Collect permeability values from all three directions."""
        for direction in [0, 1, 2]:
            calc_node = self.ctx[f'calc_dir_{direction}']
            if calc_node.exit_status not in [0, 410]:
                self.report(f"Calculation in direction {direction} failed "
                            f"(PK {calc_node.pk}, exit {calc_node.exit_status})")
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
