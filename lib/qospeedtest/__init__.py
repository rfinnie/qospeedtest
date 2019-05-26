import os


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
