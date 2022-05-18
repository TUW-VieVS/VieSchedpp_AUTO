import argparse
from pathlib import Path
import pandas as pd


def check_time_table(folder):
    for f in folder.glob("*.time"):
        print(f"check {f}")
        df = pd.read_csv(f, delim_whitespace=True, header=None, comment="*")
        df.columns = ["scan", "source", "scan_start", "delay_start", "delay_end", "slew_start", "slew_end",
                      "idle_start", "idle_end", "preob_start", "preob_end", "obs_start", "obs_end", "scan_end", "slew"]

        for a, b in [("delay_end", "slew_start"), ("slew_end", "idle_start"), ("preob_end", "obs_start")]:
            flag = (df[a] == df[b]).all()
            if not flag:
                print(f"inconsistency between {a} and {b}")

        diff_slew = df["slew_end"] - df["slew_start"]
        flag_slew = ((diff_slew - df["slew"]).abs() <= 1).all()
        if not flag_slew:
            print(f"inconsistency between slew times")

        if (df["slew"] < 0).any():
            print(f"negative slew times")

        itms = ["delay_start", "delay_end", "slew_start", "slew_end", "idle_start", "idle_end", "preob_start",
                "preob_end", "obs_start", "obs_end"]
        for a, b in zip(itms[:-1], itms[1:]):
            flag = (df[b] < df[a]).all()
            if flag:
                print(f"{b} occurs before {a}")

        pass


if __name__ == "__main__":
    doc = "Checks all time table files in a given folder for inconsistencies."

    parser = argparse.ArgumentParser(description=doc)
    parser.add_argument("-f", "--folder", help="path to folder containing *.time files", required=True)
    args = parser.parse_args()

    folder = Path(args.folder)
    check_time_table(folder)
