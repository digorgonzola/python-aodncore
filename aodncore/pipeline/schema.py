"""This module holds schema definitions for validating the various :py:class:`dicts` which are used through the
pipeline, and also the helper functions necessary to validate an object against their respective schema.
"""

import jsonschema

__all__ = [
    'validate_check_params',
    'validate_custom_params',
    'validate_harvest_params',
    'validate_json_manifest',
    'validate_logging_config',
    'validate_pipeline_config',
    'validate_notify_params',
    'validate_resolve_params'
]

CHECK_PARAMS_SCHEMA = {
    'type': 'object',
    'properties': {
        'checks': {'type': 'array'},
        'criteria': {'type': 'string'},
        'skip_checks': {'type': 'array', 'items': {'type': 'string'}},
        'output_format': {'type': 'string'},
        'verbosity': {'type': 'integer'}
    },
    'additionalProperties': False
}

CUSTOM_PARAMS_SCHEMA = {
    'type': 'object'
}

HARVEST_PARAMS_SCHEMA = {
    'type': 'object',
    'properties': {
        'slice_size': {'type': 'integer'},
        'undo_previous_slices': {'type': 'boolean'},
        'ingest_type': {'type': 'string', 'enum': ['replace', 'truncate', 'append']},
        'db_schema': {'type': 'string'},
        'db_objects': {
            'type': 'array',
            'items': {'$ref': '#/definitions/db_object'},
        },
        'metadata_updates': {
            'type': 'array',
            'items': {'$ref': '#/definitions/metadata_update'},
        },
    },
    'additionalProperties': False,
    'definitions': {
        'db_object': {
            'type': 'object',
            'properties': {
                'name': {'type': 'string'},
                'type': {'type': 'string'},
                'dependencies': {'type': 'array', 'items': {'type': 'string'}}
            },
            'required': ['name', 'type'],
            'additionalProperties': False
        },
        'metadata_update': {
            'type': 'object',
            'properties': {
                'uuid': {'type': 'string'},
                'spatial': {
                    'type': 'object',
                    'properties': {
                        'table': {'type': 'string'},
                        'column': {'type': 'string'},
                        'resolution': {'type': 'integer'}
                    },
                    'required': ['table', 'column', 'resolution'],
                    'additionalProperties': False
                },
                'temporal': {
                    'type': 'object',
                    'properties': {
                        'table': {'type': 'string'},
                        'column': {'type': 'string'}
                    },
                    'required': ['table', 'column'],
                    'additionalProperties': False
                },
                'vertical': {
                    'type': 'object',
                    'properties': {
                        'table': {'type': 'string'},
                        'column': {'type': 'string'}
                    },
                    'required': ['table', 'column'],
                    'additionalProperties': False
                },
            },
            'required': ['uuid'],
            'additionalProperties': False
        }
    },
    'dependencies': {
        'db_schema': ['db_objects'],
        'db_objects': ['db_schema'],
        'metadata_updates': ['db_schema', 'db_objects']
    }
}

LOGGING_CONFIG_SCHEMA = {
    'type': 'object',
    'properties': {
        'version': {
            'type': 'integer',
            'enum': [1]
        },
        'filters': {'type': 'object'},
        'formatters': {'type': 'object'},
        'handlers': {'type': 'object'},
        'loggers': {'type': 'object'},
    },
    'required': ['version', 'formatters', 'handlers', 'loggers'],
    'additionalProperties': False
}

NOTIFY_PARAMS_SCHEMA = {
    'type': 'object',
    'properties': {
        'notify_owner_error': {'type': 'boolean'},
        'notify_owner_success': {'type': 'boolean'},
        'error_notify_list': {'$ref': '#/definitions/notifyList'},
        'owner_notify_list': {'$ref': '#/definitions/notifyList'},
        'success_notify_list': {'$ref': '#/definitions/notifyList'},
    },
    'additionalProperties': False,
    'definitions': {
        'notifyList': {
            'type': 'array',
            'items': {'type': 'string'}
        }
    }
}

