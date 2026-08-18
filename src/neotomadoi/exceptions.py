class DatasetNotReady(Exception):
    """_The dataset cannot be minted yet, through no fault of the system._

    Raised for conditions that are expected to resolve on their own — most
    commonly a dataset with no submission date, meaning its owner has not
    submitted it yet. Callers should skip these datasets and carry on rather
    than treating them as failures, so that one not-yet-ready record does not
    block minting for everything else in the same run.
    """
