# SPDX-PackageName: qospeedtest
# SPDX-PackageSupplier: Ryan Finnie <ryan@finnie.org>
# SPDX-PackageDownloadLocation: https://github.com/rfinnie/qospeedtest
# SPDX-FileCopyrightText: © 2019 Ryan Finnie <ryan@finnie.org>
# SPDX-License-Identifier: MPL-2.0

import unittest

import qospeedtest


class TestUtils(unittest.TestCase):
    def test_guid(self):
        self.assertEqual(len(qospeedtest.guid()), 36)