PIPELINE_CONFIG_SCHEMA = {
    'type': 'object',
    'properties': {
        'global': {
            'type': 'object',
            'properties': {
                'admin_recipients': {
                    'type': 'array',
                    'items': {'type': 'string'}
                },
                'archive_uri': {'type': 'string'},
                'error_uri': {'type': 'string'},
                'opendap_root': {'type': 'string'},
                'processing_dir': {'type': 'string'},
                'tmp_dir': {'type': 'string'},
                'upload_uri': {'type': 'string'},
                'wfs_url': {'type': 'string'},
                'wfs_version': {'type': 'string'},
                'wip_dir': {'type': 'string'}
            },
            'required': ['admin_recipients', 'archive_uri', 'error_uri', 'processing_dir', 'upload_uri', 'wip_dir'],
            'additionalProperties': False
        },
        'logging': {
            'type': 'object',
            'properties': {
                'level': {'$ref': '#/definitions/loggingLevel'},
                'lib_level': {'$ref': '#/definitions/loggingLevel'},
                'pipeline_format': {'type': 'string'},
                'log_root': {'type': 'string'},
                'watchservice_format': {'type': 'string'}
            },
            'required': ['level', 'pipeline_format', 'log_root', 'watchservice_format'],
            'additionalProperties': False
        },
        'mail': {
            'type': 'object',
            'properties': {
                'from': {'type': 'string'},
                'subject': {'type': 'string'},
                'smtp_server': {'type': 'string'},
                'smtp_port': {'type': 'integer'},
                'smtp_user': {'type': 'string'},
                'smtp_pass': {'type': 'string'}
            },
            'required': ['from', 'subject', 'smtp_server', 'smtp_user', 'smtp_pass'],
            'additionalProperties': False
        },
        'pluggable': {
            'type': 'object',
            'properties': {
                'handlers_group': {'type': 'string'},
                'path_function_group': {'type': 'string'},
                'module_versions_group': {'type': 'string'}
            },
            'required': ['handlers_group', 'path_function_group', 'module_versions_group'],
            'additionalProperties': False
        },
        'talend': {
            'type': 'object',
            'properties': {
                'talend_log_dir': {'type': 'string'}
            },
            'required': ['talend_log_dir'],
            'additionalProperties': False
        },
        'harvester': {
            'type': 'object',
            'properties': {
                'config_dir': {'type': 'string'},
                'schema_base_dir': {'type': 'string'}
            },
            'required': ['config_dir', 'schema_base_dir'],
            'additionalProperties': False
        },
        'templating': {
            'type': 'object',
            'properties': {
                'template_package': {'type': 'string'},
                'html_notification_template': {'type': 'string'},
                'text_notification_template': {'type': 'string'},
            },
            'required': ['template_package', 'html_notification_template', 'text_notification_template'],
            'additionalProperties': False
        },
        'watch': {
            'type': 'object',
            'properties': {
                'incoming_dir': {'type': 'string'},
                'logger_name': {'type': 'string'},
                'task_namespace': {'type': 'string'}
            },
            'required': ['incoming_dir', 'logger_name', 'task_namespace'],
            'additionalProperties': False
        }
    },
    # TODO: add 'harvester' to the required list - once it has been added to the chef build
    'required': ['global', 'logging', 'mail', 'talend', 'templating', 'watch', 'harvester'],
    'additionalProperties': False,
    'definitions': {
        'loggingLevel': {
            'type': 'string',
            'enum': ['CRITICAL', 'FATAL', 'ERROR', 'WARNING', 'WARN', 'INFO', 'SYSINFO', 'DEBUG', 'NOTSET']
        }
    }
}

RESOLVE_PARAMS_SCHEMA = {
    'type': 'object',
    'properties': {
        'allow_delete_manifests': {'type': 'boolean'},
        'relative_path_root': {'type': 'string'}
    },
    'additionalProperties': False
}


JSON_MANIFEST_SCHEMA = {
    'type': 'object',
    'properties': {
        'files': {'type': 'array', 'items': {'$ref': '#/definitions/manifestEntry'}},
    },
    'additionalProperties': True,
    'definitions': {
        'manifestEntry': {
            'type': 'object',
            'properties': {
                'local_path': {'type': 'string'},
                'dest_path': {'type': 'string'}
            },
            'required': ['local_path'],
            'additionalProperties': False
        }
    }
}


def validate_check_params(check_params):
    jsonschema.validate(check_params, CHECK_PARAMS_SCHEMA)


def validate_custom_params(check_params):
    jsonschema.validate(check_params, CUSTOM_PARAMS_SCHEMA)


def validate_harvest_params(harvest_params):
    jsonschema.validate(harvest_params, HARVEST_PARAMS_SCHEMA)


def validate_logging_config(logging_config):
    jsonschema.validate(logging_config, LOGGING_CONFIG_SCHEMA)


def validate_notify_params(notify_params):
    jsonschema.validate(notify_params, NOTIFY_PARAMS_SCHEMA)


def validate_pipeline_config(pipeline_config):
    jsonschema.validate(pipeline_config, PIPELINE_CONFIG_SCHEMA)


def validate_resolve_params(resolve_params):
    jsonschema.validate(resolve_params, RESOLVE_PARAMS_SCHEMA)


def validate_json_manifest(json_manifest):
    jsonschema.validate(json_manifest, JSON_MANIFEST_SCHEMA)
