# SPDX-PackageName: qospeedtest
# SPDX-PackageSupplier: Ryan Finnie <ryan@finnie.org>
# SPDX-PackageDownloadLocation: https://github.com/rfinnie/qospeedtest
# SPDX-FileCopyrightText: © 2019 Ryan Finnie <ryan@finnie.org>
# SPDX-License-Identifier: MPL-2.0

import os
import uuid

__version__ = "0.0.0"


class EWMA:
    _weight = 8.0
    _ewma_state = 0.0
    _initial = True

    def __init__(self, weight=8.0, state=0.0):
        self._weight = weight
        self._ewma_state = state

    def add(self, number):
        if self._initial:
            self._ewma_state = number * self._weight
            self._initial = False
        else:
            self._ewma_state += number - (self._ewma_state / self._weight)

    @property
    def average(self):
        return self._ewma_state / self._weight


# Randomized at module load time; we just need something semi-random.
# 1048573 is the first prime before 1024*1024; resists compression
# in transit.
RANDOM_POOL = os.urandom(1048573)


def SemiRandomGenerator(byte_count):
    while byte_count > 0:
        if byte_count < 1048573:
            yield RANDOM_POOL[:byte_count]
        else:
            yield RANDOM_POOL
        byte_count -= 1048573


def guid():
    return str(uuid.uuid4())


def si_number(n, binary=False, rollover=1.0, limit=0):
    class SINumber(float):
        prefix = ""

    prefixes = [
        ("k", "Ki"),
        ("M", "Mi"),
        ("G", "Gi"),
        ("T", "Ti"),
        ("P", "Pi"),
        ("E", "Ei"),
        ("Z", "Zi"),
        ("Y", "Yi"),
    ]
    divisor = 1024 if binary else 1000
    if limit == 0:
        limit = len(prefixes)

    count = 0
    p = ""
    for prefix in prefixes:
        if n < (divisor * rollover):
            break
        if count >= limit:
            break
        count += 1
        n = n / float(divisor)
        p = prefix[1] if binary else prefix[0]
    ret = SINumber(n)
    ret.prefix = p
    return ret
