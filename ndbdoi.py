
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
import traceback
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

def printargs(args, datasetids):
    runstart = datetime.now(UTC).isoformat()
    print("*** Neotoma DOI Generator ***")
    print(f"Run: {runstart}")
    print(f"Database: {'Tank' if args.tank else 'Production'}")
    print(f"DataCite: {'Production' if args.mint else 'Sandbox'}")
    print(f"Datasets: {len(datasetids)} to process")
    print("-" * 50)

def main(args):
    runstart = datetime.now(UTC).isoformat()
    load_dotenv()

    DCITE = json.loads(os.getenv("DCITE"))
    datacite_meta = neotomadoi.credentials(DCITE)

    # Do we use Neotoma proper or the holding tank?
    if args.tank:
        con = neotomadoi.neo_connect(tank = True)
    else:
        con = neotomadoi.neo_connect(tank = False)

    if args.datasets:
        datasetids = args.datasets[0]
    else:
        with open('src/neotomadoi/sql/ds_timeslice.sql') as file:
            query = file.read()
        with con.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            time = f'{args.weeks} WEEKS'
            cur.execute(query, {'interval': time})
            datasetids = cur.fetchall()
            datasetids = [i[0] for i in datasetids]

    _ = printargs(args, datasetids)

    for dataset_id in datasetids:
        try:
            # Create and configure DOI object
            doi_obj = neotomadoi.neotomaDOI(datasetid=dataset_id, defaults="neotomadoi.yaml")
            doi_obj.set_user(datacite_meta)

            if not args.tank:
                doi_obj.databaseProd_mode()
            if args.mint:
                doi_obj.dataciteProd_mode()

            # Update metadata
            doi_obj.update()

            # Mint or update
            if not doi_obj.identifiers or args.update:
                result = doi_obj.mint_doi()
                # Log based on action
                log_file = f"{args.output}_{runstart}_{result['action']}.log"
                with open(log_file, "a", encoding="UTF-8") as f:
                    json.dump({
                        "datasetid": dataset_id,
                        "doi": result['doi'],
                        "action": result['action'],
                        "version": result.get('new_version', result.get('version')),
                        "metadata": doi_obj.data
                    }, f)
                    f.write("\n")

                # Print result
                print(f"✓ Dataset {dataset_id}: {result['message']}")
            else:
                print(f"○ Dataset {dataset_id}: Skipped (already has DOI: {doi_obj.identifiers.get('identifier')})")

        except Exception as e:
            print(f"✗ Dataset {dataset_id}: Failed - {str(e)}")
            with open(f"{args.output}_{runstart}_errored.log", "a", encoding="UTF-8") as f:
                json.dump({
                    "datasetid": dataset_id,
                    "error": str(e),
                    "traceback": traceback.format_exc()  # Also log it
                }, f)
                f.write("\n")

    print("-" * 50)
    print("Processing complete")

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
