from enum import Enum


class databaseMode(Enum):
    """_A class to manage connections to the Neotoma Database, connecting to either the production database or the holding tank._

    Examples:
    >>> test = databaseMode.tank
    >>> test.value
    'neotomatank'
    >>> prod = databaseMode.prod
    >>> prod
    <databaseMode.prod: 'neotoma'>

    Args:
        Enum (_string_): _An enumerated object, with either `tank`or `prod` modes._
    """
    tank = "neotomatank"
    prod = "neotoma"
