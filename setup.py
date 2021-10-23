# SPDX-PackageSummary: Quick-and-Dirty OoklaServer-compatible Speed Test
# SPDX-FileCopyrightText: Copyright (C) 2019-2021 Ryan Finnie <ryan@finnie.org>
# SPDX-License-Identifier: MPL-2.0

import sys

from setuptools import setup

assert sys.version_info > (3, 4)


setup(
    name="qospeedtest",
    description="Quick-and-Dirty OoklaServer Speed Test",
    license="MPL-2.0",
    author="Ryan Finnie",
    author_email="ryan@finnie.org",
    package_dir={"": "lib"},
    install_requires=["requests", "PyYAML"],
    packages=["qospeedtest"],
    entry_points={
        "console_scripts": [
            "qospeedtest = qospeedtest.client:main",
            "qospeedtest-server = qospeedtest.server:main",
        ]
    },
)
