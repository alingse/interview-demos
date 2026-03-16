"""Helper functions."""

from typing import Iterator, List, TypeVar

T = TypeVar("T")


def batched(iterable: List[T], batch_size: int) -> Iterator[List[T]]:
    """Split list into batches.

    Args:
        iterable: List to split
        batch_size: Size of each batch

    Yields:
        Batches of the specified size
    """
    for i in range(0, len(iterable), batch_size):
        yield iterable[i:i + batch_size]
