"""Pre-defined overridable options for commonly used command line interface parameters."""
from aiida.cmdline.params.options import OverridableOption
import click

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
