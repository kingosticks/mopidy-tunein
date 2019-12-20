import unittest

from mopidy_tunein import Extension


class ExtensionTest(unittest.TestCase):
    def test_get_default_config(self):
        ext = Extension()

        config = ext.get_default_config()

        self.assertIn("[tunein]", config)
        self.assertIn("enabled = true", config)

    def test_get_config_schema(self):
        ext = Extension()

        schema = ext.get_config_schema()

        self.assertIn("timeout", schema)
        self.assertIn("filter", schema)
