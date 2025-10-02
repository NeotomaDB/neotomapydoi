import neotomadoi
from dotenv import load_dotenv
import os
import json
import psycopg2
import psycopg2.extras
import argparse

def parse_args():
    parser = argparse.ArgumentParser(prog = "neotomadoi",
                                    description = "A DataCite DOI minter for Neotoma.")
    parser.add_argument('-t', '--tank',
                        help='Use the Holding Tank (not Neotoma Proper).',
                        action="store_true")
    parser.add_argument('-m', '--mint',
                        action = "store_true",
                        default = False,
                        help = 'Mint and publish the dataset. Without this flag the datasets will be tested in the DataCite Sandbox.')
    parser.add_argument('-v', '--version',
                        action='version',
                        version='%(prog)s 1.0',
                        help='Show the program\'s version number and exit.')
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

def main(args):
    load_dotenv()

    DCITE = json.loads(os.getenv("DCITE"))

    # Define credentials and connect to Neotoma.
    datacite_meta = neotomadoi.credentials(DCITE)

    # Do we use Neotoma proper or the holding tank?
    if args.tank:
        con = neotomadoi.neo_connect(test=True)
    else:
        con = neotomadoi.neo_connect(test=False)

    if args.datasets:
        with open('src/neotomadoi/sql/ds_datasetids.sql', 'r') as file:
            query = file.read()
            datasetids = args.mintdataset[0]
    else:
        with open('src/neotomadoi/sql/ds_timeslice.sql', 'r') as file:
            query = file.read()
        with con.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            time = f'{args.weeks} WEEKS'
            cur.execute(query, {'interval': time})
            datasetids = cur.fetchall()
            datasetids = [i[0] for i in datasetids]

    print(args)

    for i in datasetids:
        print(f"Working on {i}")
        new_doi = neotomadoi.neotomaDOI(datasetid=i, defaults="neotomadoi.yaml")
        new_doi.set_user(datacite_meta)
        if not args.mint:
            print("Using test mode.")
            new_doi.dataciteTest_mode()
        else:
            print("Using production mode.")
            new_doi.dataciteProd_mode()
        if not args.tank:
            new_doi.databaseProd_mode()
        try:
            try:
                new_doi.update()
            except ValueError as e:
                if "critical" in str(e):
                    new_doi.freeze_data(con)
                    new_doi.update()
            _ = new_doi.validate()
            new_doi.get_activity()
            old_activity = len(new_doi.activity)
            new_doi.mint_doi(publish=args.mint)
            if old_activity == 0:
                with open("minting_dois.log", "a", encoding="UTF-8") as f:
                    new_doi.get_meta()
                    json.dump(
                        {"datasetid": i, "doi": new_doi.identifiers, "meta": new_doi.meta},
                        f,
                    )
                    _ = f.write("\n")
                print(f'  Minted new DOI: {new_doi.identifiers.get('identifier')}')
            elif old_activity > 0:
                with open("updating_dois.log", "a", encoding="UTF-8") as f:
                    new_doi.get_meta()
                    json.dump(
                        {"datasetid": i, "doi": new_doi.identifiers, "meta": new_doi.meta},
                        f,
                    )
                    _ = f.write("\n")
                print(f'  Updated DOI: {new_doi.identifiers.get('identifier')}')
        except Exception as e:
            print("Whoops.")
            print(e)
            with open("failing_dois.log", "a", encoding="UTF-8") as f:
                json.dump({"datasetid": i, "error": str(e)}, f)
                _ = f.write("\n")

if __name__ == '__main__':
    args = parse_args()
else:
    args = {'tank': False,
            'mint': False,
            'weeks': [1],
            'datasets': None}

main(args)