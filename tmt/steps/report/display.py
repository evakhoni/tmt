from collections.abc import Sequence
from typing import Optional

import tmt
import tmt.log
import tmt.steps
import tmt.steps.report
from tmt.container import container, field
from tmt.result import BaseResult, CheckResult, Result, SubCheckResult, SubResult
from tmt.steps.execute import TEST_OUTPUT_FILENAME
from tmt.utils import Path

# How much test and test check info should be shifted to the right in the output.
# We want tests to be shifted by one extra level, with their checks shifted by
# yet another level.
TEST_SHIFT = 1
CHECK_SHIFT = 2
SUBRESULT_SHIFT = CHECK_SHIFT
SUBRESULT_CHECK_SHIFT = SUBRESULT_SHIFT + 1


@container
class ReportDisplayData(tmt.steps.report.ReportStepData):
    display_guest: str = field(
        default='auto',
        option='--display-guest',
        metavar='auto|always|never',
        choices=['auto', 'always', 'never'],
        help="""
             When to display full guest name in report: when more than a single guest was involved
             (default), always, or never.
             """,
    )


@tmt.steps.provides_method('display')
class ReportDisplay(tmt.steps.report.ReportPlugin[ReportDisplayData]):
    """
    Show test results on the terminal.

    Give a concise summary of test results directly on the terminal.
    Allows to select the desired level of verbosity.

    .. code-block:: yaml

        tmt run -l report        # overall summary only
        tmt run -l report -v     # individual test results
        tmt run -l report -vv    # show full paths to logs
        tmt run -l report -vvv   # provide complete test output
    """

    _data_class = ReportDisplayData

    def details(self, result: tmt.Result, verbosity: int, display_guest: bool) -> None:
        """
        Print result details.

        :param result: a test result to display.
        :param verbosity: how verbose should the report be. Generally equal to
            number of  ``--verbose``/``-v`` options given on command line.
            For ``1``, display only test name and its result, ``2`` will add
            log paths, and ``3`` or more would show the test output as well.
        :param display_guest: if set, guest multihost name would be part of the
            report.
        """

        def _display_log_info(log: Path, shift: int) -> None:
            """
            Display info about a single result log
            """

            # TODO: are we sure it cannot be None?
            assert self.step.plan.execute.workdir is not None

            self.verbose(
                log.name, self.step.plan.execute.workdir / log, color='yellow', shift=shift
            )

        def _display_log_content(log: Path, shift: int) -> None:
            """
            Display content of a single result log
            """

            # TODO: are we sure it cannot be None?
            assert self.step.plan.execute.workdir is not None

            self.verbose(
                'content',
                self.read(self.step.plan.execute.workdir / log),
                color='yellow',
                shift=shift,
            )

        def display_outcome(result: BaseResult) -> None:
            """
            Display a single result outcome
            """

            if isinstance(result, SubCheckResult):
                self.verbose(
                    f'{result.show()} ({result.event.value} check)', shift=SUBRESULT_CHECK_SHIFT
                )

            elif isinstance(result, CheckResult):
                self.verbose(f'{result.show()} ({result.event.value} check)', shift=CHECK_SHIFT)

            elif isinstance(result, SubResult):
                self.verbose(result.show(), shift=SUBRESULT_SHIFT)

            elif isinstance(result, Result):
                self.verbose(result.show(display_guest=display_guest), shift=TEST_SHIFT)

        def display_log_info(result: BaseResult) -> None:
            """
            Display info about result logs
            """

            # TODO: are we sure it cannot be None?
            assert self.step.plan.execute.workdir is not None

            shift = (TEST_SHIFT + 1) if isinstance(result, Result) else (CHECK_SHIFT + 1)

            for log in result.log:
                _display_log_info(log, shift)

        def display_log_content(result: BaseResult) -> None:
            """
            Display content of interesting result logs
            """

            # TODO: are we sure it cannot be None?
            assert self.step.plan.execute.workdir is not None

            shift = (TEST_SHIFT + 1) if isinstance(result, Result) else (CHECK_SHIFT + 1)

            for log in result.log:
                _display_log_info(log, shift)

                if log.name == TEST_OUTPUT_FILENAME:
                    _display_log_content(log, shift)

        def display_subresults(results: Sequence[BaseResult]) -> None:
            """
            Display subresults, checks and subresult checks
            """

            for subresult in results:
                display_outcome(subresult)

                if verbosity > 2:
                    display_log_content(subresult)

                elif verbosity > 1:
                    display_log_info(subresult)

                # Recursively show also all the results of subresult checks
                if isinstance(subresult, SubResult):
                    display_subresults(subresult.check)

        # Always show the result outcome
        display_outcome(result)

        # With verbosity increased to `-vvv` or more, display content of the main test log
        if verbosity > 2:
            display_log_content(result)

        # With verbosity increased to `-vv`, display the list of logs
        elif verbosity > 1:
            display_log_info(result)

        display_subresults(result.check)
        display_subresults(result.subresult)

    def go(self, *, logger: Optional[tmt.log.Logger] = None) -> None:
        """
        Discover available tests
        """

        super().go(logger=logger)
        # Show individual test results only in verbose mode
        if not self.verbosity_level:
            return

        if self.data.display_guest == 'always':
            display_guest = True

        elif self.data.display_guest == 'never':
            display_guest = False

        else:
            seen_guests = {result.guest.name for result in self.step.plan.execute.results()}

            display_guest = len(seen_guests) > 1

        for result in self.step.plan.execute.results():
            self.details(result, self.verbosity_level, display_guest)
