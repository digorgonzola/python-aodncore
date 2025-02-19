import os
from uuid import uuid4

from aodncore.pipeline import PipelineFilePublishType
from aodncore.pipeline.exceptions import DuplicatePipelineFileError, InvalidFileFormatError
from aodncore.pipeline.steps.resolve import (get_resolve_runner, DeleteManifestResolveRunner, DirManifestResolveRunner,
                                             GzipFileResolveRunner, JsonManifestResolveRunner, MapManifestResolveRunner,
                                             RsyncManifestResolveRunner, SimpleManifestResolveRunner,
                                             SingleFileResolveRunner, ZipFileResolveRunner)
from aodncore.testlib import BaseTestCase
from test_aodncore import TESTDATA_DIR

BAD_NC = os.path.join(TESTDATA_DIR, 'bad.nc')
BAD_GZ = os.path.join(TESTDATA_DIR, 'bad.nc.gz')
BAD_ZIP = os.path.join(TESTDATA_DIR, 'bad.zip')
GOOD_NC = os.path.join(TESTDATA_DIR, 'good.nc')
GOOD_GZ = os.path.join(TESTDATA_DIR, 'good.nc.gz')
GOOD_ZIP = os.path.join(TESTDATA_DIR, 'good.zip')
RECURSIVE_ZIP = os.path.join(TESTDATA_DIR, 'recursive.zip')
INVALID_FILE = os.path.join(TESTDATA_DIR, 'invalid.png')
NOT_NETCDF_NC_FILE = os.path.join(TESTDATA_DIR, 'not_a_netcdf_file.nc')
TEST_MANIFEST_NC = os.path.join(TESTDATA_DIR, 'test_manifest.nc')
TEST_DIR_MANIFEST_NC = os.path.join(TESTDATA_DIR, 'layer1', 'layer2', 'test_manifest.nc')
DIR_MANIFEST = os.path.join(TESTDATA_DIR, 'test.dir_manifest')
JSON_MANIFEST = os.path.join(TESTDATA_DIR, 'test.json_manifest')
MAP_MANIFEST = os.path.join(TESTDATA_DIR, 'test.map_manifest')
MAP_MANIFEST_MISSINGFIELD = os.path.join(TESTDATA_DIR, 'test_missing_field.map_manifest')
MAP_MANIFEST_DUPLICATEFIELD = os.path.join(TESTDATA_DIR, 'test_duplicate_field.map_manifest')
RSYNC_MANIFEST = os.path.join(TESTDATA_DIR, 'test.rsync_manifest')
RSYNC_MANIFEST_DUPLICATE = os.path.join(TESTDATA_DIR, 'test_duplicate.rsync_manifest')
SIMPLE_MANIFEST = os.path.join(TESTDATA_DIR, 'test.manifest')
DELETE_MANIFEST = os.path.join(TESTDATA_DIR, 'test.delete_manifest')
DELETE_MANIFEST_DUPLICATE = os.path.join(TESTDATA_DIR, 'test_duplicate.delete_manifest')
DELETE_MANIFEST_INVALID = os.path.join(TESTDATA_DIR, 'test_invalid.delete_manifest')


class MockConfig(object):
    pipeline_config = {
        'global': {
            'wip_dir': TESTDATA_DIR
        }
    }


MOCK_CONFIG = MockConfig


