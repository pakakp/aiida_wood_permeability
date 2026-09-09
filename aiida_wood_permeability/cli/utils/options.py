# -*- coding: utf-8 -*-
"""Pre-defined overridable options for commonly used command line interface parameters."""
from aiida.cmdline.params import types
from aiida.cmdline.params.options import OverridableOption
import click

##################################################################################################################
# Options for WOOD_MS specific calculations

def validate_resolution(ctx, param, value):
    """Validate that the resolution is a comma-separated list of three positive integers."""
    if value is None:
        return value
    try:
        resolution = [int(v) for v in value.split(',')]
        if len(resolution) != 3 or any(v <= 0 for v in resolution):
            raise ValueError
        return resolution
    except:
        raise click.BadParameter('Resolution must be a comma-separated list of three positive integers.')


WOOD_MS_CODE = OverridableOption(
    '--wood-ms', 'wood_ms_code', type=types.CodeParamType(entry_point='core.shell'),
    help='A single code for wood_ms (e.g. wood_ms@localhost).'
)

WOOD_TYPE = OverridableOption(
    '--wood-type',
    'wood_type',
    type=click.Choice(['birch', 'spruce']),
    help='The type of wood to simulate.'
)

PARAMS_FILE = OverridableOption(
    '--params-file',
    'params_file',
    type=click.Path(exists=True, dir_okay=False, readable=True),
    help='Path to a JSON file containing the simulation parameters.'
)

WOOD_STRUCTURE_FILE = OverridableOption(
    '--wood-structure-file',
    'wood_structure_file',
    type=click.Path(exists=True, dir_okay=False, readable=True, resolve_path=True),
    help='Path to a file containing the wood structure.'
)

WOOD_STRUCT_NODE = OverridableOption(
    '--wood-structure-node',
    'wood_structure_node',
    type=types.DataParamType(sub_classes=('aiida.data:singlefile',)),
    help='A SinglefileData node containing the wood structure.'
)

PARAM_CELL_R = OverridableOption(
    '--cell-r',
    'cell_r',
    type=click.FloatRange(min=0.0, min_open=True),
    help='The cell_r parameter for the simulation.'
)

PARAM_CELL_WALL_THICKNESS = OverridableOption(
    '--cell-wall-thickness',
    'cell_wall_thickness',
    type=click.FloatRange(min=0.0, min_open=True),
    help='The cell_wall_thickness parameter for the simulation.'
)

GRID_RESOLUTION = OverridableOption(
    '--resolution',
    'resolution',
    type=click.STRING,
    callback=validate_resolution,
    help='A comma-separated list of three integers representing the resolution in xyz directions (e.g., "10,10,10").'
)

PARAM_SEED = OverridableOption(
    '--seed',
    'seed',
    type=click.IntRange(min=0),
    help='The seed for the random number generator.'
)

##################################################################################################################
# Options for OpenLB permeability calculations

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
    default=1e-5,
    show_default=True,
    help='The scaling factor to apply to the permeability calculation. Untis: [m]'
)

UPHYS = OverridableOption(
    '--uphys',
    'uphys',
    type=click.FloatRange(min=0.0, min_open=True),
    default=1e-3,
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
    default=1e5,
    show_default=True,
    help='The applied pressure gradient to use for the permeability calculation. Units: [Pa/m]'
)

TAU = OverridableOption(
    '--tau',
    'tau',
    type=click.FLOAT,
    default=0.8,
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
    default=1e-6,
    show_default=True,
    help='The fluid kinematic viscosity to use for the permeability calculation. Units: [m²/s]. Example: 1e-6 for water.'
)

FLUID_DENSITY = OverridableOption(
    '--fluid-density',
    'fluid_density',
    type=click.FLOAT,
    default=1000.0,
    show_default=True,
    help='The fluid density to use for the permeability calculation. Units: [kg/m³]. Example: 1000 for water.'
)

TOLERANCE = OverridableOption(
    '--tolerance',
    'tolerance',
    type=click.FLOAT,
    default=1e-5,
    show_default=True,
    help='The convergence tolerance used during permeability monitoring.'
)

UNIFORM_GUO_ZHAO = OverridableOption(
    '--uniform-guo-zhao',
    'uniform_guo_zhao',
    type=click.Choice(['0', '1']),
    default='0',
    show_default=True,
    help='The mode for the permeability calculation: 0 = Production mode, 1 = Diagnostic mode.'
)

##################################################################################################################
# Resource options for calculations

NUM_NODES = OverridableOption(
    '-m',
    '--num-nodes',
    type=click.IntRange(min=1),
    default=1,
    show_default=True,
    help='The number of nodes to use for the calculations.'
)

NUM_MPIPROCS_PER_MACHINE = OverridableOption(
    '--num-mpiprocs-per-machine',
    type=click.IntRange(min=1),
    help='The number of MPI processes to use per node.'
)

MAX_WALLCLOCK_SECONDS = OverridableOption(
    '-w',
    '--max-wallclock-seconds',
    type=click.IntRange(min=1),
    default=1800,
    show_default=True,
    help='the maximum wallclock time in seconds to set for the calculations.'
)

WITH_MPI = OverridableOption(
    '--with-mpi/--without-mpi',
    type=bool,
    default=True,
    show_default=True,
    help='Run the calculations with MPI enabled.'
)

DAEMON = OverridableOption(
    '-d',
    '--daemon',
    is_flag=True,
    default=False,
    show_default=True,
    help='Submit the process to the daemon instead of running it locally.'
)

CLEAN_WORKDIR = OverridableOption(
    '-x',
    '--clean-workdir',
    is_flag=True,
    default=False,
    show_default=True,
    help='Clean the remote folder of all the launched calculations after completion of the workchain.'
)
