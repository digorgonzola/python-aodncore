"""This module provides the step runner classes for the "harvest" step, which is a sub-step of the :ref:`publish` step.

Harvesting is performed by a :py:class:`BaseHarvesterRunner` class.

This currently supports "talend" and "csv" as harvesting tools.

The "talend" harvester runner runs Talend instances as subprocesses, whereas the "csv" harvester runner calls the core
"DatabaseInteractions" harvester class directly.
"""

import abc
import itertools
import os
import re
import json
from collections import OrderedDict
from tempfile import NamedTemporaryFile
from pathlib import Path

from .basestep import BaseStepRunner
from ..exceptions import (InvalidHarvesterError, UnmappedFilesError, MissingConfigParameterError, InvalidConfigError,
                          MissingConfigFileError, UnexpectedCsvFilesError, InvalidSQLConnectionError,
                          InvalidSQLTransactionError)
from ..files import PipelineFileCollection, validate_pipelinefilecollection
from ..geonetwork import Geonetwork, GeonetworkMetadataHandler
from ..db import DatabaseInteractions
from ...util import (LoggingContext, SystemProcess, TemporaryDirectory, merge_dicts, mkdir_p, validate_string,
                     validate_type)

__all__ = [
    'create_input_file_list',
    'create_symlink',
    'executor_conversion',
    'get_harvester_runner',
    'HarvesterMap',
    'TalendHarvesterRunner',
    'CsvHarvesterRunner',
    'TriggerEvent',
    'validate_harvestermap',
    'validate_harvester_mapping',
    'validate_triggerevent'
]


def get_harvester_runner(harvester_name, store_runner, harvest_params, tmp_base_dir, config, logger):
    """Factory function to return appropriate harvester class

    :param harvester_name: harvester name used to retrieve :py:class:`BaseHarvesterRunner` class
    :param store_runner: :py:class:`BaseStoreRunner` instance to use for uploads
    :param harvest_params: dict of parameters to pass to :py:class:`BaseCheckRunner` class for runtime configuration
    :param tmp_base_dir: base temporary directory
    :param config: :py:class:`LazyConfigManager` instance
    :param logger: :py:class:`Logger` instance
    :return: :py:class:`BaseHarvesterRunner` class
    """

    if harvester_name == 'talend':
        return TalendHarvesterRunner(store_runner, harvest_params, tmp_base_dir, config, logger)
    elif harvester_name == 'csv':
        return CsvHarvesterRunner(store_runner, harvest_params, config, logger)
    else:
        raise InvalidHarvesterError("invalid harvester '{name}'".format(name=harvester_name))


class HarvesterMap(object):
    __slots__ = ['_map']

    def __init__(self):
        self._map = OrderedDict()

    def __iter__(self):
        return iter(self._map.items())

    @property
    def all_events(self):
        """Get a flattened list of all events from all harvesters.

        :return: list of all :py:class:`TriggerEvent` instances from all harvesters
        """
        return itertools.chain.from_iterable(self._map.values())

    @property
    def all_pipeline_files(self):
        """Get a flattened collection containing all :py:class:`PipelineFile` instances from all harvester events

        :return: :py:class:`PipelineFileCollection` containing all :py:class:`PipelineFile` objects in map
        """
        all_pipeline_files = PipelineFileCollection()
        for event in self.all_events:
            all_pipeline_files.update(event.matched_files, overwrite=True)
        return all_pipeline_files

    @property
    def map(self):
        return self._map

    def add_event(self, harvester, event):
        """Add a :py:class:`TriggerEvent` to this map, under the given harvester

        :param harvester: harvester name
        :param event: :py:class:`TriggerEvent` object
        :return: None
        """
        validate_string(harvester)
        validate_triggerevent(event)

        try:
            self.map[harvester].append(event)
        except KeyError:
            self.map[harvester] = [event]

    def merge(self, other):
        """Merge another :py:class:`HarvesterMap` instance into this one

        :param other: other :py:class:`HarvesterMap` instance
        :return: None
        """
        validate_harvestermap(other)
        self._map = merge_dicts(self._map, other.map)

    def set_pipelinefile_bool_attribute(self, attribute, value):
        """Set a boolean attribute on all :py:class:`PipelineFile` instances in all events

        :param attribute: attribute to set
        :param value: value to set
        :return: None
        """
        self.all_pipeline_files.set_bool_attribute(attribute, value)

    def is_collection_superset(self, pipeline_files):
        """Determine whether all :py:class:`PipelineFile` instances in the given :py:class:`PipelineFileCollection` are
        present in this map

        :param pipeline_files: :py:class:`PipelineFileCollection` for comparison
        :return: True if all files in the collection are in one or more events in this map
        """
        validate_pipelinefilecollection(pipeline_files)

        return pipeline_files.issubset(self.all_pipeline_files)


