from pytest import raises

from neotomadoi import neo_size


def test_size_with_doiobj(con_tester, doiobj_test_frozen):
    """Test neo_size using pre-configured DOI object."""
    sizes = neo_size(con_tester, doiobj_test_frozen)

    assert isinstance(sizes, list)
    assert len(sizes) > 0


def test_size_invalid_dataset(con_tester):
    """Test neo_size with non-existent dataset."""
    from neotomadoi import neotomaDOI

    invalid_doi = neotomaDOI(datasetid=700000, defaults="neotomadoi.yaml")
    with raises(Exception, match="no frozen version"):
        neo_size(con_tester, invalid_doi)
