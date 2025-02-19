"""This module provides the step runner classes for the :ref:`check` step.

Checking is performed by a :py:class:`BaseCheckRunner` class, which is used to determine whether a file conforms to a
"check", the definition of which is contained in the specific class. A check typically involves reading a file, and
testing whether the file conforms to some arbitrary criteria.

The most common use of this step is to test for compliance using the IOOS Compliance Checker.
"""

import abc
import itertools
import os
# from collections import namedtuple
# import json

import tableschema
import yaml

from compliance_checker.runner import ComplianceChecker, CheckSuite

from .basestep import BaseStepRunner
from ..common import CheckResult, PipelineFileCheckType, validate_checktype
from ..exceptions import ComplianceCheckFailedError, InvalidCheckSuiteError, InvalidCheckTypeError, MissingFileError
from ..files import PipelineFileCollection
from ...util import (format_exception, is_netcdf_file, is_nonempty_file, CaptureStdIO, find_file,
                     get_tableschema_descriptor)

__all__ = [
    'get_check_runner',
    'get_child_check_runner',
    'CheckRunnerAdapter',
    'ComplianceCheckerCheckRunner',
    'FormatCheckRunner',
    'NonEmptyCheckRunner',
    'TableSchemaCheckRunner'
]


def get_check_runner(config, logger, check_params=None):
    return CheckRunnerAdapter(config, logger, check_params)


def get_child_check_runner(check_type, config, logger, check_params=None):
    """Factory function to return appropriate checker class based on check type value

    :param check_type: :py:class:`PipelineFileCheckType` enum member
    :param check_params: dict of parameters to pass to :py:class:`BaseCheckRunner` class for runtime configuration
    :param config: :py:class:`LazyConfigManager` instance
    :param logger: :py:class:`Logger` instance
    :return: :py:class:`BaseCheckRunner` sub-class
    """
    validate_checktype(check_type)

    if check_type is PipelineFileCheckType.NC_COMPLIANCE_CHECK:
        return ComplianceCheckerCheckRunner(config, logger, check_params)
    elif check_type is PipelineFileCheckType.FORMAT_CHECK:
        return FormatCheckRunner(config, logger)
    elif check_type is PipelineFileCheckType.NONEMPTY_CHECK:
        return NonEmptyCheckRunner(config, logger)
    elif check_type is PipelineFileCheckType.TABLE_SCHEMA_CHECK:
        return TableSchemaCheckRunner(config, logger)
    else:
        raise InvalidCheckTypeError("invalid check type '{check_type}'".format(check_type=check_type))


class BaseCheckRunner(BaseStepRunner, metaclass=abc.ABCMeta):
    """A CheckRunner is responsible for performing checks on a given collection of files.
    
    The 'run' method is supplied with a PipelineFileCollection object and performs arbitrary checks against the files, 
    with the only expectation being that it must update the PipelineFile elements' check_result property with a
    CheckResult instance.
    
    The 'compliant' attribute of the CheckResult instance is a simple boolean determining whether the file
    is compliant with the given arbitrary check, and 'compliance_log' must be a collection (e.g. list, tuple) containing
    arbitrary information about why the file is considered non-compliant. Note: 'compliance_log' is a collection type in
    order to correlate it to 'lines in a log file', and typically should return an empty tuple if the file is compliant.
    """

    @abc.abstractmethod
    def run(self, pipeline_files):
        pass


class CheckRunnerAdapter(BaseCheckRunner):
    def __init__(self, config, logger, check_params=None):
        super().__init__(config, logger)

        if check_params is None:
            check_params = {}

        self.check_params = check_params

    def run(self, pipeline_files):
        check_types = {t.check_type for t in pipeline_files if
                       t.check_type in PipelineFileCheckType.all_checkable_types}

        for check_type in check_types:
            check_list = pipeline_files.filter_by_attribute_id('check_type', check_type)
            check_runner = get_child_check_runner(check_type, self._config, self._logger, self.check_params)
            self._logger.sysinfo("get_child_check_runner -> {check_runner}".format(check_runner=check_runner))
            check_runner.run(check_list)

        failed_files = PipelineFileCollection((f for f in pipeline_files
                                              if f.check_type in check_types and not f.check_result.compliant),
                                              validate_unique=False)

        for f in failed_files:
            self._logger.error(u"log for failed file '{name}'{sep}{log}".format(name=f.name, sep=os.linesep,
                                                                                log=os.linesep.join(
                                                                                    f.check_result.log)))
        if failed_files:
            failed_list = failed_files.get_attribute_list('name')
            raise ComplianceCheckFailedError(
                "the following files failed the check step: {failed_list}".format(failed_list=failed_list))