class TriggerEvent(object):
    __slots__ = ['_matched_files', '_extra_params']

    def __init__(self, matched_files, extra_params=None):
        validate_pipelinefilecollection(matched_files)

        self._matched_files = matched_files
        self._extra_params = extra_params

    @property
    def matched_files(self):
        return self._matched_files

    @property
    def extra_params(self):
        return self._extra_params


def create_input_file_list(talend_base_dir, matched_file_list):
    with NamedTemporaryFile(mode='w', prefix='file_list', suffix='.txt', dir=talend_base_dir, delete=False) as f:
        f.writelines("{line}{sep}".format(line=l, sep=os.linesep) for l in matched_file_list)

    return f.name


def create_symlink(base_dir, src_path, dest_path):
    symlink_target = os.path.join(base_dir, dest_path)
    index_dir = os.path.dirname(symlink_target)
    mkdir_p(index_dir)
    os.symlink(src_path, symlink_target)


def executor_conversion(executor):
    python_formatted_exec = re.sub('=%{', '={', executor)
    return python_formatted_exec


def validate_harvester_mapping(pipeline_files, harvester_map):
    """Validate whether all files in the given :py:class:`PipelineFileCollection` are present at least once in the
    given :py:class:`HarvesterMap`

    :param pipeline_files: :py:class:`PipelineFileCollection` instance
    :param harvester_map: :py:class:`HarvesterMap` instance
    :return: None
    """
    validate_pipelinefilecollection(pipeline_files)
    validate_harvestermap(harvester_map)

    if not harvester_map.is_collection_superset(pipeline_files):
        unmapped_files = [m.src_path for m in pipeline_files.difference(harvester_map.all_pipeline_files)]
        raise UnmappedFilesError(
            "no matching harvester(s) found for: {unmapped_files}".format(unmapped_files=unmapped_files))


class BaseHarvesterRunner(BaseStepRunner, metaclass=abc.ABCMeta):
    """Base class for HarvesterRunner classes
    """

    @abc.abstractmethod
    def run(self, pipeline_files):
        pass


