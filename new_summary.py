import argparse
import shutil
from pathlib import Path

import pandas as pd


def start(path_main):
    shutil.copy(path_main / "summary.txt", path_main / "summary.txt.old_format_5")
    ls = []
    names = []
    for p in path_main.iterdir():

        p = p / "selected"
        if not p.is_dir():
            continue
        if not (p / "email.txt").is_file():
            continue
        if not (p / "merged_statistics.csv").is_file():
            continue

        with open(p / "email.txt") as f:
            for l in f:
                if l.startswith("best version: "):
                    tmp = l.split(" ")[-1]
                    v = int(tmp[1:])
                    break

        df = pd.read_csv(p / "merged_statistics.csv")
        l = df.loc[df["version"] == v, :].copy()

        # number of observations per baseline
        tlcs = set()
        filter_col = [col for col in l if col.startswith('n_bl_obs_')]
        for col in filter_col:
            name = col.split("_")[-1]
            tlc1 = name[0:2]
            tlc2 = name[3:5]
            tlcs.add(tlc1)
            tlcs.add(tlc2)

        tlcs = "".join(tlcs)
        l["stations"] = tlcs

        ls.append(l)
        names.append(p.parent.stem)

    d = pd.concat(ls)
    d.index = names
    d.to_csv(path_main / "summary.txt")
    pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-p")

    args = parser.parse_args()
    path = Path(args.p)
    start(path)
