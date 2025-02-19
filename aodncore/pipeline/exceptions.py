"""This module provides custom exceptions used throughout the :py:mod:`aodncore.pipeline` package.
"""

from ..common.exceptions import AodnBaseError

__all__ = [
    'PipelineProcessingError',
    'PipelineSystemError',
    'ComplianceCheckFailedError',
    'AttributeNotSetError',
    'AttributeValidationError',
    'DuplicatePipelineFileError',
    'HandlerAlreadyRunError',
    'InvalidCheckSuiteError',
    'InvalidFileContentError',
    'InvalidFileFormatError',
    'InvalidFileNameError',
    'InvalidCheckTypeError',
    'InvalidConfigError',
    'InvalidPathFunctionError',
    'InvalidHandlerError',
    'InvalidHarvesterError',
    'InvalidHarvestMapError',
    'InvalidInputFileError',
    'InvalidRecipientError',
    'InvalidStoreUrlError',
    'MissingConfigParameterError',
    'MissingFileError',
    'MissingConfigFileError',
    'NotificationFailedError',
    'StorageBrokerError',
    'UnmappedFilesError',
    'UnmatchedFilesError',
    'UnexpectedCsvFilesError',
    'InvalidSchemaError',
    'InvalidSQLConnectionError',
    'InvalidSQLTransactionError',
    'GeonetworkConnectionError',
    'GeonetworkRequestError'
]


class PipelineProcessingError(AodnBaseError):
    """Base class for all exceptions which indicate that there was a problem processing the file as opposed to an
    internal configuration or environmental error. Handler classes should typically raise exceptions based on this
    exception to signal non-compliance of the file or some other *user correctable* problem.
    """
    pass


class PipelineSystemError(AodnBaseError):
    """Base class for all exceptions *not* related to file processing and which would typically *not* be suitable to
    return to an end user
    """
    pass


# Processing errors

class ComplianceCheckFailedError(PipelineProcessingError):
    pass


class InvalidFileNameError(PipelineProcessingError):
    pass


class InvalidFileContentError(PipelineProcessingError):
    pass


class InvalidFileFormatError(PipelineProcessingError):
    pass


# System errors

class AttributeNotSetError(PipelineSystemError):
    pass


class AttributeValidationError(PipelineSystemError):
    pass


class DuplicatePipelineFileError(PipelineSystemError):
    pass


class HandlerAlreadyRunError(PipelineSystemError):
    pass


class InvalidCheckSuiteError(PipelineSystemError):
    pass


class InvalidCheckTypeError(PipelineSystemError):
    pass


class InvalidConfigError(PipelineSystemError):
    pass


class InvalidHandlerError(PipelineSystemError):
    pass


class InvalidHarvesterError(PipelineSystemError):
    pass


class InvalidHarvestMapError(PipelineSystemError):
    pass


class InvalidInputFileError(PipelineSystemError):
    pass


class InvalidPathFunctionError(PipelineSystemError):
    pass


class InvalidRecipientError(PipelineSystemError):
    pass


class InvalidStoreUrlError(PipelineSystemError):
    pass


class MissingConfigParameterError(PipelineSystemError):
    pass


class MissingFileError(PipelineSystemError):
    pass


class MissingConfigFileError(PipelineSystemError):
    pass


class NotificationFailedError(PipelineSystemError):
    pass


class StorageBrokerError(PipelineSystemError):
    pass


class UnmappedFilesError(PipelineSystemError):
    pass


class UnmatchedFilesError(PipelineSystemError):
    pass


class UnexpectedCsvFilesError(PipelineSystemError):
    pass


class InvalidSchemaError(PipelineSystemError):
    pass


class InvalidSQLConnectionError(PipelineSystemError):
    pass


class InvalidSQLTransactionError(PipelineSystemError):
    pass


class GeonetworkConnectionError(PipelineSystemError):
    pass


class GeonetworkRequestError(PipelineSystemError):
    pass
