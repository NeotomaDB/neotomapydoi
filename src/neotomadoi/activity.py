"""A module to track changes to an individual DOI, to manage versioning, and to provide some
summary functions to understand how the DOI metadata content has changed over time. This
module can be used outside the rest of the `neotomaDOI` class."""

from datetime import datetime

from requests import RequestException, get


class activity:
    """An activity component, to return past activity for a DOI object.

    This class contains metadata, from the DataCite Activities endpoint at
    [https://api.datacite.org/dois/{doi}/activities](). The activities endpoint is
    fully documented at [https://support.datacite.org/reference/get_activities]().

    Attributes:
        activity (dict): A dict representation of the JSON object returned from DataCite.

    """

    def __init__(self, doi: str):
        """_Create a new activity object._

        Example:
                >>> check = activity("10.21233/1qx3-a004")
                >>> check
                <activity class: 3 records - from: 2020-07-07/29/20 to 2025-05-05/07/25>
                >>> isinstance(check.activity, list)
                True

        Args:
            doi (str): _A valid DOI string._

        Raises:
            requests.RequestException: _Is DOI activity available for this object?_
        """
        url = f"https://api.datacite.org/dois/{doi}/activities"
        activities = get(url)
        if activities.status_code != 200:
            raise RequestException(f"Failed to obtain DOI activity: {activities.text}")
        response = activities.json()
        self.activity = response.get("data")

    def __repr__(self) -> str:
        """_Print output summary._

        Returns:
            _str_: _A high-level overview of the activity object for the particular doi._
        """
        dates = [
            datetime.strptime(
                i.get("attributes").get("prov:generatedAtTime"), "%Y-%m-%dT%H:%M:%S.%fZ"
            )
            for i in self.activity
        ]
        if dates == []:
            return "<activity class: No activity.>"
        else:
            return f"<activity class: {len(self.activity)} records - from: {min(dates).strftime('%Y-%m-%D')} to {max(dates).strftime('%Y-%m-%D')}>"

    def __len__(self) -> int:
        """_Get the number of times the DOI has been modified._

        Examples:
        >>> check = activity("10.21233/1qx3-a004")
        >>> len(check)
        3

        Returns:
            int: _The number of elements in the activity object._
        """
        return len(self.activity)
