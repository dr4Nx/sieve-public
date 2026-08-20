"""File sampling helpers (supports .gz logs)."""

import gzip
import random
from typing import Iterable, List, Tuple

from .logging_utils import Logger


def iter_lines(path: str) -> Iterable[str]:
    if path.endswith(".gz"):
        with gzip.open(path, "rt", errors="ignore") as fh:
            for line in fh:
                yield line
    else:
        with open(path, "r", errors="ignore") as fh:
            for line in fh:
                yield line


def reservoir_sample(path: str, k: int, log: Logger, seed: int | None = None) -> Tuple[List[str], int]:
    """Reservoir-sample up to k lines. Returns (sample, total_lines).

    If seed is provided, sampling is deterministic; the same seed and the
    same input file always produce the same sample. This lets us keep the
    sampled context fixed across reruns when we want to isolate model variance.
    """
    log.info(f"Sampling up to {k} random lines from: {path}")
    rng = random.Random(seed) if seed is not None else random
    sample: List[str] = []
    n = 0
    for line in iter_lines(path):
        n += 1
        if n <= k:
            sample.append(line)
        else:
            j = rng.randint(1, n)
            if j <= k:
                sample[j - 1] = line
        if n % 250000 == 0:
            log.debug(f"...streamed {n:,} lines so far")
    log.info(f"Finished sampling: saw {n:,} total lines; kept {len(sample)}")
    return sample, n
