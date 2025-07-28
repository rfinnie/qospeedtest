# SPDX-PackageSummary: qospeedtest
# SPDX-FileCopyrightText: Copyright (C) 2019-2025 Ryan Finnie
# SPDX-License-Identifier: MPL-2.0

import unittest

import qospeedtest


class TestUtils(unittest.TestCase):
    def test_guid(self):
        self.assertEqual(len(qospeedtest.guid()), 36)