class TestPipelineStepsResolve(BaseTestCase):
    def test_get_resolve_runner(self):
        json_manifest_resolve_runner = get_resolve_runner(JSON_MANIFEST, self.temp_dir, MOCK_CONFIG, self.test_logger)
        self.assertIsInstance(json_manifest_resolve_runner, JsonManifestResolveRunner)

        map_manifest_resolve_runner = get_resolve_runner(MAP_MANIFEST, self.temp_dir, MOCK_CONFIG, self.test_logger)
        self.assertIsInstance(map_manifest_resolve_runner, MapManifestResolveRunner)

        rsync_manifest_resolve_runner = get_resolve_runner(RSYNC_MANIFEST, self.temp_dir, MOCK_CONFIG, self.test_logger)
        self.assertIsInstance(rsync_manifest_resolve_runner, RsyncManifestResolveRunner)

        simple_manifest_resolve_runner = get_resolve_runner(SIMPLE_MANIFEST, self.temp_dir, MOCK_CONFIG,
                                                            self.test_logger)
        self.assertIsInstance(simple_manifest_resolve_runner, SimpleManifestResolveRunner)

        delete_manifest_resolve_runner = get_resolve_runner(DELETE_MANIFEST, self.temp_dir, MOCK_CONFIG,
                                                            self.test_logger, {'allow_delete_manifests': True})
        self.assertIsInstance(delete_manifest_resolve_runner, DeleteManifestResolveRunner)

        # delete manifests will not be resolved unless 'allow_delete_manifests' is present in resolve_params
        with self.assertRaises(InvalidFileFormatError):
            _ = get_resolve_runner(DELETE_MANIFEST, self.temp_dir, MOCK_CONFIG, self.test_logger)

        nc_resolve_runner = get_resolve_runner(GOOD_NC, self.temp_dir, MOCK_CONFIG, self.test_logger)
        self.assertIsInstance(nc_resolve_runner, SingleFileResolveRunner)

        unknown_file_extension = get_resolve_runner(str(uuid4()), self.temp_dir, MOCK_CONFIG,
                                                    self.test_logger)
        self.assertIsInstance(unknown_file_extension, SingleFileResolveRunner)

        gzip_resolve_runner = get_resolve_runner(GOOD_GZ, self.temp_dir, MOCK_CONFIG, self.test_logger)
        self.assertIsInstance(gzip_resolve_runner, GzipFileResolveRunner)

        zip_resolve_runner = get_resolve_runner(GOOD_ZIP, self.temp_dir, MOCK_CONFIG, self.test_logger)
        self.assertIsInstance(zip_resolve_runner, ZipFileResolveRunner)


class TestDirManifestResolveRunner(BaseTestCase):
    def test_dir_manifest_resolve_runner(self):
        dir_manifest_resolve_runner = DirManifestResolveRunner(DIR_MANIFEST, self.temp_dir, MOCK_CONFIG,
                                                               self.test_logger)
        collection = dir_manifest_resolve_runner.run()

        self.assertEqual(collection[0].src_path, os.path.join(MOCK_CONFIG.pipeline_config['global']['wip_dir'],
                                                              'layer1', 'layer2',
                                                              os.path.basename(TEST_DIR_MANIFEST_NC)))
        self.assertEqual(collection[1].src_path, os.path.join(MOCK_CONFIG.pipeline_config['global']['wip_dir'],
                                                              os.path.basename(NOT_NETCDF_NC_FILE)))


class TestJsonManifestResolveRunner(BaseTestCase):
    def test_json_manifest_resolve_runner_valid(self):
        json_manifest_resolve_runner = JsonManifestResolveRunner(JSON_MANIFEST, self.temp_dir, MOCK_CONFIG,
                                                                 self.test_logger)
        collection = json_manifest_resolve_runner.run()

        self.assertEqual(collection[0].src_path, os.path.join(MOCK_CONFIG.pipeline_config['global']['wip_dir'],
                                                              os.path.basename(GOOD_NC)))
        self.assertEqual(collection[0].dest_path, None)

        self.assertEqual(collection[1].src_path, os.path.join(MOCK_CONFIG.pipeline_config['global']['wip_dir'],
                                                              os.path.basename(BAD_NC)))
        self.assertEqual(collection[1].dest_path, 'UNITTEST/NOT/A/REAL/PATH')

    def test_json_manifest_resolve_runner_invalid(self):
        json_manifest_resolve_runner = JsonManifestResolveRunner(GOOD_NC, self.temp_dir, MOCK_CONFIG,
                                                                 self.test_logger)
        with self.assertRaises(InvalidFileFormatError):
            _ = json_manifest_resolve_runner.run()


