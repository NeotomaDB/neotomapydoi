[![lifecycle](https://img.shields.io/badge/lifecycle-active-orange.svg)]
[![NSF-2410961](https://img.shields.io/badge/NSF-2410961-blue.svg)](https://nsf.gov/awardsearch/showAward?AWD_ID=2410961)
[![OpenSSF Best Practices](https://www.bestpractices.dev/projects/11102/badge)](https://www.bestpractices.dev/projects/11102)

# `neotomapydoi`: Minting and Managing Neotoma PIDs

Neotoma stores information about tens of thousands of datasets around the world, including spatial, temporal and observational data about the taxa, chemistry and physical properties of the samples found in these sedimentary archives. These records are exposed through the Neotoma R package ([`neotoma2`](https::/github.com/NeotomaDB/neotoma2)), the [Neotoma API](https://api.neotomadb.org), [Neotoma Explorer](https://apps.neotomadb.org/explorer), and, more broadly, through their Digial Object identifiers (DOIs).

DOIs managed by DataCite have a [defined metadata schema](https://schema.datacite.org/), which allows Neotoma to provide dataset terms in a form that can be easily searched and returned by users around the globe, without the need for detailled knowledge about Neotoma or its database schema. The DOIs (e.g., [https://doi.org/10.21233/znex-sp94](https://doi.org/10.21233/znex-sp94)) return users to the Neotoma Landing Pages, where they can download records in JSON format and examine additional metadata about the records.

## Development

* [Simon Goring](http://goring.org): University of Wisconsin - Madison [![orcid](https://img.shields.io/badge/orcid-0000--0002--2700--4605-brightgreen.svg)](https://orcid.org/0000-0002-2700-4605)

## Contribution

We welcome user contributions to this project.  All contributors are expected to follow the [code of conduct](code_of_conduct.md). Contribution guidelines can be found in the [Contributing](CONTRIBUTING.md) document. Contributors should fork this project and make a pull request indicating the nature of the changes and the intended utility.  Further information for this workflow can be found on the GitHub [Pull Request Tutorial webpage](https://help.github.com/articles/about-pull-requests/).

## Using `neotomadoi`

### Requirements

* Python 3.12 in a Linux environment.
* A valid connection to the Neotoma Paleoecology Database, either in the cloud (AWS) or locally (see the Neotoma Snapshot documentation)
* All packages as defined in the `pyproject.toml` file (use `uv` and the `uv install` command)
* Valid DataCite credentials

### Credential Storage

All credentials should be stored within a `.env` file. We provide [`.env-template`](.env-template) as an example. The user should modify this file to reflect their own credentials and connection strings for these environment variables.