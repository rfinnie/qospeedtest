import unittest

import qospeedtest


class TestUtils(unittest.TestCase):
    def test_guid(self):
        self.assertEqual(len(qospeedtest.guid()), 36)
