import argparse

import requests
from pathlib import Path


# def download(url, path):
#     path.parent.mkdir(exist_ok=True, parents=True)
#
#     r = requests.get(url, stream=True)
#     if r.ok:
#         with open(path, 'wb') as f:
#             for ch in r:
#                 f.write(ch)


def run(cat):
    trans = dict()
    with open("IVS/IVS_SrcNamesTable.txt") as f:
        for l in f:
            if l.startswith("#"):
                continue
            ivs = l[:8].strip()
            iers = l[40:48].strip()
            if iers == "-" or iers == "":
                continue
            trans[iers] = ivs
            pass

    for n1, n2 in cat.items():
        if n1 in trans.keys() and trans[n1] != n2:
            print(f"rename {n1} to {trans[n1]}")
        if n1 in trans.keys() and trans[n1] == n2:
            print(f"{n1} is correctly named {trans[n1]}")
        if n1 not in trans.keys() and n2 != '$':
            print(f"missing entry for {n1} {n2}")

    pass


def parse_cat(file):
    cat = dict()
    with open(file) as f:
        for l in f:
            l = l.strip()
            if l.startswith('*'):
                continue
            tmp = l.split()
            n1 = tmp[0]
            n2 = tmp[1]
            cat[n1] = n2

    return cat


def parse_skd(file):
    cat = dict()
    read = False
    with open(file) as f:
        for l in f:
            l = l.strip()
            if l.startswith("$SOURCES"):
                read = True
                continue
            if read:
                if l.startswith('$'):
                    break
                if l.startswith('*'):
                    continue
                tmp = l.strip().split()
                n1 = tmp[0]
                n2 = tmp[1]
                cat[n1] = n2

    return cat


if __name__ == "__main__":
    doc = "Takes a schedule or source catalog and checks source names against the IVS translation table."

    parser = argparse.ArgumentParser(description=doc)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-skd', "--schedule", help="path to input .skd file")
    group.add_argument('-cat', "--catalog", help="path to input source catalog")
    args = parser.parse_args()

    if args.catalog is not None:
        cat = parse_cat(args.catalog)

    if args.schedule is not None:
        cat = parse_skd(args.schedule)

    print(f"found {len(cat)} sources")

    # download('https://cddis.nasa.gov/archive/vlbi/gsfc/ancillary/solve_apriori/IVS_SrcNamesTable.txt',
    #          Path('IVS') / 'IVS_SrcNamesTable.txt')

    run(cat)
