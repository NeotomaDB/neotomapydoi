import psycopg2
import psycopg2.extras


def neo_description(con: psycopg2.connect, self) -> object:
    """_Return a formatted description string for the dataset to be used in the DOI metadata._

    Args:
        con (psycopg2.connect): _A valid connection to the Neotoma database._

    Returns:
        object: _An object with the description and description type._
    """    
    query = """
        SELECT st.sitename || ' ' || dst.datasettype || ' dataset' AS title
        FROM
        ndb.datasets AS ds
        INNER JOIN ndb.datasettypes AS dst ON dst.datasettypeid = ds.datasettypeid
        INNER JOIN ndb.collectionunits AS cu ON cu.collectionunitid = ds.collectionunitid
        INNER JOIN ndb.sites AS st ON st.siteid = cu.siteid
        WHERE ds.datasetid = %(datasetid)s; 
    """
    with con.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(query, {"datasetid": self.datasetid})
        response = cur.fetchone()
        string = (
            f"Raw data for the {response[0]} submitted to the Neotoma Paleoecology Database. Data is available through the landing page in JSON format. "
            "The landing page referenced by the DOI also contains links to publications and a map-based viewer for the dataset. "
            "The Neotoma Paleoecology Database maintains a homepage at https://www.neotomadb.org."
        )
        description = [
            {"descriptionType": "Abstract", "description": string, "lang": "EN"}
        ]
    return description