class ComplianceCheckerCheckRunner(BaseCheckRunner):
    def __init__(self, config, logger, check_params=None):
        super().__init__(config, logger)
        if check_params is None:
            check_params = {}

        self.checks = check_params.get('checks', None)
        self.verbosity = check_params.get('verbosity', 0)
        self.criteria = check_params.get('criteria', 'normal')
        self.skip_checks = check_params.get('skip_checks', None)
        self.output_format = check_params.get('output_format', 'text')

        if not self.checks:
            raise InvalidCheckSuiteError('compliance check requested but no check suite specified')

        CheckSuite.load_all_available_checkers()

        # workaround a possible bug in the compliance checker where invalid check suites are ignored
        available_checkers = set(CheckSuite.checkers)
        these_checkers = set(self.checks)
        if not these_checkers.issubset(available_checkers):
            invalid_suites = list(these_checkers.difference(available_checkers))
            raise InvalidCheckSuiteError(
                'invalid compliance check suites: {invalid_suites}'.format(invalid_suites=invalid_suites))

    def __repr__(self):
        return "{self.__class__.__name__}(checks={self.checks})".format(self=self)

    def run(self, pipeline_files):
        if self.skip_checks:
            self._logger.info("compliance checks will skip {self.skip_checks}".format(self=self))

        for pipeline_file in pipeline_files:
            self._logger.info("checking compliance of '{pipeline_file.src_path}' "
                              "against {self.checks}".format(pipeline_file=pipeline_file, self=self))

            # first check that it is a valid NetCDF format file
            if not is_netcdf_file(pipeline_file.src_path):
                compliance_log = ("invalid NetCDF file",)
                pipeline_file.check_result = CheckResult(False, compliance_log)
                continue

            check_results = []
            for check in self.checks:
                check_results.append(self._run_check(pipeline_file.src_path, check))

            compliant = all(r.compliant for r in check_results)
            compliance_log = list(itertools.chain.from_iterable(r.log for r in check_results))
            errors = any(r.errors for r in check_results)

            pipeline_file.check_result = CheckResult(compliant, compliance_log, errors)

    def _run_check(self, file_path, check):
        """
        Run a single check suite on the given file.

        :param str file_path: Full path to the file
        :param str check: Name of check suite to run.
        :return: :py:class:`aodncore.pipeline.CheckResult` object
        """
        stdout_log = []
        stderr_log = []
        try:
            with CaptureStdIO() as (stdout_log, stderr_log):
                compliant, errors = ComplianceChecker.run_checker(file_path, [check],
                                                                  self.verbosity, self.criteria, self.skip_checks,
                                                                  output_format=self.output_format)
        except Exception as e:  # pragma: no cover
            errors = True
            stderr_log.extend([
                'WARNING: compliance checks did not complete due to error. {e}'.format(e=format_exception(e))
            ])

        # if any exceptions during checking, assume file is non-compliant
        if errors:
            compliant = False

        compliance_log = []
        if not compliant:
            compliance_log.extend(stdout_log)
            compliance_log.extend(stderr_log)

        return CheckResult(compliant, compliance_log, errors)


class FormatCheckRunner(BaseCheckRunner):
    def run(self, pipeline_files):
        for pipeline_file in pipeline_files:
            self._logger.info(
                "checking '{pipeline_file.src_path}' is a valid '{pipeline_file.file_type.name}' file".format(
                    pipeline_file=pipeline_file))
            compliant = pipeline_file.file_type.validator(pipeline_file.src_path)
            compliance_log = () if compliant else (
                "invalid format: did not validate as type: {pipeline_file.file_type.name}".format(
                    pipeline_file=pipeline_file),)
            pipeline_file.check_result = CheckResult(compliant, compliance_log)


class NonEmptyCheckRunner(BaseCheckRunner):
    def run(self, pipeline_files):
        for pipeline_file in pipeline_files:
            self._logger.info(
                "checking that '{pipeline_file.src_path}' is not empty".format(pipeline_file=pipeline_file))
            compliant = is_nonempty_file(pipeline_file.src_path)
            compliance_log = () if compliant else ('empty file',)
            pipeline_file.check_result = CheckResult(compliant, compliance_log)


class TableSchemaCheckRunner(BaseCheckRunner):
    def __init__(self, config, logger):
        super().__init__(config, logger)
        self.compliance_log = []
        self.compliant = True
        self.schema_base_path = self._config.pipeline_config['harvester']['schema_base_dir']

    def _dict_to_str(self, _dict):
        _str = ''
        for k, v in _dict.items():
            _str += ' {}: {},'.format(k, v)
        return _str[:-1]

    def _exc_handler(self, exc, row_number=None, row_data=None, error_data=None):
        error = "Exception: {}\nRow Data: {}\nError Data: {}\n".format(str(exc),
                                                                       self._dict_to_str(row_data),
                                                                       self._dict_to_str(error_data))
        self.compliance_log.append(error)

    def _reset_compliance(self):
        self.compliance_log = []
        self.compliant = True

    def validate(self, path):
        self._reset_compliance()
        search_string = os.path.splitext(os.path.basename(path))[0]
        fn = find_file(self.schema_base_path, '(.*){}(.*).yaml'.format(search_string))
        if fn:
            with open(fn) as stream:
                schema = get_tableschema_descriptor(yaml.safe_load(stream), 'schema')
                table = tableschema.Table(path, schema)
                _ = [r for r in table.iter(exc_handler=self._exc_handler)]
            if len(self.compliance_log) > 0:
                self.compliant = False
        else:
            self.compliance_log = ("could not find schema definition matching: {search_string}".format(
                    search_string=search_string),)
            self.compliant = False

    def run(self, pipeline_files):
        for pipeline_file in pipeline_files:
            self._logger.info(
                "checking that '{pipeline_file.src_path}' is valid".format(pipeline_file=pipeline_file))
            self.validate(pipeline_file.src_path)
            pipeline_file.check_result = CheckResult(self.compliant, self.compliance_log)
