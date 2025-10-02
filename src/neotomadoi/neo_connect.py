import psycopg2
from dotenv import dotenv_values
from json import loads


def neo_connect(tank: bool = False) -> psycopg2.connect:
    """_Connect to the Neotoma Database_

    Args:
        tank (bool): _Are we connecting to the Neotoma Holding Tank or the Production database?_

    Returns:
        psycopg2.connect: _A valid connection the the Neotoma Database server_
    """
    secrets = dotenv_values()
    if tank:
        CONN_STRING = loads(secrets["DBAUTH_TEST"])
    else:
        CONN_STRING = loads(secrets["DBAUTH"])
    con = psycopg2.connect(**CONN_STRING, connect_timeout=5)
    return con
