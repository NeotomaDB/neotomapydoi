import yaml
from datetime import datetime, timedelta
import jsonschema
from json import load
from .neo_connect import neo_connect
from .neo_contributors import neo_contributors
from .neo_creators import neo_creators
from .neo_title import neo_title
from .neo_subjects import neo_subjects
from .neo_location import neo_location
from .neo_identifier import neo_identifier
from .neo_relatedIdentifiers import neo_relatedIdentifiers
from .neo_dates import neo_dates
from .neo_size import neo_size
from .neo_description import neo_description
from datacite import schema45
import requests
import psycopg2
import psycopg2.extras
from psycopg2.extras import Json
import deepdiff.diff as dd
from json import dumps
from warnings import warn
from .testMode import testMode
from .credentials import credentials
from .activity import activity

class neotomaDOI:
    def __init__(self, datasetid: int, defaults: str = None):
        if defaults:
            with open(defaults, "r") as file:
                self.defaults = yaml.safe_load(file)
        else:
            self.defaults = {}
        self.datasetid = datasetid
        self.mode = testMode.test
        self.data = {
            "creators": None,
            "titles": None,
            "publisher": self.defaults.get("publisher"),
            "publicationYear": str(datetime.now().year),
            "types": self.defaults.get("types"),
            "schemaVersion": self.defaults.get("schemaVersion"),
            "language": self.defaults.get("language"),
            "rightsList": self.defaults.get("rightsList"),
            "formats": self.defaults.get("formats"),
        }
        self.meta = {}
        self.schema = None
        self.client = None
        self.datacite_url = testMode.test

    def __str__(self):
        return dumps(self.data)

    def add_schema(self, schema:str):
        """_Add additional DataCite schema metadata to the NeotomaDOI object._

        Args:
            schema (str): _A valid file path to a valid DataCite JSON schema._
        """        
        with open(schema, "r", encoding="UTF-8") as f:
            self.schema = load(f)

    def validate(self, schema: str = None) -> bool:
        """_summary_

        Args:
            schema (str, optional): _A valid DataCite JSON schema_. Defaults to None.

        Raises:
            jsonschema.exceptions.ValidationError: _Validation errors from the `jsonschema` package._

        Returns:
            _bool_: _Returns True if the function passes the schema, else raises an error._
        """        
        if schema is not None:
            self.add_schema(schema)
        if self.schema is not None:
            return jsonschema.validate(instance=self.data, schema=self.schema)
        else:
            try:
                _ = schema45.validator.validate(self.data)
            except Exception:
                raise jsonschema.exceptions.ValidationError(
                    "There is an issue in the JSON object passed."
                )
        return True

    def update(self):
        """_Add relevant metadata for DOI minting rom the remote database._

        Raises:
            ValueError: _If critical metadata is missing, or is formatted incorrectly, then raise an error._
        """        
        if self.datasetid:
            con = neo_connect(test=(self.mode.name == "test"))
            try:
                self.data["creators"] = neo_creators(con, self)
                self.data["contributors"] = neo_contributors(con, self)
                self.data["titles"] = [neo_title(con, self)]
                self.data["subjects"] = neo_subjects(con, self)
                self.data["geoLocations"] = neo_location(con, self)
                self.identifiers = neo_identifier(con, self)
                self.data["relatedIdentifiers"] = neo_relatedIdentifiers(con, self)
                self.data["dates"] = neo_dates(con, self)
                self.data["sizes"] = neo_size(con, self)
                self.data["descriptions"] = neo_description(con, self)
                self.activity = None
                if self.identifiers:
                    self.get_activity()
                    self.get_meta()
            except Exception:
                raise ValueError(
                    f"Dataset {self.datasetid} is missing critical metadata values in the database."
                )

    def set_user(self, cred: credentials, mode: testMode = testMode.test):
        """_Set the user credentials for the DataCite API, depending on the mode._

        Args:
            cred (credentials): _A neotomapydoi.credentials() object._
            mode (testMode, optional): _The API mode, either test or produxtion_. Defaults to testMode.test.

        Raises:
            TypeError: _Raised if credentials are not passed in the proper format._
        """        
        if not isinstance(cred, credentials):
            raise TypeError("Credentials must be of type neotomadoi.credential")
        self.client = cred
        self.mode = mode

    def test_mode(self):
        """_Set the DataCite API interactions to sadbox mode._

        Raises:
            ValueError: _Ensure that credentials have been passed to the datacite object._
        """        
        if self.client is None:
            raise ValueError("You cannot change the mode without credentials [use neotomapydoi.credentials()].")
        self.mode = testMode.test

    def prod_mode(self):
        """_Set the DataCite API mode to production._

        Raises:
            ValueError: _Raises a ValueError is the value of the self.client is not set using `object.set_user()`._
        """        
        if self.client is None:
            raise ValueError("You cannot use production mode without credentials.")
        self.mode = testMode.prod

    def get_mode(self):
        """_Get the current DataCite DOI access mode (test or production)._

        Returns:
            _str_: _Prints the current mode name and URL path._
        """        
        return print(f"mode: {self.mode.name}; URL: {self.mode.value}")

    def get_meta(self):
        """_Obtain the current DOI metadata for the record (if it exists).

        Raises:
            ValueError: _Raises a value error when there is no DOI identifier associated with the data object._
            requests.exceptions.HTTPError: _Passes along any API errors returned from DataCite associated with the identifier provided._
        """        
        if self.identifiers:
            dois = self.identifiers.get("identifier")
            doi_call = requests.get(
                self.mode.value + dois,
                headers={"Content-Type": "application/vnd.api+json"},
                auth=(
                    self.client.mode(self.mode).get("username"),
                    self.client.mode(self.mode).get("pw"),
                ),
            )
            if doi_call.status_code == 200:
                self.meta = doi_call.json().get("data").get("attributes")
            else:
                raise requests.exceptions.HTTPError(doi_call.json().get("errors"))
        else:
            raise ValueError("There is no DOI currently associated with this object.")

    def update_doi(self):
        outcome = None
        try:
            outcome = self.validate()
        except Exception:
            outcome = False
        if outcome is False:
            print("Validation error. Check with the `validate()` method.")
            return None
        doi = self.identifiers.get("identifier")
        self.get_meta()
        version = self.meta.get("version")
        if version:
            version = version.split(".")
            version[1] = int(version[1]) + 1
            self.data["version"] = ".".join([str(i) for i in version])
        else:
            self.data["version"] = "1.1"
        payload = {
            "data": {"type": "dois", "attributes": self.data, "action": "update"}
        }
        try:
            modifier = requests.put(
                self.mode.value + self.identifiers.get("identifier"),
                headers={"Content-Type": "application/vnd.api+json"},
                auth=(
                    self.client.mode(self.mode).get("username"),
                    self.client.mode(self.mode).get("pw"),
                ),
                data=dumps(payload),
            )
            if modifier.status_code != 200:
                raise requests.RequestException(
                    f"Failed to modify DOI: {modifier.text}"
                )
            else:
                print(f'Successful PUT update for dataset {self.datasetid} to {self.identifiers['identifier']}')    
                response = modifier.json()
                assert response.get("data").get("id") == doi
                self.meta = self.get_meta()
                insertQuery = """INSERT INTO ndb.datasetdoi (datasetid, doi, published, recdatecreated)
                                VALUES (%(datasetid)s, %(identifier)s, %(publish)s, NOW()::timestamp)
                                ON CONFLICT (datasetid, doi)
                                DO UPDATE
                                SET recdatemodified=NOW()::timestamp
                                RETURNING datasetid
                                """
                con = neo_connect(test=(self.mode.name == "test"))
                with con.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    _ = cur.execute(
                        insertQuery,
                        {
                            "datasetid": self.datasetid,
                            "identifier": self.identifiers.get("identifier"),
                            "publish": True,
                        },
                    )
                    con.commit()
                con = neo_connect(test=(self.mode.name == "test"))
                insertMeta = """INSERT INTO doi.doimeta(doi, meta, datasetid)
                                VALUES (%(doi)s, %(meta)s, %(datasetid)s)
                                ON CONFLICT (doi, datasetid) DO UPDATE
                                    SET meta = EXCLUDED.meta
                                    RETURNING datasetid;"""
                with con.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    _ = cur.execute(
                        insertMeta,
                        {
                            "meta": Json(self.meta),
                            "datasetid": self.datasetid,
                            "doi": self.identifiers.get("identifier"),
                        },
                    )
                    con.commit()
                self.get_activity()
        except Exception as e:
            print(e)

    def get_activity(self):
        self.activity = activity(doi=self.identifiers.get("identifier"))

    def mint_doi(self, publish=True):
        if self.identifiers:
            self.get_meta()
            if self.meta.get("isActive", False):
                # If a DOI has been minted and the DOI is active, update the DOI.
                self.update_doi()
                return None
            elif self.meta.get("isActive", True) is False and publish is True:
                self.update_doi()
                return None
            else:
                return None
        outcome = None
        try:
            self.data["version"] = "1.0"
            outcome = self.validate()
        except Exception:
            outcome = True
        if outcome:
            print("Validation error. Check with the `validate()` method.")
            return None
        payload = {"type": "dois", "attributes": self.data}
        date = min(
            [
                datetime.strptime(i.get("date"), "%Y-%m-%d")
                for i in self.data.get("dates")
                if i.get("dateType") == "Submitted"
            ]
        )
        if datetime.now() - date > timedelta(days=2) and publish is True:
            # We're publishing and the dataset is old enough.
            payload["attributes"]["event"] = "publish"
        if self.meta.get("isActive", True) is False:
            # The dataset has been drafted, but we want to publish now.
            # If there is no `meta` element, then we continue to ignore it.
            payload["attributes"]["event"] = "publish"
            payload["attributes"]["doi"] = self.identifiers.get("identifier")
        payload["attributes"]["prefix"] = self.client.mode(self.mode).get("handle")
        payload["attributes"]["url"] = (
            f"https://data.neotomadb.org/datasets/{self.datasetid}"
        )
        payload["attributes"]["version"] = "1.0"
        try:
            created = requests.post(
                self.mode.value,
                headers={"Content-Type": "application/vnd.api+json"},
                auth=(
                    self.client.mode(self.mode).get("username"),
                    self.client.mode(self.mode).get("pw"),
                ),
                data=dumps({"data": payload}),
            )
            if created.status_code != 201:
                raise requests.RequestException(f"Failed to create DOI: {created.text}")
            else:
                # self.meta = created.json().get('data').get('attributes')
                self.identifiers = {
                    "identifier": created.json().get("data").get("id"),
                    "identifierType": "DOI",
                }
                self.get_meta()
                insertQuery = """INSERT INTO ndb.datasetdoi (datasetid, doi, published, recdatecreated)
                                VALUES (%(datasetid)s, %(identifier)s, %(publish)s, NOW()::timestamp)
                                ON CONFLICT (datasetid, doi)
                                DO UPDATE
                                SET recdatemodified=NOW()::timestamp
                                RETURNING datasetid
                                """
                con = neo_connect(test=(self.mode.name == "test"))
                with con.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    _ = cur.execute(
                        insertQuery,
                        {
                            "datasetid": self.datasetid,
                            "identifier": self.identifiers.get("identifier"),
                            "publish": publish,
                        },
                    )
                    con.commit()
                insertMeta = """INSERT INTO doi.doimeta(doi, meta, datasetid)
                                VALUES (%(doi)s, %(meta)s, %(datasetid)s)
                                ON CONFLICT (doi, datasetid) DO NOTHING;"""
                with con.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    _ = cur.execute(
                        insertMeta,
                        {
                            "meta": Json(self.meta),
                            "datasetid": self.datasetid,
                            "doi": self.identifiers.get("identifier"),
                        },
                    )
                    con.commit()
                self.get_activity()
        except Exception:
            raise ValueError("Could not mint the dataset.")
        return None

    def meta_diff(self):
        current = self.data
        old = self.meta[0]
        self.meta_diff = dd.DeepDiff(old, current, ignore_order=True)

    def deactivate(self):
        if self.identifiers:
            self.update_doi()
        else:
            outcome = None
            try:
                outcome = self.validate()
            except Exception:
                outcome = True
            if outcome:
                print("Validation error. Check with the `validate()` method.")
                return None
        payload = {"type": "dois", "attributes": self.data}
        payload["attributes"]["event"] = "hide"
        payload["attributes"]["prefix"] = self.client.get("prefix")
        payload["attributes"]["url"] = (
            f"https://data.neotomadb.org/datasets/{self.datasetid}"
        )
        payload["attributes"]["version"] = "1.0"
        try:
            created = requests.put(
                self.mode.value,
                headers={"Content-Type": "application/vnd.api+json"},
                auth=(self.client.get("username"), self.client.get("password")),
                data=dumps(f'{"data": {payload}}'),
            )
            if created.status_code != 200:
                raise requests.RequestException(f"Failed to create DOI: {created.text}")
            else:
                self.meta = created.json().get("data").get("attributes")
                self.identifiers = [
                    {
                        "identifier": created.json().get("data").get("id"),
                        "identifierType": "DOI",
                    }
                ]
                insertQuery = """INSERT INTO ndb.datasetdoi (datasetid, doi, recdatecreated)
                                 VALUES (%(datasetid)s, %(identifier)s, NOW()::timestamp)
                                 RETURNING datasetid"""
                con = neo_connect(test=(self.mode.name == "test"))
                with con.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    cur.execute(
                        insertQuery,
                        {
                            "datasetid": self.datasetid,
                            "identifier": self.identifiers[0].get("identifier"),
                        },
                    )
                con.commit()
        except Exception as e:
            print(e)

    def freeze_data(self, con, force: bool = False):
        if self.datasetid:
            con = neo_connect(test=(self.mode.name == "test"))
            query = """
                SELECT * FROM doi.frozen
                WHERE datasetid = %(datasetid)s"""
            with con.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute(query, {"datasetid": self.datasetid})
                result = cur.fetchone()
            if not result:
                freeze = """
                    INSERT INTO doi.frozen (datasetid, download, recdatecreated)
                    SELECT df.datasetid,
                           df.record AS download,
                        current_timestamp AS recdatecreated
                    FROM doi.doifreeze(ARRAY[%(datasetid)s]) as df
                    ON CONFLICT DO NOTHING;
                """
                with con.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    cur.execute(freeze, {"datasetid": self.datasetid})
                    cur.execute(
                        "SELECT * FROM doi.frozen WHERE datasetid = %(datasetid)s;",
                        {"datasetid": self.datasetid},
                    )
                    frozen_result = cur.fetchall()
                con.commit()
                if len(frozen_result) > 0:
                    print("Dataset frozen.")
            else:
                warn(
                    "This dataset has already been frozen in the database. You must override manually.",
                    UserWarning,
                )
        else:
            raise ValueError(
                "Dataset must have a valid datasetid and be in Neotoma to freeze the dataset."
            )