class TalendHarvesterRunner(BaseHarvesterRunner):
    """:py:class:`BaseHarvesterRunner` implementation to execute Talend harvesters
    """

    def __init__(self, storage_broker, harvest_params, tmp_base_dir, config, logger, deletion=False):
        super().__init__(config, logger)
        if harvest_params is None:
            harvest_params = {}

        self.deletion = deletion
        self.slice_size = harvest_params.get('slice_size', 2048)
        self.undo_previous_slices = harvest_params.get('undo_previous_slices', True)
        self.params = harvest_params
        self.tmp_base_dir = tmp_base_dir
        self.storage_broker = storage_broker
        self.harvested_file_map = HarvesterMap()

    def run(self, pipeline_files):
        """The entry point to the ported talend trigger code to execute the harvester(s) for each file

        :return: None
        """
        validate_pipelinefilecollection(pipeline_files)

        deletions = pipeline_files.filter_by_bool_attribute('pending_harvest_early_deletion')
        additions = pipeline_files.filter_by_bool_attribute('pending_harvest_addition')
        late_deletions = pipeline_files.filter_by_bool_attribute('pending_harvest_late_deletion')

        self._logger.sysinfo("harvesting slice size: {slice_size}".format(slice_size=self.slice_size))
        deletion_slices = deletions.get_slices(self.slice_size)
        addition_slices = additions.get_slices(self.slice_size)
        late_deletions_slices = late_deletions.get_slices(self.slice_size)

        for file_slice in deletion_slices:
            deletion_map = self.match_harvester_to_files(file_slice)
            validate_harvester_mapping(file_slice, deletion_map)
            self.run_deletions(deletion_map, self.tmp_base_dir)

        for file_slice in addition_slices:
            addition_map = self.match_harvester_to_files(file_slice)
            validate_harvester_mapping(file_slice, addition_map)
            self.run_additions(addition_map, self.tmp_base_dir)

        for file_slice in late_deletions_slices:
            late_deletion_map = self.match_harvester_to_files(file_slice)
            validate_harvester_mapping(file_slice, late_deletion_map)
            self.run_deletions(late_deletion_map, self.tmp_base_dir)

    def match_harvester_to_files(self, pipeline_files):
        validate_pipelinefilecollection(pipeline_files)

        harvester_map = HarvesterMap()

        for harvester, config_item in self._config.trigger_config.items():
            for event in config_item['events']:
                extra_params = None
                matched_files = PipelineFileCollection()

                for config_type, value in event.items():
                    if config_type == 'regex':
                        for regex in value:
                            matched_files_for_regex = pipeline_files.filter_by_attribute_regexes('dest_path', regex)
                            if matched_files_for_regex:
                                for mf in matched_files_for_regex:
                                    self._logger.sysinfo(
                                        "harvester '{harvester}' matched file: {mf.src_path}".format(
                                            harvester=harvester, mf=mf))

                                matched_files.update(matched_files_for_regex, overwrite=True)
                    elif config_type == 'extra_params':
                        extra_params = value

                if matched_files:
                    event_obj = TriggerEvent(matched_files, extra_params)
                    harvester_map.add_event(harvester, event_obj)

        return harvester_map

    def undo_processed_files(self, undo_map):
        validate_harvestermap(undo_map)

        undo_map.set_pipelinefile_bool_attribute('should_undo', True)
        self.run_undo_deletions(undo_map)

    def execute_talend(self, executor, pipeline_files, talend_base_dir, success_attribute='is_harvested'):
        validate_pipelinefilecollection(pipeline_files)

        matched_file_list = [mf.dest_path for mf in pipeline_files]
        input_file_list = create_input_file_list(talend_base_dir, matched_file_list)

        converted_exec = executor_conversion(executor)

        talend_exec = converted_exec.format(base=talend_base_dir, file_list=input_file_list,
                                            log_dir=self._config.pipeline_config['talend']['talend_log_dir'])

        self._logger.sysinfo("executing {talend_exec}".format(talend_exec=talend_exec))

        p = SystemProcess(talend_exec, shell=True)

        self._logger.info('--- START TALEND OUTPUT ---')
        with LoggingContext(self._logger, format_='%(message)s'):
            try:
                p.execute()
            except Exception:
                self._logger.error(p.stdout_text)
                raise
            else:
                pipeline_files.set_bool_attribute(success_attribute, True)
                self._logger.info(p.stdout_text)
            finally:
                self._logger.info('--- END TALEND OUTPUT ---')

    def run_deletions(self, harvester_map, tmp_base_dir):
        """Function to un-harvest and delete files using the appropriate file upload runner.

        Operates in newly created temporary directory as talend requires a non-existent file to perform un-harvesting

        :param harvester_map: :py:class:`HarvesterMap` containing the events to be deleted
        :param tmp_base_dir: temporary directory base for talend operation
        """
        validate_harvestermap(harvester_map)

        for harvester, events in harvester_map:
            self._logger.info("running deletions for harvester '{harvester}'".format(harvester=harvester))

            for event in events:
                with TemporaryDirectory(prefix='talend_base', dir=tmp_base_dir) as talend_base_dir:
                    harvester_command = self._config.trigger_config[harvester]['exec']
                    if event.extra_params:
                        harvester_command = "{harvester_command} {extra_params}".format(
                            harvester_command=harvester_command, extra_params=event.extra_params)

                    self.execute_talend(harvester_command, event.matched_files, talend_base_dir)

                files_to_delete = event.matched_files.filter_by_bool_attribute('pending_store_deletion')
                if files_to_delete:
                    self.storage_broker.delete(pipeline_files=files_to_delete)

    def run_undo_deletions(self, harvester_map):
        """Function to un-harvest and undo stored files as appropriate in the case of errors.

        Operates in newly created temporary directory as talend requires a non-existent file to perform "unharvesting"

        :param harvester_map: :py:class:`HarvesterMap` containing the events to be undone
        """
        validate_harvestermap(harvester_map)

        for harvester, events in harvester_map:
            self._logger.info("running undo deletions for harvester '{harvester}'".format(harvester=harvester))

            for event in events:
                with TemporaryDirectory(prefix='talend_base', dir=self.tmp_base_dir) as talend_base_dir:
                    harvester_command = self._config.trigger_config[harvester]['exec']
                    if event.extra_params:
                        harvester_command = "{harvester_command} {extra_params}".format(
                            harvester_command=harvester_command, extra_params=event.extra_params)

                    self.execute_talend(harvester_command, event.matched_files, talend_base_dir,
                                        success_attribute='is_harvest_undone')

                files_to_delete = event.matched_files.filter_by_bool_attributes_and('pending_undo', 'is_stored')
                if files_to_delete:
                    self.storage_broker.delete(pipeline_files=files_to_delete, is_stored_attr='is_upload_undone')

    def run_additions(self, harvester_map, tmp_base_dir):
        """Function to harvest and upload files using the appropriate file upload runner.

        Operates in newly created temporary directory and creates symlink between source and destination file. Talend
        will then operate on the destination file (symlink).

        :param harvester_map: :py:class:`HarvesterMap` containing the events to be added
        :param tmp_base_dir: temporary directory base for talend operation
        """
        validate_harvestermap(harvester_map)

        for harvester, events in harvester_map:
            self._logger.info("running additions for harvester '{harvester}'".format(harvester=harvester))

            for event in events:
                with TemporaryDirectory(prefix='talend_base', dir=tmp_base_dir) as talend_base_dir:
                    for pf in event.matched_files:
                        create_symlink(talend_base_dir, pf.src_path, pf.dest_path)

                    harvester_command = self._config.trigger_config[harvester]['exec']
                    if event.extra_params:
                        harvester_command = "{harvester_command} {extra_params}".format(
                            harvester_command=harvester_command, extra_params=event.extra_params)

                    try:
                        self.execute_talend(harvester_command, event.matched_files, talend_base_dir)
                    except Exception:
                        # add current event to undo_map
                        undo_map = HarvesterMap()
                        undo_map.add_event(harvester, event)

                        # if 'undo_previous_slices' is enabled, combine the map of previously harvested events into the
                        # undo_map in order to undo all previously successful events
                        if self.undo_previous_slices:
                            undo_map.merge(self.harvested_file_map)

                        self.undo_processed_files(undo_map)
                        raise

                    # on success, register this event in the instance 'harvested_file_map' attribute
                    self.harvested_file_map.add_event(harvester, event)

                files_to_upload = event.matched_files.filter_by_bool_attribute('pending_store_addition')
                if files_to_upload:
                    self.storage_broker.upload(pipeline_files=files_to_upload)


