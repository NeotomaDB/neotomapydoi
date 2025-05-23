import psycopg2
import psycopg2.extras


def neo_identifier(con: psycopg2.connect, self) -> object:
    """_Return the dataset identifier (DOI)_

    Args:
        con (psycopg2.connect): _A valid connection the the Neotoma database._

    Returns:
        object: _An object with the dataset DOI._
    """    
    query = """
        SELECT doi as identifier,
        'DOI' as "identifierType"
        FROM doi.doimeta
        WHERE datasetid = %(datasetid)s
        LIMIT 1;
    """

    with con.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(query, {"datasetid": self.datasetid})
        response = cur.fetchone()
        if response:
            doi = dict(response)
        else:
            doi = {}
    return doi
