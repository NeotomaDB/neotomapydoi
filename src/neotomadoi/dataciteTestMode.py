from enum import Enum


class dataciteTestMode(Enum):
    """_A class to manage connections to DataCite, connecting to either the production API service or the sandbox._

    Examples:
    >>> test = dataciteTestMode.test
    >>> test.value
    'https://api.test.datacite.org/dois/'
    >>> prod = dataciteTestMode.prod
    >>> prod
    <dataciteTestMode.prod: 'https://api.datacite.org/dois/'>

    Args:
        Enum (_string_): _An enumerated object, with either `test`or `prod` modes._
    """

    test = "https://api.test.datacite.org/dois/"
    prod = "https://api.datacite.org/dois/"
