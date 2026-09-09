"""Command line scripts to launch a `` for testing and demonstration purposes."""
import json

from aiida import orm
from aiida.cmdline.utils import decorators

from . import cmd_launch
from ..utils import launch, options


@cmd_launch.command('generate_permeability')
# Required parameters
@options.WOOD_TYPE(required=True)
@options.GENERATE_PARAMS_FILE(required=True)
@options.FILTER_PARAMS_FILE(required=True)
@options.LB_RESOLUTION()
@options.WALL_PERMEABILITY()
# Codes
@options.WOOD_MS_CODE(required=True)
@options.PERMEABILITY_CODE(required=True)
# Either/or params
@options.WOOD_STRUCTURE_FILE(required=False)
@options.WOOD_STRUCT_NODE(required=False)
# Optional parameters,
@options.ARRAY_NAME(required=False)
@options.SCALING_FACTOR()
@options.UPHYS()
@options.TAU()
@options.INLET_PRESSURE()
@options.FLUID_DENSITY()
@options.KINEMATIC_VISCOSITY()
@options.TOLERANCE()
@options.UNIFORM_GUO_ZHAO()
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
    wood_type, generate_params_file, filter_params_file,
    resolution, wall_permeability,
    # Codes
    wood_ms_code,
    permeability_code,
    clean_workdir,
    # Resources
    num_nodes,
    num_mpiprocs_per_machine,
    max_wallclock_seconds,
    with_mpi,
    daemon,
    # Optional parameters
    # array_name,
    # scaling_factor, uphys,
    # inlet_pressure, tau,
    # kinematic_viscosity, fluid_density,
    # tolerance, uniform_guo_zhao,
    **optional
):
    """Launch the infiltration workflow."""
    from aiida.plugins import WorkflowFactory

    workchain = WorkflowFactory('aitw.wood_permeability.wood_permeability')

    with open(generate_params_file, 'r') as f:
        gen_params = json.load(f)
    if isinstance(gen_params, dict):
        gen_params = [gen_params]

    filter_params = {}
    if filter_params_file is not None:
        with open(filter_params_file, 'r') as f:
            filter_params = json.load(f)

    olb_params = {}
    olb_params['resolution'] = resolution
    olb_params['dSolid'] = wall_permeability

    # Optional parameters
    for opt_param, param_key in options.PERMEABILITY_PARAM_MAP.items():
        value = optional.get(opt_param)
        if value is not None:
            olb_params[param_key] = value

    for param_set in gen_params:
        builder = workchain.get_builder()

        # Generate
        builder.generator.wood_type = orm.Str(wood_type)
        builder.generator.input_params = orm.Dict(dict=param_set)

        # Filter
        builder.filter.input_params = orm.Dict(dict=filter_params)

        # Permeability
        builder.permeability.parameters = orm.Dict(dict=olb_params)

        # Metadata
        mdata_options = {'resources': {}}
        resources = mdata_options['resources']

        resources['num_machines'] = num_nodes
        mdata_options['withmpi'] = with_mpi
        mdata_options['max_wallclock_seconds'] = max_wallclock_seconds
        if num_mpiprocs_per_machine is not None:
            resources['num_mpiprocs_per_machine'] = num_mpiprocs_per_machine

        builder.wood_ms_code = wood_ms_code
        builder.permeability_code = permeability_code
        builder.shelljob.metadata.options = mdata_options
        builder.clean_workdir = orm.Bool(clean_workdir)


        launch.launch_process(builder, daemon=daemon)
