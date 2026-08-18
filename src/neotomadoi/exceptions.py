# N818 asks for an `Error` suffix, which is the right default for exceptions that
# signal something went wrong. This one deliberately does not: it reports a normal,
# temporary state, in the same spirit as `StopIteration` or `GeneratorExit`. Naming
# it `...Error` would invite exactly the treatment we are trying to avoid.
class DatasetNotReady(Exception):  # noqa: N818
    """_The dataset cannot be minted yet, through no fault of the system._

    Raised for conditions that are expected to resolve on their own — most
    commonly a dataset with no submission date, meaning its owner has not
    submitted it yet. Callers should skip these datasets and carry on rather
    than treating them as failures, so that one not-yet-ready record does not
    block minting for everything else in the same run.
    """
