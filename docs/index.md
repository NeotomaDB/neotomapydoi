# neotomadoi - DataCite Integration for Neotoma

## Commands

* `neotomadoi -w 2`: Mint DOIs for datasets added over the last two weeks.
* `neotomadoi -d 5463`: Check and validate metadata for dataset 5463 (but do not mint).
* `neotomadoi -d 5463 -m -o ds5463`: Mint (or update) the DOI for dataset 5463 and write out the report to a file starting `ds5463`.

For full documentation visit [our GitHub repository](https://github.com/NeotomaDB/netomapydoi).

# Neotoma DOI Service

This repository represents the Neotoma DOI service, for drafting, minting and managing DataCite Metadata. Within Neotoma the process for minting includes validating the data, creating a "frozen" version of the dataset, and then minting the dataset with DataCite and storing a local version of the DataCite metadata.

Because data in Neotoma does change over time, as new taxa are added, or as chronologies are built and added to datasets, the data within an individual record may change. The Neotoma Datacite integration also helps manage updates to findable metadata through the DataCite portal.

## DOIs Within Neotoma

The Neotoma Paleoecology Database uses `datasets` as a central data element. It is on the `dataset` that an individual DOI is minted. A dataset is located at a site (a lake, a bog, an archaeological dig), it is associated with a data type (pollen, charcoal, vertebrate fauna) and it contains a number of observations.

To preserve data in its original form, when a DOI is minted a JSON representation of the dataset is created and stored within the database. We call this *freezing* the dataset.
