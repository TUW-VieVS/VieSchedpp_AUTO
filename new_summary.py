import argparse
from pathlib import Path
import shutil
import pandas as pd

def start(path_main):
    shutil.copy(path_main / "summary.txt", path_main / "summary.txt.old_format")
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
        l = df.loc[df["version"] == v,:]
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
