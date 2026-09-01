"""
Structure filtering workflow for pre-generated wood structures.
Converts a tiff stack (SaveWood.tar.gz) to VTI format using filter.py.
"""
from aiida import orm
from aiida.engine import WorkChain, ToContext, calcfunction
from aiida_shell import launch_shell_job


@calcfunction
def parse_porosity(porosity_file):
    """
    Read the actual porosity value written by filter.py and return it
    as a stored Float node.  A calcfunction is required because WorkChains
    may not return bare (unstored) Data nodes.
    """
    with porosity_file.open() as f:
        return orm.Float(float(f.read().strip()))


@calcfunction
def passthrough_vti(vti_file):
    """
    Return the VTI file via a calcfunction so AiiDA can attach a proper
    CREATE link from this workflow to the output node.
    Without this, AiiDA rejects the RETURN link on the SinglefileData
    node produced by the child ShellJob.
    """
    return vti_file.clone()


class StructureFilterWorkChain(WorkChain):
    """
    Filter pre-generated tiff stack to VTI format.

    Steps:
    1. Filter tiff stack to VTI
    2. Parse actual porosity via calcfunction (required for AiiDA provenance)

    Use this when you want to apply different filter parameters
    to the same generated structure, or as a standalone pre-processing step.
    """

    @classmethod
    def define(cls, spec):
        super().define(spec)

        # ── INPUTS ──────────────────────────────────────────────
        spec.input('filter_code', valid_type=orm.InstalledCode,
                   help='filter.py code (local)')

        spec.input('structure_tar', valid_type=orm.SinglefileData,
                   help='SaveWood.tar.gz from previous generation')
        spec.input('structure_dir_name', valid_type=orm.Str,
                   help='Name of directory inside tar (e.g. SaveBirch_0)')

        spec.input('filter_params', valid_type=orm.Dict,
                   help='Parameters for filter.py')

        # ── OUTLINE ──────────────────────────────────────────────
        spec.outline(
            cls.setup,
            cls.filter_to_vti,
            cls.check_filter,
        )

        # ── OUTPUTS ──────────────────────────────────────────────
        spec.output('vti_file', valid_type=orm.SinglefileData,
                    help='Generated VTI file')
        spec.output('actual_porosity', valid_type=orm.Float,
                    help='Measured porosity from filter.py')

        # ── EXIT CODES ────────────────────────────────────────────
        spec.exit_code(401, 'ERROR_FILTER_FAILED',
                       message='VTI filtering failed')

    def setup(self):
        self.report(f"Starting structure filtering for: {self.inputs.structure_dir_name.value}")

    def filter_to_vti(self):
        """Filter tiff stack to VTI format"""
        dir_name = self.inputs.structure_dir_name.value
        self.report(f"Converting {dir_name} to VTI...")

        filter_params = self.inputs.filter_params.get_dict()

        arguments = [f'{dir_name}/FinalVolumeSlice', 'structure.vti', '--down', '1']

        param_map = {
            'threshold': '--threshold',
            'solid_dark': '--solid-dark',
            'down': '--down',
            'smooth_low_iters': '--smooth-low-iters',
            'smooth_sigma': '--smooth-sigma',
            'thicken': '--thicken',
            'final_smooth_iters': '--final-smooth-iters',
            'final_smooth_sigma': '--final-smooth-sigma',
            'upsample_intermediate': '--upsample-intermediate',
            'upsample_final': '--upsample-final',
            'pad': '--pad',
            'pad_xy_only': '--pad-xy-only',
            'porosity': '--porosity',
            'sdf_sigma': '--sdf-sigma',
            'adjust_porosity_post': '--adjust-porosity-post',
            'allow_boundary_removal': '--allow-boundary-removal',
            'majority_filter': '--majority-filter',
            'min_gradient': '--min-gradient',
            'verbose': '--verbose',
        }

        for key, flag in param_map.items():
            if key in filter_params:
                value = filter_params[key]
                if value is None or value == 'None':
                    continue  # explicitly unset -- omit the flag entirely.
                                # Checking the string 'None' too
                if isinstance(value, bool):
                    if value:
                        arguments.append(flag)
                else:
                    arguments.extend([flag, str(value)])

        self.report(f"filter.py {' '.join(arguments)}")

        _, node = launch_shell_job(
            self.inputs.filter_code,
            arguments=arguments,
            nodes={'structure_tar': self.inputs.structure_tar},
            filenames={'structure_tar': 'SaveWood.tar.gz'},
            outputs=['structure.vti', 'actual_porosity.txt'],
            metadata={
                'call_link_label': 'filter_to_vti',
                'options': {
                    'resources': {
                        'num_machines': 1,
                        'num_mpiprocs_per_machine': 1,
                    },
                    'max_wallclock_seconds': 24000,
                    'withmpi': False,
                    'prepend_text': 'tar xzf SaveWood.tar.gz',
                }
            },
            submit=True,
        )

        return ToContext(filtering=node)

    def check_filter(self):
        """Check if filtering succeeded and expose outputs"""
        # Accept 410 (stderr warnings but succeeded)
        if self.ctx.filtering.exit_status not in [0, 410]:
            self.report("ERROR: Filtering failed!")
            self.report(f"Check: verdi process report {self.ctx.filtering.pk}")
            return self.exit_codes.ERROR_FILTER_FAILED

        # Log available keys to catch aiida-shell sanitisation surprises
        self.report(f"ShellJob outputs available: {list(self.ctx.filtering.outputs)}")

        # aiida-shell sanitises filenames: dots → underscores
        # 'structure.vti'       → 'structure_vti'
        # 'actual_porosity.txt' → 'actual_porosity_txt'
        vti_file = passthrough_vti(self.ctx.filtering.outputs['structure_vti'])
        self.report(f"✓ VTI file created: PK {vti_file.pk}")
        self.out('vti_file', vti_file)

        actual_porosity = parse_porosity(self.ctx.filtering.outputs['actual_porosity_txt'])
        self.out('actual_porosity', actual_porosity)

        target_porosity = self.inputs.filter_params.get_dict().get('porosity', 'N/A')
        self.report(f"  Target porosity: {target_porosity}")
        self.report(f"  Actual porosity: {actual_porosity.value:.4f}")
        self.report("✓ Structure filtering complete!")
