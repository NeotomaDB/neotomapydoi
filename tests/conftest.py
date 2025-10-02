import pytest
from neotomadoi import neotomaDOI, credentials, neo_connect
from dotenv import load_dotenv
import json
import os

load_dotenv()

@pytest.fixture
def con_tester():
    return neo_connect()

@pytest.fixture
def dcite_credentials():
    """
    Fixture to provide DataCite credentials.
    This separates credential loading from the DOI object creation.
    """
    dcite_json = os.getenv("DCITE")
    if not dcite_json:
        pytest.skip("DCITE credentials not found in environment")
    
    try:
        dcite_data = json.loads(dcite_json)
        return credentials(dcite_data)
    except (json.JSONDecodeError, ValueError) as e:
        pytest.fail(f"Failed to parse DCITE credentials: {e}")

@pytest.fixture
def test_dataset_id():
    """
    Fixture to provide a test dataset ID.
    You can override this in specific tests if needed.
    """
    return 16  # Your default test dataset ID

@pytest.fixture
def doiobj_prod(test_dataset_id, dcite_credentials):
    new_doi = neotomaDOI(datasetid=test_dataset_id, defaults="neotomadoi.yaml")
    datacite_meta = dcite_credentials
    new_doi.set_user(datacite_meta)
    new_doi.dataciteProd_mode()
    return new_doi

@pytest.fixture
def doiobj_test(test_dataset_id, dcite_credentials):
    new_doi = neotomaDOI(datasetid=test_dataset_id, defaults="neotomadoi.yaml")
    datacite_meta = dcite_credentials
    new_doi.set_user(datacite_meta)
    new_doi.dataciteTest_mode()
    return new_doi