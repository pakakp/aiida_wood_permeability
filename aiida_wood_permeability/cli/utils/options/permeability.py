
"""Command line options for the OpenLB permeability calculation."""
from aiida.cmdline.params import types
from aiida.cmdline.params.options import OverridableOption
import click

PERMEABILITY_PARAM_MAP = {
    'array_name': 'arrayname',
    'scaling_factor': 'scaling_factor',
    'uphys': 'uout',
    'inlet_pressure': 'pressure_drop',
    'tau': 'tau',
    'kinematic_viscosity': 'kinematicViscosity',
    'fluid_density': 'fluidDensity',
    'tolerance': 'tolerance',
    'uniform_guo_zhao': 'uniformguozhao'
}

PERMEABILITY_CODE = OverridableOption(
    '--permeability-code',
    'permeability_code',
    type=types.CodeParamType(entry_point='core.shell'),
    help='A single code for the OpenLB permeability calculation (e.g. openlb_permeability@localhost).'
)

ARRAY_NAME = OverridableOption(
    '--array-name',
    'array_name',
    type=click.STRING,
    # default='ImageFile',
    # default=None
    # show_default=True,
    help='The name of the array in the VTI file to use for the permeability calculation.'
)

SCALING_FACTOR = OverridableOption(
    '--scaling-factor',
    'scaling_factor',
    type=click.FLOAT,
    default=5e-7,
    show_default=True,
    help='The scaling factor to apply to the permeability calculation. Untis: [m]'
)

UPHYS = OverridableOption(
    '--uphys',
    'uphys',
    type=click.FloatRange(min=0.0, min_open=True),
    default=1.0,
    show_default=True,
    help='The outlet velocity magnitude to use for the permeability calculation. Units: [m/s]'
)

LB_RESOLUTION = OverridableOption(
    '--resolution',
    'resolution',
    type=click.IntRange(min=1),
    default=200,
    show_default=True,
    help='The lattice resolution to use for the permeability calculation.'
)

INLET_PRESSURE = OverridableOption(
    '--inlet-pressure',
    'inlet_pressure',
    type=click.FLOAT,
    default=10.0,
    show_default=True,
    help='The applied pressure gradient to use for the permeability calculation. Units: [Pa/m]'
)

TAU = OverridableOption(
    '--tau',
    'tau',
    type=click.FLOAT,
    default=1.0,
    show_default=True,
    help='The LBM relaxation time to use for the permeability calculation. Recommended: 0.6 < tau < 1.2'
)

WALL_PERMEABILITY = OverridableOption(
    '--wall-permeability',
    'wall_permeability',
    type=click.FLOAT,
    default=1e-16,
    show_default=True,
    help=(
        'The physical Darcy permeability assigned to the porous material. Units: [m²]. '
        'Typical wood values: 1e-18 ... 1e-14 m²'
    )
)

KINEMATIC_VISCOSITY = OverridableOption(
    '--kinematic-viscosity',
    'kinematic_viscosity',
    type=click.FLOAT,
    default=1e-4,
    show_default=True,
    help='The fluid kinematic viscosity to use for the permeability calculation. Units: [m²/s]. Example: 1e-6 for water.'
)

FLUID_DENSITY = OverridableOption(
    '--fluid-density',
    'fluid_density',
    type=click.FLOAT,
    default=1.0,
    show_default=True,
    help='The fluid density to use for the permeability calculation. Units: [kg/m³]. Example: 1000 for water.'
)

TOLERANCE = OverridableOption(
    '--tolerance',
    'tolerance',
    type=click.FLOAT,
    default=1e-6,
    show_default=True,
    help='The convergence tolerance used during permeability monitoring.'
)

UNIFORM_GUO_ZHAO = OverridableOption(
    '--uniform-guo-zhao',
    'uniform_guo_zhao',
    type=click.Choice(['0', '1']),
    default='1',
    show_default=True,
    help='The mode for the permeability calculation: 0 = Production mode, 1 = Diagnostic mode.'
)
