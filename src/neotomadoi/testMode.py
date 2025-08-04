from enum import Enum

class testMode(Enum):
    """_A class to manage connections to Neotoma and DataCite_

    Examples:
    >>> test = testMode.test
    >>> test.value
    'https://api.test.datacite.org/dois/'
    >>> prod = testMode.prod
    >>> prod
    <testMode.prod: 'https://api.datacite.org/dois/'>

    Args:
        Enum (_string_): _An enumerated object, with either `test`or `prod` modes._
    """    
    test = "https://api.test.datacite.org/dois/"
    prod = "https://api.datacite.org/dois/"

