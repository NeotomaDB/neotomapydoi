
"""Neotoma DOI Minting Software

This script is used from the commandline to mint, or check DOIs minted by Neotoma using DataCite.

The tool accepts either a time period (e.g. 2 weeks) or a string of comma separated dataset
identifiers and then generates dataset metadata, and publishes, or tests the publishing of the
datasets to DataCite.

The program outputs log files for each DOI minted. They will report the dataset ID, the DOI, and
the metadata attached to the DOI. There is also an Error reporting log that is produced.

The script can be run as:

* `python ndbdoi.py -w 2 -m`
    * Generate DOI metadata for all datasets generated over the past two weeks (`-w 2`) and publish to DataCite (`-m`).
* `python ndbdoi.py -d 12,13,14 -t`
    * Generate DOI metadata for datasets (`-d 12,13,14`) using data from the holding tank (`-t`), but do not publish.
"""

import argparse
import json
import os
from datetime import UTC, datetime

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

import neotomadoi


def parse_args():
    """_Parse arguments if the script is run from the commandline._

    Returns:
        _type_: _description_
    """
    parser = argparse.ArgumentParser(prog = "neotomadoi",
                                    description = "A DataCite DOI minter for Neotoma.")
    parser.add_argument('-t', '--tank',
                        help='Use the Holding Tank (not Neotoma Proper).',
                        action = "store_true")
    parser.add_argument('-m', '--mint',
                        action = "store_true",
                        default = False,
                        help = 'Mint and publish the dataset. Without this flag the datasets will be tested in the DataCite Sandbox.')
    parser.add_argument('-v', '--version',
                        action='version',
                        version='%(prog)s 1.0',
                        help='Show the program\'s version number and exit.')
    parser.add_argument('-o', '--output',
                        default = 'minting',
                        nargs = 1,
                        type = str,
                        help = 'Provide an output file prefix for the minting report (including the log, errors and updates).')
    parser.add_argument('-u', '--update',
                        action = "store_true",
                        help = 'Update the DataCite Metadata if a DOI record exists already? (Default is False, records will not be updated)')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-w', '--weeks',
                        type = int,
                        default = 2,
                        nargs = 1,
                        help = 'Time lag in weeks for dataset minting.')
    group.add_argument('-d', '--datasets',
                        type = lambda x: [int(y) for y in x.split(',')],
                        nargs = 1,
                        help = 'Dataset id  (or comma separated ids) to be minted.')

    args = parser.parse_args()
    return args

def printargs(args):
    runstart = datetime.now(UTC).isoformat()
    print("*** Neotoma DOI Generator ***")
    print(f"Run beginning {runstart}")

    if args.tank:
        print(" * Running against the Neotoma Holding Tank")
    else:
        print(" * Running against the Neotoma Production Database")

    if args.mint:
        print(" * Datasets will be minted on DataCite")
    else:
        print(" * Datasets will be run against the DataCite Sandbox")
    if args.datasets:
        print(f" * User has defined datasets to be run against:\n\t\t{args.datasets}")


def main(args):
    runstart = datetime.now(UTC).isoformat()
    load_dotenv()

    DCITE = json.loads(os.getenv("DCITE"))

    # Define credentials and connect to Neotoma.
    datacite_meta = neotomadoi.credentials(DCITE)

    # Do we use Neotoma proper or the holding tank?
    if args.tank:
        con = neotomadoi.neo_connect(tank = True)
    else:
        con = neotomadoi.neo_connect(tank = False)

    if args.datasets:
        with open('src/neotomadoi/sql/ds_datasetids.sql') as file:
            query = file.read()
            datasetids = args.datasets[0]
    else:
        with open('src/neotomadoi/sql/ds_timeslice.sql') as file:
            query = file.read()
        with con.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            time = f'{args.weeks} WEEKS'
            cur.execute(query, {'interval': time})
            datasetids = cur.fetchall()
            datasetids = [i[0] for i in datasetids]

    _ = printargs(args)

    for i in datasetids:
        print(f"Working on {i}")
        new_doi = neotomadoi.neotomaDOI(datasetid=i, defaults="neotomadoi.yaml")
        new_doi.set_user(datacite_meta)
        if args.tank is False:
            new_doi.databaseProd_mode()
        if args.mint is True:
            new_doi.dataciteProd_mode()
        try:
            new_doi.update()
            _ = new_doi.validate()
            new_doi.get_activity()
            old_activity = len(new_doi.activity)
            if not new_doi.identifiers or args.update:
                new_doi.mint_doi()
                if old_activity == 0:
                    with open(f"{args.output[0]}_{runstart}_published.log", "a", encoding="UTF-8") as f:
                        new_doi.get_meta()
                        json.dump(
                            {"datasetid": i, "doi": new_doi.identifiers, "meta": new_doi.data},
                            f,
                        )
                        _ = f.write("\n")
                    print(f'  Minted new DOI: {new_doi.identifiers.get('identifier')}')
                elif old_activity > 0:
                    with open(f"{args.output[0]}_{runstart}_updated.log", "a", encoding="UTF-8") as f:
                        new_doi.get_meta()
                        json.dump(
                            {"datasetid": i, "doi": new_doi.identifiers, "meta": new_doi.data},
                            f,
                        )
                        _ = f.write("\n")
                    print(f'  Updated DOI: {new_doi.identifiers.get('identifier')}')
        except Exception as e:
            print("Whoops.")
            print(e)
            with open(f"{args.output[0]}_{runstart}_errored.log", "a", encoding="UTF-8") as f:
                json.dump({"datasetid": i, "error": str(e)}, f)
                _ = f.write("\n")

if __name__ == '__main__':
    args = parse_args()
else:
    # For testing in the Python environment:
    class args:
        tank = False
        mint = True
        weeks = [1]
        datasets = [[66173,66174,66175,66176]]
        output = 'minting'
        update = False

main(args)
