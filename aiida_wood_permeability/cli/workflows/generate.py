"""Command line scripts to launch a `` for testing and demonstration purposes."""
import json

from aiida import orm
from aiida.cmdline.utils import decorators
import click

from . import cmd_launch
from ..utils import launch, options


@cmd_launch.command('generate')
# @options.apply_options_wood_ms(
#     overrides={
#         'cell_r': {'required': False},
#         'cell_wall_thickness': {'required': False},
#         'resolution': {'required': False},
#         'seed': {'required': False},
#     }
# )
# Required parameters
@options.WOOD_TYPE(required=True)
@options.GENERATE_PARAMS_FILE(required=True)
# Codes
@options.WOOD_MS_CODE(required=True)
# Optional parameters,
@options.WOOD_MS_CELL_R(required=False)
@options.WOOD_MS_CELL_WALL_THICKNESS(required=False)
@options.WOOD_MS_RESOLUTION(required=False)
@options.PARAM_SEED(required=False)
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
    wood_type, generate_params_file,
    # Codes
    wood_ms_code,
    # Optional parameters,
    cell_r, cell_wall_thickness, grid_resolution, seed,
    clean_workdir,
    # Resources
    max_wallclock_seconds,
    # num_nodes,
    # num_mpiprocs_per_machine,
    # with_mpi,
    daemon,
):
    """Launch the infiltration workflow."""
    from aiida.plugins import WorkflowFactory

    workchain = WorkflowFactory('aitw.wood_permeability.wood_structure_generator')

    with open(generate_params_file, 'r') as f:
        params = json.load(f)
    if isinstance(params, dict):
        params = [params]

    click.echo(f'Launching {len(params)} workflows for wood type: {wood_type} with parameters from file: {generate_params_file}')
    for param_set in params:
        builder = workchain.get_builder()

        # Required parameters
        builder.wood_type = orm.Str(wood_type)
        builder.input_params = orm.Dict(dict=param_set)

        # Codes
        builder.wood_ms_code = wood_ms_code

        # Optional parameters
        if cell_r is not None:
            builder.cell_r = orm.Float(cell_r)
        if cell_wall_thickness is not None:
            builder.cell_wall_thickness = orm.Float(cell_wall_thickness)
        if grid_resolution is not None:
            builder.resolution = orm.List(list=grid_resolution)
        if seed is not None:
            builder.seed = orm.Int(seed)

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
