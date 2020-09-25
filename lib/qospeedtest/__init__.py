import os
import uuid


__version__ = "0.0.0"


class EWMA:
    _weight = 8.0
    _ewma_state = 0

    def __init__(self, weight=8.0):
        self._weight = weight

    def add(self, number):
        if self._ewma_state == 0:
            self._ewma_state = number * self._weight
        else:
            self._ewma_state += number - (self._ewma_state / self._weight)

    @property
    def average(self):
        return self._ewma_state / self._weight


class SemiRandomGenerator(object):
    # Randomized at module load time; we just need something semi-random
    random_1k = os.urandom(1024)

    def __init__(self, byte_count):
        self.byte_count = byte_count
        self.left = self.byte_count

    def __iter__(self):
        return self

    def __next__(self):
        return self.next()

    def next(self):
        if self.left <= 0:
            self.left = self.byte_count
            raise StopIteration()
        to_return = self.left if self.left < 1024 else 1024
        self.left -= to_return
        if to_return < 1024:
            return self.random_1k[:to_return]
        else:
            return self.random_1k


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
