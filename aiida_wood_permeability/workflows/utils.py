"""Collection of utilities and calcfunctions used by the workchains."""
import copy
import json
import os

from aiida import orm
from aiida.engine import calcfunction


@calcfunction
def dict_to_json_file(
        input_dict: orm.Dict, **overrides: orm.Data
    ) -> orm.SinglefileData:
    """
    Convert an AiiDA Dict node to a JSON file and return it as a SinglefileData node.
    """
    params = input_dict.get_dict()

    for key, node in overrides.items():
        if isinstance(node, (orm.Int, orm.Float, orm.Str, orm.Bool)):
            value = node.value
        elif isinstance(node, orm.List):
            value = node.get_list()
        else:
            raise ValueError(f"Unsupported node type for override: {type(node)}")
        params[key] = value

    content = json.dumps(params, indent=4)

    return orm.SinglefileData(content=content, filename='input.json')

@calcfunction
def json_file_to_dict(json_file: orm.SinglefileData) -> orm.Dict:
    """
    Convert a JSON file (SinglefileData) to an AiiDA Dict node.
    """
    with json_file.open() as f:
        data = json.load(f)

    return orm.Dict(dict=data)

@calcfunction
def extract_volumes_3d(folder: orm.FolderData) -> dict[str, orm.SinglefileData]:
    """Extract the 3D volumes from the output folder and return them as a dictionary of SinglefileData nodes."""
    res = {}

    target_files = {
        'BeforeLocalVolume': 'initial',
        'BeforeGlobalVolume': 'after_local',
        'AfterGlobalVolume': 'after_global',
        'FinalVolume': 'final',
    }

    root = 'FinalVolume3D'
    for file_obj in folder.list_objects(path=root):
        filename = file_obj.name
        base, ext = os.path.splitext(filename)
        if base in target_files:
            path = os.path.join(root, filename)
            with folder.open(path, 'rb') as f:
                res[target_files[base]] = orm.SinglefileData(file=f, filename=filename)
    return res

def create_metadata(
        computer: orm.Computer, metadata_tpl: dict, report_func = lambda msg: None
    ) -> tuple[dict, dict]:
    """Setup the metadata templates for the calculations."""
    options = metadata_tpl['options'] = dict(metadata_tpl.get('options', {}))
    resources = options['resources'] = dict(options.get('resources', {}))

    if 'max_wallclock_seconds' not in options:
        report_func('WARNING: max_wallclock_seconds not set in metadata; using default of 3600 seconds.')
        options['max_wallclock_seconds'] = 3600

    if 'num_machines' not in resources:
        report_func('WARNING: num_machines not set in metadata; using default of 1 machine.')
        resources['num_machines'] = 1

    computer_num_mpiprocs = computer.get_default_mpiprocs_per_machine()
    if 'num_mpiprocs_per_machine' in resources:
        nmpm = resources['num_mpiprocs_per_machine']
        report_func(
            f'Using `num_mpiprocs_per_machine` from metadata: {nmpm} instead of value from'
            f'computer {computer_num_mpiprocs}.'
        )
    else:
        resources['num_mpiprocs_per_machine'] = computer_num_mpiprocs

    max_mem = computer.get_default_memory_per_machine()
    if max_mem is not None:
        options['max_memory_kb'] = max_mem

    options['redirect_stderr'] = True

    serial_mdata = copy.deepcopy(metadata_tpl)
    parall_mdata = copy.deepcopy(metadata_tpl)

    serial_mdata['options']['withmpi'] = False
    serial_mdata['options']['resources']['num_machines'] = 1
    serial_mdata['options']['resources']['num_mpiprocs_per_machine'] = 1

    return serial_mdata, parall_mdata

def clean_calcjob_remote(calcjob: orm.CalcJobNode) -> bool:
    """Clean the remote directory of a ``CalcJobNode``."""
    cleaned = False
    try:
        calcjob.outputs.remote_folder._clean()  # pylint: disable=protected-access
        cleaned = True
    except (IOError, OSError, KeyError):
        pass
    return cleaned

def clean_workchain_calcs(workchain: orm.WorkChainNode):
    """Clean all remote directories of a workchain's descendant calculations."""
    cleaned_calcs = []

    for called_descendant in workchain.called_descendants:
        if isinstance(called_descendant, orm.CalcJobNode):
            if clean_calcjob_remote(called_descendant):
                cleaned_calcs.append(called_descendant.pk)
