import psycopg2
import psycopg2.extras
from psycopg2.errors import TransactionTimeout, InvalidTextRepresentation, UndefinedFunction, InFailedSqlTransaction


def neo_dates(con: psycopg2.connect, self) -> object:
    """_Return critical dates associated with the dataset record._

    Args:
        con (psycopg2.connect): _A valid connection to the Neotoma database._

    Returns:
        object: _A object listing each date type (Submitted, Updated, etc.) and the relevant date._
    """    
    query = """
        WITH creation AS (
            SELECT MIN(ds.submissiondate)::date as date, 'Submitted'::text
            FROM ndb.datasetsubmissions AS ds
            WHERE ds.datasetid = %(datasetid)s
        ),
        resub AS (
            SELECT ds.submissiondate as date, 'Updated'::text
            FROM ndb.datasetsubmissions AS ds
            WHERE ds.datasetid = %(datasetid)s
            ORDER BY ds.submissiondate
            OFFSET 1
        ),
        issued AS (
            SELECT dsdoi.recdatecreated as date, 'Issued'::text
            FROM ndb.datasetdoi AS dsdoi
            WHERE dsdoi.datasetid = %(datasetid)s
            ORDER BY dsdoi.recdatecreated
            LIMIT 1
        )
        SELECT DISTINCT *
        FROM (
            (SELECT * FROM creation)
        UNION ALL
        (SELECT * FROM resub)
        UNION ALL
        (SELECT * FROM issued)) AS dates
        WHERE date is not NULL;
    """
    try:
        with con.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(query, {"datasetid": self.datasetid})
            response = cur.fetchall()
            dates = []
            for i in response:
                dates.append(dict(i))
            date_out = []
            for i in dates:
                date_out.append(
                    {"dateType": i.get("text"), "date": i.get("date").strftime("%Y-%m-%d")}
                )
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
    return date_out
