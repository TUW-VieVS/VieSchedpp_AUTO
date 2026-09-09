from pathlib import Path
import skd_parser.skd as skd_parser
import numpy as np

def generate_table(skd_file, type):
    skd = skd_parser.skdParser(skd_file)
    skd.parse()

    if type == "el":
        outfile = skd_file.parent / f"{skd_file.stem}.el"
        keyword = "ELEVATION"

    elif type == "duration":
        outfile = skd_file.parent / f"{skd_file.stem}.skdsum"
        keyword = "DURATION"

    with open(outfile, "w") as f:

        f.write(f" Source      Start      {keyword}\n")
        f.write(" name     yyddd-hhmmss   ")
        stations = skd.stations
        for station in stations:
            f.write(f"{station.name2}  ")
        f.write("\n")

        for scan in skd.scans:
            srcname = scan.source.altname
            time = f"{scan.start_time:%y%j-%H%M%S}"
            f.write(f" {srcname:<8s} {time}|")

            for station in stations:
                for obs in scan.observations:
                    if obs.station == station:
                        if type == "el":
                            f.write(f"  {np.rad2deg(obs.el_start):2.0f}")
                        elif type == "duration":
                            f.write(f"{obs.duration:4d}")
                        break
                else:
                    f.write("    ")
            f.write("\n")
        pass


if __name__ == "__main__":
    file = Path("/home/schartner/programming/KOSMIC/campaigns/GC040/GC040B/gc040b.skd").absolute()
    generate_table(file, "el")
    generate_table(file, "duration")