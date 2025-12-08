import yaml
from datetime import datetime, timedelta
import jsonschema
from json import load
import traceback
from .neo_connect import neo_connect
from .fetch_metadata import neo_contributors, neo_creators, neo_title, neo_subjects, neo_location, neo_identifier, neo_relatedIdentifiers, neo_dates, neo_size, neo_description
from datacite import schema45
import requests
import psycopg2
import psycopg2.extras
from psycopg2.extras import Json
import deepdiff.diff as dd
from json import dumps
from warnings import warn
from .dataciteTestMode import dataciteTestMode
from .databaseMode import databaseMode
from .credentials import credentials
from .activity import activity

class neotomaDOI:
    """Manages DOI metadata generation and registration with DataCite for Neotoma datasets.
    
    This class handles the complete workflow of creating, validating, and publishing
    Digital Object Identifiers (DOIs) for paleological datasets in the Neotoma database.
    The `neotomaDOI()` class interfaces with both the Neotoma database (to extract metadata)
    and the DataCite API (to register DOIs).
    
    Typical Workflow:
        1. Create instance with a dataset ID
        2. Set credentials with set_user()
        3. Call update() to populate metadata from database
        4. Validate the metadata with validate()
        5. Freeze the dataset with freeze_data()
        6. Mint or update the DOI with mint_doi()
    
    Attributes:
        datasetid (int): The Neotoma dataset identifier
        data (dict): The DataCite metadata object (follows DataCite schema)
        identifiers (dict): The DOI identifier info (if one exists)
        meta (dict): Current DOI metadata from DataCite (if DOI exists)
        activity (list): History of DOI events from DataCite
        dataciteMode (dataciteTestMode): API mode (test or prod)
        databaseMode (databaseMode): Database mode (tank or prod)
        strict (bool): If True, raises errors for data state issues; if False, warns only
        
    Examples:
        >>> doi = neotomaDOI(datasetid=12345, defaults="neotomadoi.yaml")
        >>> doi.set_user(credentials_obj)
        >>> doi.update()  # Fetch metadata from database
        >>> doi.validate()  # Check against DataCite schema
        >>> doi.mint_doi()  # Publish to DataCite
    """

    _INSERT_DOI_DATASET_ = """INSERT INTO ndb.datasetdoi (datasetid, doi, published, recdatecreated)
                                VALUES (%(datasetid)s, %(identifier)s, %(publish)s, NOW()::timestamp)
                                ON CONFLICT (datasetid, doi)
                                DO UPDATE
                                SET recdatemodified=NOW()::timestamp
                                RETURNING datasetid"""
    
    _INSERT_DOI_METADATA_ = """INSERT INTO doi.doimeta(doi, meta, datasetid)
                               VALUES (%(doi)s, %(meta)s, %(datasetid)s)
                               ON CONFLICT (doi, datasetid) DO NOTHING;"""
    
    def __init__(self, datasetid: int, defaults: str = None):
        if defaults:
            with open(defaults, "r") as file:
                self.defaults = yaml.safe_load(file)
        else:
            self.defaults = {}
        self.datasetid = datasetid
        self.dataciteMode = dataciteTestMode.test
        self.databaseMode = databaseMode.tank
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
        self.datacite_url = dataciteTestMode.test
        self.strict = True
        self._updated = False
        self._validated = False
        self._data_hash = None

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
        """Validate the current DOI metadata prior to minting the DOI.
        This function tests the metadata as stored in the `data` attribute of the neotomaDOI object against the existing
        DataCite dataset schema. The function uses the `schema45.validator` function in the `datacite` Python package.
        
        Validation is required for any dataset before it can be minted. The `validate` function sets the `_validated` flag
        which also triggers the `_data_hash` call.

        Args:
            schema (str, optional): _A valid DataCite JSON schema_. Defaults to None.

        Raises:
            jsonschema.exceptions.ValidationError: _Validation errors from the `jsonschema` package._

        Returns:
            _bool_: _Returns True if the function passes the schema, else raises an error._
        """        
        if schema is not None:
            self.add_schema(schema)
        
        try:
            if self.schema is not None:
                validation = jsonschema.validate(instance=self.data, schema=self.schema)
                self._validated = True
                self._set_update()

            else:
                validation = schema45.validator.validate(self.data)
                self._validated = True
                self._set_update()
        except jsonschema.exceptions.ValidationError as e:
            raise jsonschema.exceptions.ValidationError(
                f"Dataset {self.datasetid} validation failed. "
                f"Field: {'.'.join(str(p) for p in e.path) if e.path else 'root'}. "
                f"Error: {e.message}"
            ) from e
        return validation

    def _set_update(self) -> bool:
        """Record an update to the DOI record.
        
        This changes state for the `_updated` flag, and records a new hash in `_data_hash`.

        Returns:
            bool: _Confirms the method has run._
        """        
        self._updated = True
        self._data_hash = hash(str(self.data))
        return True

    def update(self):
        """_Add relevant metadata for DOI minting from the remote database._

        Raises:
            ValueError: _If critical metadata is missing, or is formatted incorrectly, then raise an error._
        """

        assert self.datasetid is not None, "The datasetid must be defined before calling .update()"

        con = neo_connect(tank=(self.databaseMode.name == "tank"))

        # Track what we're doing for better error messages
        metadata_steps = [
            ("creators", lambda: neo_creators(con, self)),
            ("contributors", lambda: neo_contributors(con, self)),
            ("titles", lambda: [neo_title(con, self)]),
            ("subjects", lambda: neo_subjects(con, self)),
            ("geoLocations", lambda: neo_location(con, self)),
            ("identifiers", lambda: neo_identifier(con, self)),
            ("relatedIdentifiers", lambda: neo_relatedIdentifiers(con, self)),
            ("dates", lambda: neo_dates(con, self)),
            ("sizes", lambda: neo_size(con, self)),
            ("descriptions", lambda: neo_description(con, self)),
        ]

        for field_name, fetch_func in metadata_steps:
            try:
                if field_name == "identifiers":
                    self.identifiers = fetch_func()
                else:
                    self.data[field_name] = fetch_func()
            except Exception as e:
                warn(
                    f"Dataset {self.datasetid}: Failed to fetch optional '{field_name}' metadata. "
                    f"Error: {type(e).__name__}: {str(e)}. "
                    f"This field will be None.",
                    UserWarning
                )
                if field_name == "identifiers":
                    self.identifiers = None
                else:
                    self.data[field_name] = None
        
        self.activity = None

        if self.identifiers:
            try:
                self.get_activity()
            except Exception as e:
                raise ValueError(
                f"Dataset {self.datasetid}: Failed to fetch '{field_name}' metadata. "
                f"Error: {type(e).__name__}: {str(e)}"
            ) from e

            try:
                self.get_meta()
            except Exception as e:
                pass

            # Identify the data as having been remotely updated, and add the hash.
            # This way we can quickly check if things have changed without needing to rely on a separate `update()` check.
        self._set_update()
            
    def _data_changed_since_update(self) -> bool:
        """Check if self.data has been modified since update() was called.

        The function uses the hashing method to return a signed `int` representing a numerical hash of the dict object.
        If the two hashes (past and current) are different, then we return False, otherwise, if there is no change
        then we return True.

        Returns:
            _bool_: _A boolean, letting us know whether the data has been changed._
        """
        if not self._updated:
            return None
        current_hash = hash(str(self.data))
        return current_hash != self._data_hash

    def _check_data_state(self, operation: str):
        """Check that the internal data is in valid state for minting/updating.

        We have a `strict` mode for this process, where, if a dataset has been changed since
        the dataset metadata got an `update()`, it cannot be minted or have its DOI updated. This prevents
        programmatic changes to the object metadata (self.data) from propagating through the data network.
        
        Args:
            operation: Name of operation being performed (for error messages)
            
        Raises:
            AssertionError: In strict mode, if data state is invalid
            
        Warns:
            UserWarning: In non-strict mode, if data state is questionable
        """
        if not self._updated:
            msg = f"{operation} called without calling update(). Ensure self.data is properly populated."
            if self.strict:
                raise AssertionError(msg)
            else:
                warn(msg, UserWarning)
    
        data_changed = self._data_changed_since_update()
        if data_changed:
            msg = f"{operation} called after manual data modification. Data may not match database state."
            if self.strict:
                raise AssertionError(msg)
            else:
                warn(msg, UserWarning)

    def set_user(self, cred: credentials, mode: dataciteTestMode = dataciteTestMode.test):
        """_Set the user credentials for the DataCite API, depending on the mode._

        Args:
            cred (credentials): _A neotomapydoi.credentials() object._
            mode (dataciteTestMode, optional): _The API mode, either test or produxtion_. Defaults to dataciteTestMode.test.

        Raises:
            TypeError: _Raised if credentials are not passed in the proper format._
        """        
        if not isinstance(cred, credentials):
            raise TypeError("Credentials must be of type neotomadoi.credential")
        self.client = cred
        self.dataciteMode = mode

    def dataciteTest_mode(self):
        """_Set the DataCite API interactions to sadbox mode._

        Raises:
            ValueError: _Ensure that credentials have been passed to the datacite object._
        """        
        if self.client is None:
            raise ValueError("You cannot change the mode without credentials [use neotomapydoi.credentials()].")
        self.dataciteMode = dataciteTestMode.test

    def dataciteProd_mode(self):
        """_Set the DataCite API mode to production._

        Raises:
            ValueError: _Raises a ValueError is the value of the self.client is not set using `object.set_user()`._
        """        
        if self.client is None:
            raise ValueError("You cannot use production mode without credentials.")
        self.dataciteMode = dataciteTestMode.prod

    def databaseTank_mode(self):
        """_Set the DataCite API interactions to sadbox mode._

        Raises:
            ValueError: _Ensure that credentials have been passed to the datacite object._
        """        
        if self.client is None:
            raise ValueError("You cannot change the mode without credentials [use neotomapydoi.credentials()].")
        self.databaseMode = databaseMode.tank

    def databaseProd_mode(self):
        """_Set the DataCite API mode to production._

        Raises:
            ValueError: _Raises a ValueError is the value of the self.client is not set using `object.set_user()`._
        """        
        if self.client is None:
            raise ValueError("You cannot use production mode without credentials.")
        self.databaseMode = databaseMode.prod

    def get_mode(self):
        """_Get the current DataCite DOI access mode (test or production)._

        Returns:
            _str_: _Prints the current mode name and URL path._
        """        
        return print(f"mode: {self.dataciteMode.name}; URL: {self.dataciteMode.value}")

    def get_meta(self):
        """_Obtain the current DOI metadata for the record (if it exists).

        Raises:
            ValueError: _Raises a value error when there is no DOI identifier associated with the data object._
            requests.exceptions.HTTPError: _Passes along any API errors returned from DataCite associated with the identifier provided._
        """
        
        if self.identifiers:
            dois = self.identifiers.get("identifier")
            doi_call = requests.get(
                self.dataciteMode.value + dois,
                headers={"Content-Type": "application/vnd.api+json",
                         "User-Agent": "Neotoma Paleoecology Database DOI System/0.1.0 (Linux; Python v3.11) email:goring@wisc.edu"},
            )
            if doi_call.status_code == 200:
                self.meta = doi_call.json().get("data").get("attributes")
            else:
                if self.dataciteMode.name == 'prod':
                    print('Production mode is set, this DOI is not resolving.')
                    raise requests.exceptions.HTTPError(doi_call.json().get("errors"))
                else:
                    # Here, if the error is 404, then it's not found. More than likely we need to
                    # actually check the production datacite location.
                    # raise requests.exceptions.HTTPError(doi_call.json().get("errors"))
                    _ = 10
        else:
            raise ValueError("There is no DOI currently associated with this object.")

    def update_doi(self):
        assert self.client is not None, "Requires a valid DataCite client. Must call `set_user()` before updating."
        assert self.identifiers is not None, "Cannot update - no existing DOI found. Use mint_doi() instead"
        assert self.data.get("creators") is not None, "Requires valid metadata. Call update() to populate DataCite metadata before minting."
        self._check_data_state("update_doi()")

        if not self.is_frozen():
            print(f"Dataset {self.datasetid} not frozen. Freezing now...")
            self.freeze_data()

        self.validate()

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
                self.dataciteMode.value + self.identifiers.get("identifier"),
                headers={"Content-Type": "application/vnd.api+json"},
                auth=(
                    self.client.mode(self.dataciteMode).get("username"),
                    self.client.mode(self.dataciteMode).get("pw"),
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
                self._save_doi_to_database()
                self._update_doi_meta()
                self.get_activity()
        except Exception as e:
            print(e)


    def get_activity(self):
        """_Pull in the DataCite DOI activity_
        If the dataset has a prior identifier, then we request this history
        of that dataset from DataCite and add it to the `activity` property. 
        """        
        if self.identifiers:
            self.activity = activity(doi=self.identifiers.get("identifier"))
        else:
            self.activity = []

    def mint_doi(self):

        assert self.client is not None, "Must call set_user() before minting. Use neotomadoi.credentials() to set credentials."
        assert self.data.get("creators") is not None, "Must call update() before minting to populate metadata"
        
        self._check_data_state("mint_doi()")


        if not self.is_frozen():
            print(f"Dataset {self.datasetid} not frozen. Freezing now...")
            self.freeze_data()

        # If we're `minting` but the dataset already has a DOI, then we need to update.
        if self.identifiers:
            self.get_meta()
            if self.meta.get("isActive", False):
                # If a DOI has been minted and the DOI is active, update the DOI.
                self.update_doi()
                return None
            elif self.meta.get("isActive", True) is False and self.dataciteMode.name == 'prod':
                self.update_doi()
                return None
            else:
                return None
        
        _ = self.validate()
        
        payload = {"type": "dois", "attributes": self.data}
        date = min(
            [
                datetime.strptime(i.get("date"), "%Y-%m-%d")
                for i in self.data.get("dates")
                if i.get("dateType") == "Submitted"
            ]
        )
        if datetime.now() - date > timedelta(days=2) and self.dataciteMode.name == 'prod':
            # We're publishing and the dataset is old enough.
            payload["attributes"]["event"] = "publish"
        if self.meta.get("isActive", True) is False:
            # The dataset has been drafted, but we want to publish now.
            # If there is no `meta` element, then we continue to ignore it.
            payload["attributes"]["event"] = "publish"
            payload["attributes"]["doi"] = self.identifiers.get("identifier")
        payload["attributes"]["prefix"] = self.client.mode(self.dataciteMode).get("handle")
        payload["attributes"]["url"] = (
            f"https://data.neotomadb.org/datasets/{self.datasetid}"
        )
        payload["attributes"]["version"] = "1.0"
        try:
            created = requests.post(
                self.dataciteMode.value,
                headers={"Content-Type": "application/vnd.api+json"},
                auth=(
                    self.client.mode(self.dataciteMode).get("username"),
                    self.client.mode(self.dataciteMode).get("pw"),
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
                try:
                    self.get_meta()
                except Exception as e:
                    print('Failing from get_meta()')
                    print(self.identifiers)
                    print(e)
                
                _ = self._save_doi_to_database()

                self.get_activity()
        except Exception:
            raise ValueError("Could not mint the dataset.")
        return None

    def _save_doi_to_database(self) -> bool:
        """_Add the DOI into the database and associate it with the DatasetID_

        The ndb.datasetdoi table associates a DOI with a given dataset. It helps us keep track
        of DOIs and also keep track of when the DOIs were minted. It provides a quick
        lookup table for queries.

        Returns:
            _bool_: _A True/False value indicating whether the function has executed as
            expected. Returns True when a value is explicitly added to the database.
            A False is returned if the value does not need to be added, and an 
            error is raised if there is a failure adding the record._
        
        Raises:
            psycopg2.Error: If database operation fails
        """        
        # We only add to the table if we're in DataCite production mode, or
        # if the database is in Tank mode (in which case we can add whatever).
        if not (self.dataciteMode.name == 'prod' or self.databaseMode.name == "tank"):
            return False  # Explicitly skipped

        con = neo_connect(tank = (self.databaseMode.name == "tank"))
        
        with con.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            _ = cur.execute(
                self._INSERT_DOI_DATASET_,
                {
                    "datasetid": self.datasetid,
                    "identifier": self.identifiers.get("identifier"),
                    "publish": True,
                },
            )
            con.commit()
        return True


    def _update_doi_meta(self):
        """Update the DOI metadata entry in the Neotoma Database, including the JSON metadata and the DOI.
        
        This helps us keep track of any changes in the dataset DOI over longer terms without having to use the
        DataCite API over and over again. We can also perform analysis on the datasets to see how they're changing
        and what kinds of changes we're managing.

        Returns:
            _bool_: _Returns True when the statement has completed._
        """        

        con = neo_connect(tank = (self.databaseMode.name == "tank"))
        with con.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            _ = cur.execute(
                self._INSERT_DOI_METADATA_,
                {
                    "meta": Json(self.meta),
                    "datasetid": self.datasetid,
                    "doi": self.identifiers.get("identifier"),
                },
            )
            con.commit()
        return True


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
                self.dataciteMode.value,
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
                con = neo_connect(tank=(self.databaseMode.name == "tank"))
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

    def is_frozen(self):
        if self.datasetid:
            con = neo_connect(tank=(self.databaseMode.name == "tank"))
            query = """
                SELECT * FROM doi.frozen
                WHERE datasetid = %(datasetid)s"""
            with con.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute(query, {"datasetid": self.datasetid})
                result = cur.fetchall()
            if result:
                return True
            else:
                return False

    def freeze_data(self, force: bool = False):
        if self.datasetid:
            if not self.is_frozen():
                con = neo_connect(tank=(self.databaseMode.name == "tank"))
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
                self.data['sizes'] = neo_size(con, self)
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