class TestMapManifestResolveRunner(BaseTestCase):
    def test_map_manifest_resolve_runner(self):
        map_manifest_resolve_runner = MapManifestResolveRunner(MAP_MANIFEST, self.temp_dir, MOCK_CONFIG,
                                                               self.test_logger)

        self.assertTrue(map_manifest_resolve_runner.schema.valid)

        collection = map_manifest_resolve_runner.run()

        self.assertEqual(collection[0].src_path, os.path.join(MOCK_CONFIG.pipeline_config['global']['wip_dir'],
                                                              os.path.basename(TEST_MANIFEST_NC)))

        self.assertEqual(collection[0].dest_path, 'UNITTEST/NOT/A/REAL/PATH')

    def test_missing_field_map_manifest_resolve_runner(self):
        map_manifest_resolve_runner = MapManifestResolveRunner(MAP_MANIFEST_MISSINGFIELD, self.temp_dir, MOCK_CONFIG,
                                                               self.test_logger)
        with self.assertRaisesRegex(InvalidFileFormatError,
                                    r'There are 1 cast errors \(see exception.errors\) for row "2": Field "dest_path" has constraint "required" which is not satisfied for value "None".*'
                                    r'There are 1 cast errors \(see exception.errors\) for row "3": Field "local_path" has constraint "required" which is not satisfied for value "None"'):
            _ = map_manifest_resolve_runner.run()

    def test_duplicate_field_map_manifest_resolve_runner(self):
        map_manifest_resolve_runner = MapManifestResolveRunner(MAP_MANIFEST_DUPLICATEFIELD, self.temp_dir, MOCK_CONFIG,
                                                               self.test_logger)
        with self.assertRaisesRegex(InvalidFileFormatError,
                                    r'[\'Field\(s\) "dest_path" duplicates in row "2" for values (\'UNITTEST/NOT/A/REAL/PATH\',): '
                                    r'\', \'Field\(s\) "local_path" duplicates in row "3" for values (\'good.nc\',): \']'):
            _ = map_manifest_resolve_runner.run()


class TestRsyncManifestResolveRunner(BaseTestCase):
    def test_rsync_manifest_resolve_runner(self):
        rsync_manifest_resolve_runner = RsyncManifestResolveRunner(RSYNC_MANIFEST, self.temp_dir, MOCK_CONFIG,
                                                                   self.test_logger)
        collection = rsync_manifest_resolve_runner.run()

        self.assertEqual(len(collection), 2)
        self.assertFalse(collection[0].is_deletion)
        self.assertTrue(collection[1].is_deletion)

        self.assertEqual(collection[0].src_path, os.path.join(MOCK_CONFIG.pipeline_config['global']['wip_dir'],
                                                              os.path.basename(TEST_MANIFEST_NC)))

        self.assertEqual(collection[1].src_path, os.path.join(TESTDATA_DIR, 'aoml/1900728/1900728_Rtraj.nc'))

    def test_rsync_manifest_resolve_runner_duplicate(self):
        rsync_manifest_resolve_runner = RsyncManifestResolveRunner(RSYNC_MANIFEST_DUPLICATE, self.temp_dir, MOCK_CONFIG,
                                                                   self.test_logger)

        with self.assertRaises(DuplicatePipelineFileError):
            _ = rsync_manifest_resolve_runner.run()


class TestSimpleManifestResolveRunner(BaseTestCase):
    def test_simple_manifest_resolve_runner(self):
        simple_manifest_resolve_runner = SimpleManifestResolveRunner(SIMPLE_MANIFEST, self.temp_dir, MOCK_CONFIG,
                                                                     self.test_logger)
        collection = simple_manifest_resolve_runner.run()

        self.assertEqual(collection[0].src_path, os.path.join(MOCK_CONFIG.pipeline_config['global']['wip_dir'],
                                                              os.path.basename(TEST_MANIFEST_NC)))


class TestDeleteManifestResolveRunner(BaseTestCase):
    def test_delete_manifest_resolve_runner(self):
        delete_manifest_resolve_runner = DeleteManifestResolveRunner(DELETE_MANIFEST, self.temp_dir, MOCK_CONFIG,
                                                                     self.test_logger)

        self.assertTrue(delete_manifest_resolve_runner.schema.valid)

        collection = delete_manifest_resolve_runner.run()

        self.assertEqual(collection[0].dest_path, 'UNITTEST/NOT/A/REAL/PATH')
        self.assertTrue(collection[0].is_deletion)
        self.assertIs(collection[0].publish_type, PipelineFilePublishType.UNSET)

        self.assertEqual(collection[1].dest_path, 'UNITTEST/NOT/A/REAL/PATH/EITHER')
        self.assertTrue(collection[1].is_deletion)
        self.assertIs(collection[1].publish_type, PipelineFilePublishType.UNSET)

        self.assertEqual(collection[2].dest_path, 'UNITTEST/NOT/A/REAL/PATH/EITHER/AGAIN')
        self.assertTrue(collection[2].is_deletion)
        self.assertIs(collection[2].publish_type, PipelineFilePublishType.UNSET)

    def test_duplicate_delete_manifest_resolve_runner(self):
        delete_manifest_resolve_runner = DeleteManifestResolveRunner(DELETE_MANIFEST_DUPLICATE, self.temp_dir,
                                                                     MOCK_CONFIG, self.test_logger)
        with self.assertRaisesRegex(InvalidFileFormatError,
                                    r'Field\(s\) "dest_path" duplicates in row "3".*Field\(s\) "dest_path" duplicates in row "5"'):
            _ = delete_manifest_resolve_runner.run()

    def test_invalid_delete_manifest_resolve_runner(self):
        delete_manifest_resolve_runner = DeleteManifestResolveRunner(DELETE_MANIFEST_INVALID, self.temp_dir,
                                                                     MOCK_CONFIG, self.test_logger)
        with self.assertRaisesRegex(InvalidFileFormatError,
                                    r'[\'Row length 2 doesn\'t match fields count 1 for row "2": \', \'Row length 2 doesn\'t match fields count 1 for row "3": \']'):
            _ = delete_manifest_resolve_runner.run()


