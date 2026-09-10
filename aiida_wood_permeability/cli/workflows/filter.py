"""Command line scripts to launch a `` for testing and demonstration purposes."""
import json

from aiida import orm
from aiida.cmdline.utils import decorators
import click

from . import cmd_launch
from ..utils import launch, options


@cmd_launch.command('filter')
# Codes
@options.WOOD_MS_CODE(required=True)
# Either/or params
@options.WOOD_STRUCTURE_FILE(required=False)
@options.WOOD_STRUCT_NODE(required=False)
# Optional parameters
@options.FILTER_PARAMS_FILE(required=False)
@options.CLEAN_WORKDIR()
# Resources
# @options.NUM_NODES()
# @options.NUM_MPIPROCS_PER_MACHINE(required=False)
@options.MAX_WALLCLOCK_SECONDS()
# @options.WITH_MPI(default=False)
@options.DAEMON()
@decorators.with_dbenv()
def launch_workflow(
    # Required parameters
    filter_params_file,
    # Codes
    wood_ms_code,
    # Either/or params
    wood_structure_file, wood_structure_node,
    # Optional parameters,
    clean_workdir,
    # Resources
    max_wallclock_seconds,
    # num_nodes,
    # num_mpiprocs_per_machine,
    # with_mpi,
    daemon
):
    """Launch the infiltration workflow."""
    from aiida.plugins import WorkflowFactory

    workchain = WorkflowFactory('aitw.wood_permeability.structure_filter')

    params = {}
    if filter_params_file is not None:
        with open(filter_params_file, 'r') as f:
            params = json.load(f)

    if not isinstance(params, dict):
        raise click.BadParameter(f"Invalid parameter file: {filter_params_file}. Expected a JSON object.")

    builder = workchain.get_builder()
    builder.input_params = orm.Dict(dict=params)

    # Codes
    builder.wood_ms_code = wood_ms_code

    # Either/or params
    if wood_structure_node is not None:
        if wood_structure_file is not None:
            click.echo('WARNING: both structure NODE and FILE passed. Node will be used and file will be ignored.')
        builder.wood_structure = wood_structure_node
    elif wood_structure_file is not None:
        builder.wood_structure = orm.SinglefileData(file=wood_structure_file)

    builder.clean_workdir = orm.Bool(clean_workdir)

    # Metadata
    mdata_options = {'resources': {}}
    resources = mdata_options['resources']

    num_nodes = 1
    num_mpiprocs_per_machine = 1
    with_mpi = False

    resources['num_machines'] = num_nodes
    mdata_options['withmpi'] = with_mpi
    mdata_options['max_wallclock_seconds'] = max_wallclock_seconds
    if num_mpiprocs_per_machine is not None:
        resources['num_mpiprocs_per_machine'] = num_mpiprocs_per_machine
    builder.shelljob.metadata.options = mdata_options

    launch.launch_process(builder, daemon=daemon)
