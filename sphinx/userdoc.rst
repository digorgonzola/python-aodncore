Overview
--------

The ``aodncore.pipeline`` package provides the base class for each pipeline handler,
:py:class:`aodncore.pipeline.HandlerBase`. This is the starting point for any new handler development, as
it contains all of the core functionality of each handler, which is then available to the child class via class
inheritance.


State machine / handler steps
-----------------------------

In order to provide consistency and structure to the handler, the pipeline is broken into a series of ordered "steps",
with each performing a distinct function in the processing of the input file. The "machine" defines a series of states,
and also controls/enforces the transitions between states.

For example, since it makes no sense to check a collection of files before the collection exists, the state machine
enforces that the ``check`` step may *only* be entered into from the ``resolve`` step.

Similarly, the ``publish`` step cannot ever be entered into other than from the ``process`` step, which means that the
step can safely make several assumptions about the overall state of the handler when it does get executed. For example,
it can automatically assume with a 100% guarantee that the ``initalise``, ``resolve``, ``preprocess``, ``check`` and
``process`` step have all been run in that order with no errors, allowing it to focus purely on the core concern of the
step; publishing files, and nothing more.

The ordered steps are as follows:

initialise
~~~~~~~~~~

Responsible for general setup of handler class and performing initial sanity checking of the input file and parameters

#. validation of parameters
#. validation of input file (e.g. the file exists, is accessible, is of an allowed type etc.)
#. setup temporary directories

resolve
~~~~~~~

Responsible for preparing the central file collection of the handler instance, including handling input files which
represent multiple files (e.g. ZIP and manifest files). The file collection is used to hold the processing state of all
"known" files for the duration of the handler. After this step, there is no need to consider the original source format
of the input file, as this step "resolves" the file into a generic collection for further processing.

#. prepare the "file collection" used by all subsequent steps by placing files into a temporary directory and
   creating an entry in the handlers "file_collection" attribute, which is a special type of set
   (PipelineFileCollection object) optimised for dealing with pipeline files (PipelineFile objects)

    #. if single file, copy to temporary directory and add to file collection
    #. if ZIP file, extract files into temporary directory and add them to the file collection
    #. if manifest file, add files "in place" to the file collection

#. update files to be included/excluded from processing based on regex filter (if defined in parameter)

preprocess
~~~~~~~~~~

Special override method (see below for details)

check
~~~~~

Responsible for checking the validity and/or compliance of files in the collection.

#.  determine the type of check to be performed based on the handler parameters and file type

    #. if NetCDF and compliance checks defined in parameters, check against listed check suites
    #. if NetCDF and no compliance checks defined, validate NetCDF format
    #. if known file type, validate file format (e.g. if .pdf extension, validate PDF format)  # TODO
    #. if unknown file type, check that the file is not empty

process
~~~~~~~

Special override method (see below for details)

publish
~~~~~~~

Responsible for publishing the file to external repositories. This is a composite step, and will perform the following
actions only on files in the collection which have been flagged for that action (as determined by the publish_type
attribute of the files).

#. determine files flagged as needing to be archived, and upload to 'archive' location
#. determine files flagged as needing to be harvested, match and execute Talend (or CSV) harvester(s) for files
#. determine files flagged as needing to be uploaded or deleted, and perform the necessary storage operation

.. note:: upload/delete operations are collectively referred to in the handler and supporting code as "store" operations

postprocess
~~~~~~~~~~~

Special override method (see below for details)

notify
~~~~~~

Responsible for notifying the uploader and/or the pipeline 'owner' of the result of the handler attempt.

#. determine the recipients, based on notification parameters and handler result
#. send notifications

Customising handler behaviour
-----------------------------

Methods
~~~~~~~

The methods in the HandlerBase (and therefore any subclasses inheriting from it) can be separated into two categories:

*Internal / non-public methods*

These methods must *not* be overridden by child handlers, or the handler behaviour will be compromised. In following the
Python convention, these methods begin with a single underscore (_) character. Note that this is a convention, and
therefore it is possible to manipulate or even override them, however it is mandatory that the conventions are followed
to maintain the integrity of the handler execution.

In addition to any methods starting with one or more underscores, the ``run`` method is also a special case, which must
*not* be overridden or extended, as this is the entry point for handler execution. This is implemented and run
separately from the class initialiser (```__init__```) such that the handler instance can be created, and have it's
contents inspected (e.g. by unit tests) before and after actually executing the file processing code of the handler.

*Public methods*

There are three special methods defined which are *intended* to be overridden by subclasses in order to provide a
handler author with the ability to call code in order to modify the behaviour of the handler during it's execution.

The special methods are: ``preprocess``, ``process`` and ``postprocess``

These methods are deliberately left empty (i.e. they are there but don't do anything) in the base class, so it is purely
optional whether the subclass implements these.

The only difference between these methods is *when* they are called by the handler state machine. Refer to the above
section for further details about where they appear in the steps order.

Attributes
----------

A handler instance contains a number of attributes which control or modify the behaviour of the handler. The attributes
are typically set from the **params** key of the watch configuration, or from the ``__init__`` method of a handler
subclass (e.g. when writing tests).

Class parameters
~~~~~~~~~~~~~~~~

The following class parameters are also assigned to attributes of the same name, as a convenience.

For example, a handler instantiated with any of these class parameters may also access them from the class instance as
follows::

    from aodncore.pipeline import HandlerBase
    from aodncore.pipeline.config import CONFIG


    class MyHandler(HandlerBase):
        def print_upload_path(self):
            # Note: when accessing attributes from within the class itself, the usual Python 'self.attr'
            # convention applies to access the *current* instance
            print(self.upload_path)


    h = MyHandler('/path/to/input/file.nc', config=CONFIG, upload_path='/original/incoming/path/file.nc')
    h.input_file
    '/path/to/input/file.nc'
    h.upload_path
    '/original/incoming/path/file.nc'
    h.config
    <aodncore.pipeline.configlib.LazyConfigManager object at 0x7f22230c5990>

    h.print_upload_path()
    /original/incoming/path/file.nc



