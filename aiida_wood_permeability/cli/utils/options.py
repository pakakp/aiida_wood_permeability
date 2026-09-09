# -*- coding: utf-8 -*-
"""Pre-defined overridable options for commonly used command line interface parameters."""
from aiida.cmdline.params import types
from aiida.cmdline.params.options import OverridableOption
import click

# def validate_deformation_velocities(ctx, param, value):
#     """Validate that the deformation velocities are a comma-separated list of positive floats."""
#     if value is None:
#         return None
#     try:
#         velocities = [float(v) for v in value.split(',')]
#         if any(v <= 0 for v in velocities):
#             raise ValueError
#         return velocities
#     except:
#         raise click.BadParameter('Deformation velocities must be a comma-separated list of positive numbers.')

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

PARAM_RESOLUTION = OverridableOption(
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
