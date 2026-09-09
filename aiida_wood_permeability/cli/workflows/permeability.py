"""Command line scripts to launch a `` for testing and demonstration purposes."""
import json

from aiida import orm
from aiida.cmdline.utils import decorators
import click

from . import cmd_launch
from ..utils import launch, options


@cmd_launch.command('permeability')
# Required parameters
@options.LB_RESOLUTION()
@options.WALL_PERMEABILITY()
# Codes
@options.PERMEABILITY_CODE(required=True)
# Either/or params
@options.WOOD_STRUCTURE_FILE(required=False)
@options.WOOD_STRUCT_NODE(required=False)
# Optional parameters,
@options.SCALING_FACTOR()
@options.UPHYS()
@options.TAU()
@options.INLET_PRESSURE()
@options.FLUID_DENSITY()
@options.KINEMATIC_VISCOSITY()
@options.TOLERANCE()
@options.UNIFORM_GUO_ZHAO()
@options.ARRAY_NAME(required=False)
@options.CLEAN_WORKDIR()
# Resources
@options.NUM_NODES()
@options.NUM_MPIPROCS_PER_MACHINE(required=False)
@options.MAX_WALLCLOCK_SECONDS()
@options.WITH_MPI(default=False)
@options.DAEMON()
@decorators.with_dbenv()
def launch_workflow(
    # Required parameters
    resolution, wall_permeability,
    # Codes
    permeability_code,
    # Either/or params
    wood_structure_file, wood_structure_node,
    # Resources
    num_nodes,
    num_mpiprocs_per_machine,
    max_wallclock_seconds,
    with_mpi,
    daemon,
    # Optional parameters,
    clean_workdir,
    # array_name,
    # scaling_factor, uphys,
    # inlet_pressure, tau,
    # kinematic_viscosity, fluid_density,
    # tolerance, uniform_guo_zhao,
    **optional
):
    """Launch the infiltration workflow."""
    from aiida.plugins import WorkflowFactory

    workchain = WorkflowFactory('aitw.wood_permeability.olb_permeability')

    params = {}

    builder = workchain.get_builder()

    # Required parameters
    params['resolution'] = resolution
    params['dSolid'] = wall_permeability

    # Codes
    builder.code = permeability_code

    # Either/or params
    if wood_structure_node is not None:
        if wood_structure_file is not None:
            click.echo('WARNING: both structure NODE and FILE passed. Node will be used and file will be ignored.')
        builder.vti_file = wood_structure_node
    elif wood_structure_file is not None:
        builder.vti_file = orm.SinglefileData(file=wood_structure_file)

    # Optional parameters
    for opt_param, param_key in options.PERMEABILITY_PARAM_MAP.items():
        value = optional.get(opt_param)
        if value is not None:
            params[param_key] = value

    builder.clean_workdir = orm.Bool(clean_workdir)

    # Metadata
    mdata_options = {'resources': {}}
    resources = mdata_options['resources']

    resources['num_machines'] = num_nodes
    mdata_options['withmpi'] = with_mpi
    mdata_options['max_wallclock_seconds'] = max_wallclock_seconds
    if num_mpiprocs_per_machine is not None:
        resources['num_mpiprocs_per_machine'] = num_mpiprocs_per_machine
    builder.shelljob.metadata.options = mdata_options

    builder.parameters = orm.Dict(dict=params)

    launch.launch_process(builder, daemon=daemon)
