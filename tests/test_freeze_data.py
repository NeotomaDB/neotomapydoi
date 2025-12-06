from neotomadoi import neotomaDOI
import pytest
import psycopg2
import psycopg2.extras
from random import choice


def test_update_no_freeze_warns(con_tester):
    unfrozen_query = """
        SELECT ds.datasetid
        FROM ndb.datasets AS ds
        LEFT OUTER JOIN doi.frozen AS fz ON fz.datasetid = ds.datasetid
        WHERE fz.datasetid IS null
		  AND ds.datasettypeid > 1;"""
    with con_tester.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(unfrozen_query)
        frozen_result = cur.fetchall()

    if not frozen_result:
        pytest.skip("No unfrozen datasets available for testing")
    
    dsid = choice(frozen_result)[0]
    new_doi = neotomaDOI(datasetid=dsid, defaults="neotomadoi.yaml")
    
    with pytest.warns(UserWarning, match = 'Failed to fetch optional \'sizes\' metadata.'):
        new_doi.update()
    


def test_mint_auto_freezes(doiobj_test, dcite_credentials, con_tester):
    """Test that mint_doi() automatically freezes data if needed."""
    # Find an unfrozen dataset
    unfrozen_query = """
        SELECT ds.datasetid
        FROM ndb.datasets AS ds
        LEFT OUTER JOIN doi.frozen AS fz ON fz.datasetid = ds.datasetid
        WHERE fz.datasetid IS NULL
          AND ds.datasettypeid > 1;"""
    
    with con_tester.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(unfrozen_query)
        result = cur.fetchall()
    
    if not result:
        import pytest
        pytest.skip("No unfrozen datasets available for testing")
    
    dsid = choice(result)[0]
    test_doi = neotomaDOI(datasetid=dsid, defaults="neotomadoi.yaml")
    test_doi.set_user(dcite_credentials)
    test_doi.dataciteTest_mode()  # Use test mode!
    
    # Verify not frozen
    assert not test_doi.is_frozen()

    # Update and mint - should auto-freeze
    test_doi.update()
    test_doi.mint_doi()
    
    # Verify it got frozen
    assert test_doi.is_frozen()