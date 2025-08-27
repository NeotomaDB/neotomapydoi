from neotomadoi import neotomaDOI, activity, credentials
from dotenv import load_dotenv
import pytest

def test_activity(doiobj_prod):
    # We should expect that we can create the object and obtain activity information.
    doiobj_prod.update()
    doiobj_prod.get_activity()
    assert len(doiobj_prod.activity) > 0
    assert isinstance(doiobj_prod.activity, activity)
