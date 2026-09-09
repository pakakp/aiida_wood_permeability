"""Base WorkChain for the other workflows in this package."""

from aiida import orm
from aiida.engine import WorkChain
from aiida.plugins import CalculationFactory

from . import utils as utils

ShellJob = CalculationFactory('core.shell')

class BaseSehllJobChain(WorkChain):
    """Base WorkChain for the other workflows in this package."""
    shellcode_name = None

    @classmethod
    def define(cls, spec):
        super().define(spec)

        # ── INPUTS ──────────────────────────────────────────────
        spec.expose_inputs(
            ShellJob,
            namespace='shelljob',
            include=('metadata', ),
            namespace_options={
                'required': True,
                'populate_defaults': False,
            }
        )
        spec.input(
            'clean_workdir', valid_type=orm.Bool,
            default=lambda: orm.Bool(False),
            help='If `True`, work directories of all called calculation will be cleaned at the end of execution.'
        )

    def setup(self):
        """Setup method for the base workchain."""
        code = getattr(self.inputs, self.shellcode_name, None)
        if code is None:
            raise ValueError(f"Input '{self.shellcode_name}' is required but not provided.")

        computer: orm.Computer = code.computer
        metadata_tpl = dict(self.inputs.shelljob.metadata)

        serial_mdata, parall_mdata = utils.create_metadata(computer, metadata_tpl, report_func=self.report)

        self.ctx.serial_metadata = serial_mdata
        self.ctx.parall_metadata = parall_mdata

    def _on_terminated(self):
        """Clean the working directories of all child calculations if `clean_workdir=True` in the inputs."""
        if self.inputs.clean_workdir.value is False:
            self.report('remote folders will not be cleaned')
            return

        cleaned_calcs = utils.clean_workchain_calcs(self.node)

        if cleaned_calcs:
            self.report(f"cleaned remote folders of calculations: {' '.join(map(str, cleaned_calcs))}")

    def on_terminated(self):
        """Clean the working directories of all child calculations if `clean_workdir=True` in the inputs."""
        super().on_terminated()
        self._on_terminated()
