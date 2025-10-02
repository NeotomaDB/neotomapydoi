import psycopg2
import psycopg2.extras
from psycopg2.errors import TransactionTimeout, InvalidTextRepresentation, UndefinedFunction, InFailedSqlTransaction


def neo_creators(con: psycopg2.connect, self) -> list:
    """_Obtain a list of Neotoma dataset PIs for a dataset._

    Args:
        con (psycopg2.connect): _A valid psycopg connection to the Neotoma database._

    Returns:
        list: _A list of dataset PIs, including any external identifiers._
    """
    query = """
        SELECT DISTINCT cts.contactname AS name,
                        dspi.piorder,
                        -- cts.address AS affiliation,
                        jsonb_agg(DISTINCT 
                                jsonb_build_object('nameIdentifier', exct.identifier,
                                                   'nameIdentifierScheme', exdb.extdatabasename, 
                                                   'schemeUri', exdb.url)) AS "nameIdentifiers"
        FROM ndb.datasetpis AS dspi
        INNER JOIN ndb.contacts AS cts ON cts.contactid = dspi.contactid
        LEFT JOIN ndb.externalcontacts AS exct ON exct.contactid = cts.contactid
        LEFT JOIN ndb.externaldatabases AS exdb ON exdb.extdatabaseid = exct.extdatabaseid
        WHERE dspi.datasetid = %(datasetid)s
        GROUP BY cts.contactid, dspi.piorder
        ORDER BY dspi.piorder;
    """
    try:
        with con.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(query, {"datasetid": self.datasetid})
            response = cur.fetchall()
            creators = []
            if len(response) == 0:
                creators = [{"name": "None listed"}]
            for i in response:
                creator = dict(i)
                if creator.get("name") is None:
                    creator["name"] = "None listed"
                if not all(
                    [i.get("nameIdentifier") for i in creator.get("nameIdentifiers")]
                ):
                    _ = creator.pop("nameIdentifiers", None)
                creators.append({k:creator[k] for k in creator.keys() if k != 'piorder'})
    except TransactionTimeout as error:
        print("Database timeout error in neo_creators:")
        print(error)
    except (InvalidTextRepresentation, UndefinedFunction) as error:
        print(f"Dataset ID type is not integer. You passed {self.datasetid}:")
        print(error)
    except InFailedSqlTransaction as error:
        print("The database is in an invalid state. Rolling back operations:")
        con.rollback()
        print(error)
    return creators
