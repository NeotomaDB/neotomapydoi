"""Fetch Metadata from a valid Neotoma Database Connection

The DataCite API and metadata schema requires certain data elements from
Neotoma. These fetch methods (prepended by `neo_*()`) use calls to Neotoma
or other data resources, such as OpenAlex, to build the metadata elements.

Each function is intended to return a particular metadata element. In this way
we can maintain the capacity to add or modify the kinds of metadata we contribute
to DataCite without having to modify the core code. We can also improve
query methods or other tools without impacting other methods."""

import json
from json import dumps
from sys import getsizeof

import psycopg2
import psycopg2.extras
from psycopg2.errors import (
    InFailedSqlTransaction,
    InvalidTextRepresentation,
    TransactionTimeout,
    UndefinedFunction,
)
from pyalex import Works, config
from shapely import wkt

config.max_retries = 0
config.retry_backoff_factor = 0.1
config.retry_http_codes = [429, 500, 503]
config.email = "goring@wisc.edu"


def neo_subjects(con: psycopg2.connect, self) -> object:
    """_Obtain valid subjects to associate with Neotoma datasets._

    Args:
        con (psycopg2.connect): _A valid Neotoma database connection._

    Returns:
        object: _A list of subjects with associated subject schemes._
    """
    pubs = []
    topics = []
    subjects = []
    pub_query = """
        SELECT DISTINCT TRIM(pub.doi) as doi
        FROM ndb.datasetpublications AS dsp
        INNER JOIN ndb.publications AS pub ON dsp.publicationid = pub.publicationid
        WHERE dsp.datasetid = %(datasetid)s
        AND pub.doi IS NOT NULL;"""
    with con.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(pub_query, {"datasetid": self.datasetid})
        response = cur.fetchall()
        for i in response:
            pubs.append(dict(i))
    if len(pubs) > 0:
        for i in pubs:
            try:
                open_record = Works()["https://doi.org/" + i.get("doi")]
                topics = [j for j in open_record.get("topics") if j.get("score") > 0.5]
                topics.append(open_record.get("primary_topic"))
                subjects = [
                    {
                        "subjectScheme": "OpenAlex Topic",
                        "schemeUri": "https://openalex.org",
                        "subject": top.get("display_name"),
                        "valueUri": top.get("id"),
                    }
                    for top in topics
                ]
            except Exception as e:
                print(e)
                subjects = []
                pass
    if self.defaults:
        subjects = subjects + self.defaults["subjects"]
    subjects = [json.loads(i) for i in set([json.dumps(i) for i in subjects])]
    return subjects


