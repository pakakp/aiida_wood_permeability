"""Command line scripts to launch a `` for testing and demonstration purposes."""
import json

from aiida import orm
from aiida.cmdline.utils import decorators
import click

from . import cmd_launch
from ..utils import launch, options


@cmd_launch.command('permeability')
# Required parameters
@options.SCALING_FACTOR()
@options.UPHYS()
@options.LB_RESOLUTION()
@options.INLET_PRESSURE()
@options.TAU()
@options.WALL_PERMEABILITY()
@options.KINEMATIC_VISCOSITY()
@options.FLUID_DENSITY()
@options.TOLERANCE()
@options.UNIFORM_GUO_ZHAO()
# Codes
@options.PERMEABILITY_CODE(required=True)
# Either/or params
@options.WOOD_STRUCTURE_FILE(required=False)
@options.WOOD_STRUCT_NODE(required=False)
# Optional parameters,
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
    scaling_factor, uphys, resolution, inlet_pressure, tau,
    wall_permeability, kinematic_viscosity, fluid_density,
    tolerance, uniform_guo_zhao,
    # Codes
    permeability_code,
    # Either/or params
    wood_structure_file, wood_structure_node,
    # Optional parameters,
    array_name,
    clean_workdir,
    # Resources
    num_nodes,
    num_mpiprocs_per_machine,
    max_wallclock_seconds,
    with_mpi,
    daemon
):
    """Launch the infiltration workflow."""
    from aiida.plugins import WorkflowFactory

    workchain = WorkflowFactory('aitw.wood_permeability.olb_permeability')

    params = {}

    builder = workchain.get_builder()

    # Required parameters
    params['scaling_factor'] = scaling_factor
    params['uout'] = uphys
    params['resolution'] = resolution
    params['pressure_drop'] = inlet_pressure
    params['tau'] = tau
    params['dSolid'] = wall_permeability
    params['kinematicViscosity'] = kinematic_viscosity
    params['fluidDensity'] = fluid_density
    params['tolerance'] = tolerance
    params['uniformguozhao'] = uniform_guo_zhao

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
    if array_name is not None:
        params['arrayname'] = array_name

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