class TestSingleFileResolveRunner(BaseTestCase):
    def test_single_file_resolve_runner(self):
        single_file_resolve_runner = SingleFileResolveRunner(GOOD_NC, self.temp_dir, MOCK_CONFIG, self.test_logger)
        collection = single_file_resolve_runner.run()

        good_nc = os.path.join(self.temp_dir, os.path.basename(GOOD_NC))

        self.assertEqual(len(collection), 1)
        self.assertTrue(os.path.exists(good_nc))
        self.assertEqual(collection[0].src_path, good_nc)


class TestGzipFileResolveRunner(BaseTestCase):
    def test_gzip_file_resolve_runner(self):
        collection_dir = os.path.join(self.temp_dir, 'collection')
        os.mkdir(collection_dir)

        gzip_file_resolve_runner = GzipFileResolveRunner(GOOD_GZ, collection_dir, MOCK_CONFIG, self.test_logger)
        collection = gzip_file_resolve_runner.run()

        good_nc = os.path.join(collection_dir, os.path.basename(GOOD_NC))

        self.assertEqual(len(collection), 1)
        self.assertEqual(collection[0].src_path, good_nc)
        self.assertTrue(os.path.exists(good_nc))

    def test_not_gzip_file(self):
        collection_dir = os.path.join(self.temp_dir, 'collection')
        gzip_file_resolve_runner = GzipFileResolveRunner(self.temp_nc_file, collection_dir, MOCK_CONFIG,
                                                         self.test_logger)
        with self.assertRaises(InvalidFileFormatError):
            _ = gzip_file_resolve_runner.run()


class TestZipFileResolveRunner(BaseTestCase):
    def test_zip_file_resolve_runner(self):
        collection_dir = os.path.join(self.temp_dir, 'collection')
        zip_file_resolve_runner = ZipFileResolveRunner(BAD_ZIP, collection_dir, MOCK_CONFIG, self.test_logger)
        collection = zip_file_resolve_runner.run()

        good_nc = os.path.join(collection_dir, os.path.basename(GOOD_NC))
        bad_nc = os.path.join(collection_dir, os.path.basename(BAD_NC))

        self.assertEqual(len(collection), 2)

        self.assertEqual(collection[0].src_path, bad_nc)
        self.assertTrue(os.path.exists(bad_nc))

        self.assertEqual(collection[1].src_path, good_nc)
        self.assertTrue(os.path.exists(good_nc))

    def test_recursive_zip(self):
        collection_dir = os.path.join(self.temp_dir, 'collection')
        zip_file_resolve_runner = ZipFileResolveRunner(RECURSIVE_ZIP, collection_dir, MOCK_CONFIG, self.test_logger)
        collection = zip_file_resolve_runner.run()

        good_nc = os.path.join(collection_dir, 'layer1', os.path.basename(GOOD_NC))
        bad_nc = os.path.join(collection_dir, 'layer1/layer2', os.path.basename(BAD_NC))

        self.assertEqual(len(collection), 2)

        self.assertEqual(collection[0].src_path, good_nc)
        self.assertTrue(os.path.exists(good_nc))

        self.assertEqual(collection[1].src_path, bad_nc)
        self.assertTrue(os.path.exists(bad_nc))

    def test_not_zip_file(self):
        collection_dir = os.path.join(self.temp_dir, 'collection')
        zip_file_resolve_runner = ZipFileResolveRunner(self.temp_nc_file, collection_dir, MOCK_CONFIG, self.test_logger)
        with self.assertRaises(InvalidFileFormatError):
            _ = zip_file_resolve_runner.run()
