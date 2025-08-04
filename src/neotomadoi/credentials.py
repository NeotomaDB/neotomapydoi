from .testMode import testMode

class credentials:
    """_An object to manage credentials for the DOI minting flow._
    """    
    def __init__(self, datacite_meta: dict):
        """_Create a new credentials object._

        Args:
            datacite_meta (dict): _The required DataCite authentication metadata for logging in to the DOI minting system._
        """        
        assert isinstance(
            datacite_meta, dict
        ), "You must pass a `dict` as the metatdata."
        assert all(
            [i in datacite_meta.keys() for i in ["user", "mode"]]
        ), "Your client metadata must be a dict with the keys `user`, and `mode`."
        assert all(
            [i in datacite_meta.get("mode").keys() for i in ["test", "prod"]]
        ), "You must have production and test data in your client credentials."
        self.data = datacite_meta

    def mode(self, mode: testMode = testMode.test):
        """_Change the interaction mode for the DOI system._

        Args:
            mode (testMode, optional): _Change or set the mode for DOI interaction_. Defaults to testMode.test.

        Returns:
            _type_: _Returns the DOI interaction mode._
        """        
        output = self.data.get("mode").get(mode.name)
        output["username"] = self.data.get("user")
        return output