def neo_title(con: psycopg2.connect, self) -> object:
    """_Generate a valid dataset title._

    Args:
        con (psycopg2.connect): _A valid connection to the Neotoma database._

    Returns:
        object: _A title component matching the DataCite schema element._
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
        title = {"title": response[0], "lang": "en-us"}
    return title


def neo_location(con: psycopg2.connect, self) -> object:
    """_Generate a valid geopolitical location name and bounding box for the dataset._

    Args:
        con (psycopg2.connect): _A valid Neotoma database connection._

    Raises:
        ValueError: _An error raised if there is no proximate geopolitical unit (mostly ocean sites)._

    Returns:
        object: _An object that maps to the geoLocation element in the DataCite metadata._
    """
    geolocation = {"geoLocationPlace": None}
    # Using 0.01 as the precision to give less precise coordinate box.
    loc_query = """
        SELECT
            ST_AsText(ST_extent(st_buffer(st.geog::geometry, 0.01))) AS polygon
        from ndb.sites as st
        inner join ndb.collectionunits as cu on cu.siteid = st.siteid
        inner join ndb.datasets as ds on ds.collectionunitid = cu.collectionunitid
        where ds.datasetid = %(datasetid)s;"""
    with con.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(loc_query, {"datasetid": self.datasetid})
        response = cur.fetchone()
    polygon = wkt.loads(response[0])
    coordinates = list(polygon.exterior.coords)
    geolocation["geoLocationBox"] = {
        "westBoundLongitude": min([i[0] for i in coordinates]),
        "eastBoundLongitude": max([i[0] for i in coordinates]),
        "southBoundLatitude": min([i[1] for i in coordinates]),
        "northBoundLatitude": max([i[1] for i in coordinates]),
    }
    place_query = """
        select
            st.sitename,
            gadm.name_0,
            gadm.name_1,
            gadm.name_2,
            gadm.name_3,
            gadm.name_4,
            gadm.name_5
            from ndb.sites as st
            inner join ndb.collectionunits as cu on cu.siteid = st.siteid
            inner join ndb.datasets as ds on ds.collectionunitid = cu.collectionunitid
            inner join ap.gadm as gadm on st_contains(gadm.shape, st.geog::geometry)
            where ds.datasetid = %(datasetid)s;"""
    with con.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(place_query, {"datasetid": self.datasetid})
        response = cur.fetchone()
    if response is None:
        place_query = """
        with dsset as (
            SELECT
            st.geog, st.sitename
            from ndb.sites as st
            inner join ndb.collectionunits as cu on cu.siteid = st.siteid
            inner join ndb.datasets as ds on ds.collectionunitid = cu.collectionunitid
            where ds.datasetid = %(datasetid)s
            LIMIT 1
        )
        select
        st.sitename,
            gadm.name_0,
            gadm.name_1,
            gadm.name_2,
            gadm.name_3,
            gadm.name_4,
            gadm.name_5
        from dsset as st
        cross join lateral (
        select  gadm.name_0,
                gadm.name_1,
                gadm.name_2,
                gadm.name_3,
                gadm.name_4,
                gadm.name_5,
                gadm.shape::geometry <-> st.geog::geometry as dist
        from ap.gadm as gadm
        order by dist
        limit 1) gadm;"""
        with con.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(place_query, {"datasetid": self.datasetid})
            response = cur.fetchone()
        if response is None:
            raise ValueError("This site cannot return a close neighbour.")
    response_loc = (
        "Site name: "
        + response[0]
        + "; "
        + "; ".join(reversed([i for i in response[1:] if i]))
    )
    geolocation["geoLocationPlace"] = response_loc
    return [geolocation]


def neo_relatedIdentifiers(con: psycopg2.connect, self) -> object:
    """_Return identifiers related to the Neotoma dataset._

    Args:
        con (psycopg2.connect): _A valid Neotoma database connection._

    Returns:
        object: _An object that aligns with the DataCite `relatedIdentifiers` schema for Neotoma datasets._
    """
    relatedIdentifiers = []
    ds_query = """
        SELECT doi as identifier,
        'DOI' as identifierType
        FROM doi.doimeta
        WHERE datasetid = %(datasetid)s;
    """
    with con.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        _ = cur.execute(ds_query, {"datasetid": self.datasetid})
        response = cur.fetchall()
        if response:
            for i in response:
                if i[0] != self.identifiers.get("identifier"):
                    relatedIdentifiers.append(
                        {
                            "relatedIdentifierType": "DOI",
                            "relationType": "IsIdenticalTo",
                            #'relatedItemType': 'Dataset',
                            "relatedIdentifier": i.get("identifier"),
                        }
                    )
    pub_query = """
        SELECT DISTINCT pub.doi as doi,
        'DOI' as identifierType
        FROM ndb.datasetpublications AS dsp
        INNER JOIN ndb.publications AS pub ON dsp.publicationid = pub.publicationid
        WHERE dsp.datasetid = %(datasetid)s
        AND pub.doi IS NOT NULL;"""
    with con.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(pub_query, {"datasetid": self.datasetid})
        response = cur.fetchall()
        if response:
            for i in response:
                pubdoi = dict(i)
                relatedIdentifiers.append(
                    {
                        "relatedIdentifierType": "DOI",
                        "relationType": "IsSupplementTo",
                        "relatedIdentifier": pubdoi.get("doi"),
                    }
                )
    geochron_query = """
        SELECT DISTINCT egc.identifier as identifier,
               edb.extdatabasename as name
        FROM ndb.datasets AS ds
        inner join ndb.collectionunits as cu on ds.collectionunitid = cu.collectionunitid
        inner join ndb.chronologies as ch on ch.collectionunitid = cu.collectionunitid
        inner join ndb.chroncontrols as cc on cc.chronologyid = ch.chronologyid
        inner join ndb.geochroncontrols as gcc on gcc.chroncontrolid = cc.chroncontrolid
        inner join ndb.externalgeochronology as egc on egc.geochronid = gcc.geochronid
        inner join ndb.externaldatabases as edb on edb.extdatabaseid = egc.extdatabaseid
        WHERE ds.datasetid = %(datasetid)s AND edb.extdatabasename = 'ARK';"""
    with con.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(geochron_query, {"datasetid": self.datasetid})
        response = cur.fetchall()
        if response:
            for i in response:
                gc_ark = dict(i)
                relatedIdentifiers.append(
                    {
                        "relatedIdentifierType": "ARK",
                        "relationType": "HasMetadata",
                        #'relatedItemType': 'Dataset',
                        "relatedIdentifier": gc_ark.get("identifier"),
                    }
                )
    return relatedIdentifiers


def neo_size(con: psycopg2.connect, self) -> object:
    """_Get dataset object size._

    Args:
        con (psycopg2.connect): _A valid Neotoma database connection._

    Raises:
        AttributeError: _An error raised when the dataset has not been previously frozen._

    Returns:
        object: _An object that aligns with the DataCite `size` property._
    """
    query = """
        SELECT download
        FROM doi.frozen
        WHERE datasetid = %(datasetid)s;
    """
    with con.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(query, {"datasetid": self.datasetid})
        response = cur.fetchone()
        if response:
            download = getsizeof(dumps(response))
            size = [f"{round(download / 1000)} kB"]
        else:
            raise AttributeError(
                "There is no frozen version of this dataset. Use the freeze_data()"
            )
    return size


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
                creators.append(
                    {k: creator[k] for k in creator.keys() if k != "piorder"}
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
    return creators


def neo_contributors(con: psycopg2.connect, self) -> list:
    """_Obtain a list of the dataset contributors by activity for a dataset._

    Args:
        con (psycopg2.connect): _A valid connection the the Neotoma Database server_

    Returns:
        list: _A list of Neotoma contributors, including external identifiers when available._
    """
    query = """
        WITH chronfolk AS (
        SELECT DISTINCT  contactid,
                'Researcher'::text AS contributorType
        FROM     ndb.datasets AS d
        JOIN ndb.chronologies AS chron ON d.collectionunitid = chron.collectionunitid
        WHERE d.datasetid = %(datasetid)s
        ),
        collfolk AS (
        SELECT DISTINCT  contactid, 'DataCollector'::text AS contributortype
        FROM     ndb.datasets AS d
        JOIN   ndb.collectors AS coll ON d.collectionunitid = coll.collectionunitid
        WHERE d.datasetid = %(datasetid)s
        ),
        dpi AS (
        SELECT DISTINCT  contactid,
                'ProjectLeader'::text AS contributortype
        FROM ndb.datasetpis WHERE datasetpis.datasetid = %(datasetid)s
        ),
        curator AS (
        /* In the DB stuff this should be a 'DataSteward' */
        SELECT DISTINCT  contactid, 'DataCurator'::text AS contributortype
        FROM ndb.datasetsubmissions
        WHERE datasetsubmissions.datasetid = %(datasetid)s
        ),
        coauth AS (
        SELECT DISTINCT contactid,
                'Researcher'::text AS contributortype
        FROM ndb.datasetpublications AS d
        JOIN ndb.publicationauthors AS paut ON d.publicationid = paut.publicationid
        WHERE d.datasetid = %(datasetid)s
        ),
        analyst AS (
            SELECT DISTINCT sana.contactid,
        /* In the DB stuff this should be a 'DataAnalyst' */
                    'DataCollector'::text AS contributortype
        FROM        ndb.samples AS samp
        JOIN ndb.sampleanalysts AS sana ON samp.sampleid = sana.sampleid
        WHERE samp.datasetid = %(datasetid)s
        )
        SELECT DISTINCT cts.contactname AS name,
                        -- cts.address AS affiliation,
                        lister.contributortype as "contributorType",
                        jsonb_agg(DISTINCT 
                                jsonb_build_object('nameIdentifier', exct.identifier,
                                                   'nameIdentifierScheme', exdb.extdatabasename, 
                                                   'schemeUri', exdb.url)) AS "nameIdentifiers"
        FROM (SELECT * FROM analyst
        UNION ALL
        (SELECT * FROM coauth)
        UNION ALL
        (SELECT * FROM curator)
        UNION ALL
        (SELECT * FROM dpi)
        UNION ALL
        (SELECT * FROM collfolk)
        UNION ALL
        (SELECT * FROM chronfolk)) AS lister
        JOIN ndb.contacts AS cts ON cts.contactid = lister.contactid
        LEFT JOIN ndb.externalcontacts AS exct ON exct.contactid = cts.contactid
        LEFT JOIN ndb.externaldatabases AS exdb ON exdb.extdatabaseid = exct.extdatabaseid
        GROUP BY cts.contactid, lister.contributortype;
    """
    try:
        with con.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(query, {"datasetid": self.datasetid})
            response = cur.fetchall()
            contributors = []
            for i in response:
                creator = dict(i)
                if not all(
                    [i.get("nameIdentifier") for i in creator.get("nameIdentifiers")]
                ):
                    _ = creator.pop("nameIdentifiers", None)
                contributors.append(creator)
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
    return contributors


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
                    {
                        "dateType": i.get("text"),
                        "date": i.get("date").strftime("%Y-%m-%d"),
                    }
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
