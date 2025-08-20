import pandas as pd
from coord_tranformation import rade2azel
from pathlib import Path
from datetime import datetime
import matplotlib.pyplot as plt
import numpy as np


def run(sources, stations, start, end, out):
    df_sta = pd.read_csv("../CATALOGS/position.cat", comment="*", header=None, sep="\s+",
                         names="ID Name X Y Z Occ.Code lon lat Origin".split(), index_col="Name", usecols=range(8))
    df_sta["lon"] = 360 - df_sta["lon"]
    df_sta = df_sta.loc[df_sta.index.isin(stations)]

    df_src = pd.read_csv(sources, comment="*", header=None, usecols=range(10),
                         names="Name Name2 ra_h ra_m ra_s de_d de_m de_s 2000.0 0.0 type".split(), sep="\s+",
                         index_col="Name2")
    df_src["ra"] = (df_src["ra_h"] + df_src["ra_m"] / 60 + df_src["ra_s"] / 3600) * 15
    df_src["de"] = df_src["de_d"] + df_src["de_m"] / 60 + df_src["de_s"] / 3600

    time = pd.date_range(start=start, end=end, freq="min")
    unix_time = time.astype('int64') // 10 ** 9  # nanoseconds to seconds
    mjd = unix_time / 86400 + 40587
    mjd_series = pd.Series(mjd, index=time)
    out.mkdir(exist_ok=True, parents=True)

    for src in df_src.index:
        ra = np.radians(df_src.loc[src]["ra"])
        de = np.radians(df_src.loc[src]["de"])

        plt.figure()
        for y, sta in enumerate(df_sta.index):
            c = np.full(time.shape, np.nan)
            lat = np.radians(df_sta.loc[sta, "lat"])
            lon = np.radians(df_sta.loc[sta, "lon"])
            for i, mjd in enumerate(mjd_series.values):
                az, el = rade2azel(mjd, lat, lon, ra, de)
                el = np.degrees(el)
                if el > 5:
                    c[i] = el
            plt.scatter(time, np.full(time.shape, y), marker="o", c=c, vmin=0, vmax=90)
        plt.yticks(range(len(df_sta.index)), labels=df_sta.index)
        plt.xticks(rotation=90)
        plt.ylim(-0.5, len(df_sta.index) - 0.5)
        plt.grid(True, axis="x", color="gray", alpha=0.5)
        plt.colorbar(label="elevation [deg]")
        plt.title(f"{src} ({df_src.loc[src, 'Name']})")
        plt.tight_layout()
        plt.savefig(out / f"{src}.png", dpi=300)
        pass


if __name__ == "__main__":
    sources = Path('/scratch/programming/CATALOGS/Genesis/source.cat')

    # stations = ["GGAO12M", "MACGO12M", "RAEGSMAR", "WESTFORD", "ONSA13NE", "ONSA13SW", "WETTZ13N", "WETTZ13S"]
    # start = datetime(2025,7,31, 15,00,00)
    # end = datetime(2025,7,31, 15,30,00)
    # out = Path('/scratch/programming/CATALOGS/Genesis/gt501a')
    # run(sources, stations, start, end, out)

    sources = Path('/scratch/programming/CATALOGS/Genesis/source_south.cat')
    stations = "HARTVGS MATERAVG NYALE13N NYALE13S ONSA13NE ONSA13SW RAEGSMAR RAEGYEB WETTZ13N WETTZ13S".split()
    start = datetime(2025, 7, 31, 10, 00, 00)
    end = datetime(2025, 7, 31, 10, 30, 00)
    out = Path('/scratch/programming/CATALOGS/Genesis/gt501b')
    run(sources, stations, start, end, out)

    # sources = Path('/scratch/programming/CATALOGS/Genesis/source_south.cat')
    # stations = "HOBART12 ISHIOKA KATH12M KOKEE12M SESHAN13 TIANMA13 URUMQI13 YARRA12M ONSA13NE ONSA13SW WETTZ13N WETTZ13S".split()
    # start = datetime(2025, 7, 31, 2, 00, 00)
    # end = datetime(2025, 7, 31, 2, 30, 00)
    # out = Path('/scratch/programming/CATALOGS/Genesis/gt501c')
    # run(sources, stations, start, end, out)