class CsvHarvesterRunner(BaseHarvesterRunner):
    """:py:class:`BaseHarvesterRunner` implementation to load csv pipeline files to the database."""

    def __init__(self, storage_broker, harvest_params, config, logger):
        super().__init__(config, logger)
        if harvest_params is None:
            harvest_params = {}

        self.params = harvest_params
        self.storage_broker = storage_broker
        self.config = self._config
        self.logger = self._logger
        self.db_objects_raw = self.params.get('db_objects')
        self.db_objects = list(map(self.build_dependency_tree, self.db_objects_raw)) if self.db_objects_raw else None
        self.unexpected_pipeline_files = []

    def run(self, pipeline_files):
        """The entry point to the generic csv harvester

        :return: None
        """
        validate_pipelinefilecollection(pipeline_files)

        if self.db_objects:
            for pf in pipeline_files:
                self.build_runsheet(pf)
            if len(self.unexpected_pipeline_files) > 0:
                raise UnexpectedCsvFilesError('No db_objects match these pipeline files: {}'
                                              .format(self.unexpected_pipeline_files))
            runsheet = list(filter(lambda x: x.get('include'), self.db_objects))
        else:
            raise MissingConfigParameterError('Generic CSV Harvester requires that the '
                                              'harvest_params["db_objects"] attribute be set')

        with DatabaseInteractions(config=self.get_config_file('database.json'),
                                  schema_base_path=self._config.pipeline_config['harvester']['schema_base_dir'],
                                  logger=self.logger) as conn:
            process = self.get_process_sequence(conn)
            for step in runsheet:
                self._logger.info('Executing steps for {}'.format(step['name']))
                for task in process:
                    getattr(conn, task)(step)

        files_to_upload = pipeline_files.filter_by_bool_attribute('pending_store_addition')
        if files_to_upload:
            self.storage_broker.upload(pipeline_files=files_to_upload)

        pipeline_files.set_bool_attribute('is_harvested', True)

        metadata = self.params.get('metadata_updates')
        if metadata and len(metadata) > 0:
            try:
                gn_config = self.get_config_file('metadata.json')
                gn = Geonetwork(
                    base_url=gn_config['metadata_url'],
                    username=gn_config['metadata_username'],
                    password=gn_config['metadata_password']
                )
                with DatabaseInteractions(config=self.get_config_file('database.json'),
                                          schema_base_path=self._config.pipeline_config['harvester']['schema_base_dir'],
                                          logger=self.logger) as conn:
                    for m in metadata:
                        if 'spatial' in m:
                            m['spatial']['db_schema'] = self.params['db_schema']
                        handler = GeonetworkMetadataHandler(conn, gn, m, self.logger)
                        handler.run()
            except (InvalidSQLConnectionError, InvalidSQLTransactionError):
                raise
            except Exception as e:
                self._logger.warning(e)

    def get_config_file(self, filename):
        """Function to return database connection object for schema

        :return: dict containing database connection parameters.
        """
        harvest_config = self._config.pipeline_config['harvester']['config_dir']
        fn = os.path.join(harvest_config, self.params['db_schema'], filename)
        try:
            with open(fn) as json_file:
                return json.load(json_file)
        except FileNotFoundError as e:
            raise MissingConfigFileError(e)

    def get_process_sequence(self, conn):
        """Function to return the database transaction process sequence based in ingest_type.

        :param conn: instance of DatabaseInteractions().
        :return: dict containing process sequence.
        """
        processes = {
            "replace": [
                "drop_object",
                "create_table_from_yaml_file",
                "load_data_from_csv",
                "execute_sql_file",
            ],
            "truncate": [
                "truncate_table",
                "load_data_from_csv",
                "refresh_materialized_view",
            ],
            "append": [
                "load_data_from_csv",
                "refresh_materialized_view",
            ],
        }
        # compare_schemas not yet implemented
        ingest_type = self.params.get('ingest_type', 'replace') if conn.compare_schemas() else 'replace'
        process = processes.get(ingest_type)
        if process:
            self._logger.info("Using process sequence `{}`".format(ingest_type))
            return processes[ingest_type]
        else:
            raise InvalidConfigError('No implementation for {} ingest_type'.format(ingest_type))

    def build_dependency_tree(self, obj):
        """Update one item from the db_objects list to include indirect dependencies.
        (i.e. dependencies of dependencies, etc...).

        :param obj: dict describing a database object (from db_objects config)
        :return: copy of obj with updated dependencies
        """
        def get_parent_dependencies(deps):
            if deps:
                for d in deps:
                    parent = next(filter(lambda x: x['name'] == d, self.db_objects_raw))
                    deps = deps + get_parent_dependencies(parent.get('dependencies', []))
            return deps

        dependencies = get_parent_dependencies(obj.get('dependencies'))
        obj_out = dict(obj)  # make a writeable copy
        if dependencies:
            obj_out['dependencies'] = list(set(dependencies))
        return obj_out

    def build_runsheet(self, pf):
        """Function to generate a runsheet for the harvest process.

        :return: bool
        """
        found = False
        for obj in self.db_objects:
            if Path(pf.local_path).stem.lower() == obj['name'].lower() and obj['type'] == "table":
                obj['include'] = True
                obj['local_path'] = pf.local_path
                found = True
            elif Path(pf.local_path).stem.lower() in obj.get('dependencies', []):
                obj['include'] = True
        if not found:
            self.unexpected_pipeline_files.append(pf.local_path)
        return True


validate_triggerevent = validate_type(TriggerEvent)
validate_harvestermap = validate_type(HarvesterMap)
