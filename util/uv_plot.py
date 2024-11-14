import argparse
import matplotlib.pyplot as plt
import skd_parser.skd as skd_parser
from astropy.time import Time
from math import pi
from collections import defaultdict
from itertools import combinations
from pathlib import Path
import numpy as np
import datetime
from skd_parser.mask import Step
from math import sqrt

from util.coord_tranformation import rade2azel

DEG2RAD = pi / 180
RAD2DEG = 180 / pi

WARNING_FLUX = True


def calc_uv(gmst, ra, de, dx, dy, dz):
    gmst = gmst.value * 15 * DEG2RAD
    ha = gmst - ra

    sinHa = np.sin(ha)
    cosHa = np.cos(ha)
    cosDe = np.cos(de)
    sinDe = np.sin(de)

    u = dx * sinHa + dy * cosHa
    v = dz * cosDe + sinDe * (-dx * cosHa + dy * sinHa)
    return u, v


def run(skdFile, cutoff_el, min_sta, snr_x=None, snr_s=None, max_scan=None, rec_rate_x=None, rec_rate_s=None,
        no_obs=False, yellow=None, cyan=None):
    skd = skd_parser.skdParser(skdFile)
    skd.parse()
    if cutoff_el != "mask":
        cutoff_el = float(cutoff_el)
        for sta in skd.stations.stations:
            sta.mask = Step([0, cutoff_el, 360])
    if snr_x is not None:
        skd.snr["x"] = snr_x
    if snr_s is not None:
        skd.snr["s"] = snr_s
    if max_scan is not None:
        skd.maxscan = max_scan
    if rec_rate_x is not None:
        skd.data_rate["x"] = rec_rate_x
    if rec_rate_s is not None:
        skd.data_rate["s"] = rec_rate_s

    sources = defaultdict(list)
    for scan in skd.scans.scans:
        time = Time(scan.start_time, scale='utc')
        gmst = time.sidereal_time('mean', 'greenwich')
        srcname = scan.source.name
        ra = scan.source.ra
        de = scan.source.de
        for a, b in combinations(scan.observations.obs, 2):
            dx = a.station.x - b.station.x
            dy = a.station.y - b.station.y
            dz = a.station.z - b.station.z
            uv = calc_uv(gmst, ra, de, dx, dy, dz)
            sources[srcname].append((uv))
            pass
        pass

    all_visible = visibility(skd, sources, min_sta)

    out = Path(skdFile).parent / f"{Path(skdFile).stem}_uv"
    out.mkdir(exist_ok=True)
    for name, uv in sources.items():
        uvplot(name, uv, out, all_visible[name], cutoff_el, min_sta, skd, no_obs, yellow, cyan)


def visibility(skd, sources, min_sta):
    start = skd.scans.scans[0].start_time
    end = skd.scans.scans[-1].start_time
    date_list = [start + datetime.timedelta(seconds=x) for x in range(0, int((end - start).total_seconds()), 60)]
    t = Time(date_list)
    mjd = t.mjd
    gmst = t.sidereal_time('mean', 'greenwich')

    storage = defaultdict(lambda: defaultdict(list))

    for srcname in sources.keys():
        src = skd.sources.get_source_by_name(srcname)

        visible = {}
        el_storage = dict()
        az_storage = dict()
        for sta in skd.stations.stations:
            els = []
            azs = []
            flag = np.full(len(mjd), False)
            for i, m in enumerate(mjd):
                az, el = rade2azel(m, sta.lat, sta.lon, src.ra, src.de)
                bool = sta.mask.visible(az, el)
                if bool:
                    els.append(el)
                    azs.append(az)
                    flag[i] = True
                else:
                    els.append(np.nan)
                    azs.append(np.nan)
                    flag[i] = False
            visible[sta.name] = flag
            el_storage[sta.name] = els
            az_storage[sta.name] = azs

        for i in range(len(mjd)):
            flags = [f[i] for f in visible.values()]
            if sum(flags) < min_sta:
                for v in visible.values():
                    v[i] = False
        pass

        for a, b in combinations(skd.stations.stations, 2):
            flag = visible[a.name] & visible[b.name]
            n = sum(flag)

            dx = a.x - b.x
            dy = a.y - b.y
            dz = a.z - b.z
            u, v = calc_uv(gmst, src.ra, src.de, dx, dy, dz)
            u[~flag] = np.nan
            v[~flag] = np.nan
            good_snr = check_snr(skd, u, v, a, b, src, el_storage)

            storage[src.name][f"{a.name}--{b.name}"] += (u, v, good_snr)
        pass
    return storage


def check_snr(skd, us, vs, sta1, sta2, src, el_storage):
    el1s = el_storage[sta1.name]
    el2s = el_storage[sta2.name]

    equip_model_1 = sta1.equip
    equip_model_2 = sta2.equip
    t = skd.maxscan

    global WARNING_FLUX
    flux_model = src.flux
    flags = [np.nan for i in range(len(us))]
    for band in ["x", "s"]:
        rec = skd.data_rate[band]
        eta = skd.obs_mode_eta

        for i, (u, v, el1, el2) in enumerate(zip(us, vs, el1s, el2s)):
            if np.isnan(u) or np.isnan(el1) or np.isnan(el2):
                continue
            if flux_model is None:
                if WARNING_FLUX:
                    print(f"WARNING: No flux information - defaulting to 0.1 Jy (this message is only shown once)")
                    WARNING_FLUX = False
                f = 0.1
            else:
                f = flux_model.flux(band, (u, v))

            if f is None:
                if WARNING_FLUX:
                    print(f"WARNING: No flux information - defaulting to 0.1 Jy (this message is only shown once)")
                    WARNING_FLUX = False
                f = 0.1

            sefd1 = equip_model_1.sefd(band, el1)
            sefd2 = equip_model_2.sefd(band, el2)

            snr = eta * f / sqrt(sefd1 * sefd2) * sqrt(rec * 1e6 * t)
            if snr < skd.snr[band]:
                flags[i] = False
            else:
                flags[i] = True
        pass
    return flags


def uvplot(name, uv, outdir, all, cutoff_el, min_sta, skd, no_obs=False, yellow=None, cyan=None):
    if yellow is None:
        yellow = []
    if cyan is None:
        cyan = []

    fig, ax = plt.subplots(1, 1, figsize=(5, 5))
    ax.set_aspect('equal')
    ax.minorticks_on()

    u, v = zip(*uv)
    u = np.asarray(u)
    v = np.asarray(v)

    circle = plt.Circle((0, 0), 2 * 6.371, color="gray", fill=False)
    ax.add_patch(circle)
    if all is not None:
        for bl, (uall, vall, flag) in all.items():
            sta1 = bl.split("--")[0]
            sta2 = bl.split("--")[1]
            if sta1 in yellow or sta2 in yellow:
                plt.plot(uall / 1e6, vall / 1e6, 'y', alpha=.5, linewidth=5, zorder=0)
                plt.plot(-uall / 1e6, -vall / 1e6, 'y', alpha=.5, linewidth=5, zorder=0)
            if sta1 in cyan or sta2 in cyan:
                plt.plot(uall / 1e6, vall / 1e6, 'c', alpha=.5, linewidth=5, zorder=0)
                plt.plot(-uall / 1e6, -vall / 1e6, 'c', alpha=.5, linewidth=5, zorder=0)

            good_u = np.asarray([u if np.isnan(u) or f == True else np.nan for u, f in zip(uall, flag)])
            good_v = np.asarray([v if np.isnan(v) or f == True else np.nan for v, f in zip(vall, flag)])

            bad_u = np.asarray([u if np.isnan(u) or f == False else np.nan for u, f in zip(uall, flag)])
            bad_v = np.asarray([v if np.isnan(v) or f == False else np.nan for v, f in zip(vall, flag)])

            n = sum([1 for f in flag if ~np.isnan(f)])
            n_good = (~np.isnan(good_u)).sum()
            n_bad = (~np.isnan(bad_u)).sum()

            plt.plot(good_u / 1e6, good_v / 1e6, 'g', alpha=0.5, zorder=1)
            plt.plot(-good_u / 1e6, -good_v / 1e6, 'g', alpha=0.5, zorder=1)
            plt.plot(bad_u / 1e6, bad_v / 1e6, 'r', alpha=0.5, zorder=1)
            plt.plot(-bad_u / 1e6, -bad_v / 1e6, 'r', alpha=0.5, zorder=1)
    if not no_obs:
        plt.scatter(u / 1e6, v / 1e6, 10, 'k', zorder=2)
        plt.scatter(-u / 1e6, -v / 1e6, 10, 'k', zorder=2)

    plt.xlabel('u [1000 km]')
    plt.ylabel('v [1000 km]')
    plt.xlim([-13, 13])
    plt.ylim([-13, 13])
    plt.grid(True, which='major', color='gray', alpha=0.5)
    plt.grid(True, which='minor', color='gray', linestyle=":", alpha=0.25)

    plt.title(name)
    txt3 = f'{len(uv)} obs'

    txt = f'min sta/scan: {min_sta}\n' \
          f'min el: {cutoff_el}\n' \
          f"flux: model, sefd: model"

    txt2 = f"snr: X {skd.snr['x']:.0f}, S {skd.snr['s']:.0f}\n" \
           f"rec: X {skd.data_rate['x']:.0f}, S {skd.data_rate['s']:.0f} Mbps\n" \
           f"eta: {skd.obs_mode_eta:.4f}, t = {skd.maxscan} [s]"

    txt4_p1 = ""
    txt4_p2 = ""
    if yellow:
        txt4_p1 = "yellow:\n" + "\n".join(yellow)
    if cyan:
        txt4_p2 = "cyan:\n" + "\n".join(cyan)
    if yellow or cyan:
        plt.text(1.01, 0.99, "\n\n".join([txt4_p1, txt4_p2]), transform=ax.transAxes,
                 ha='left', va='top', fontsize=8)

    plt.text(0.01, -0.1, txt2, transform=ax.transAxes,
             ha='left', va='top', fontsize=8)
    plt.text(0.99, -0.1, txt, transform=ax.transAxes,
             ha='right', va='top', fontsize=8)
    if not no_obs:
        plt.text(0.99, 0.01, txt3, transform=ax.transAxes,
                 ha='right', va='bottom', fontsize=8)
    plt.tight_layout()
    plt.savefig(outdir / f'{name}.png', dpi=150)
    plt.close(fig)

    pass


if __name__ == "__main__":
    doc = "Plots a uv plot of all sources. The plots will be stored under path_to_skd/uv/*.png."

    parser = argparse.ArgumentParser(description=doc)
    parser.add_argument("-skd", help="path to input skd file")
    parser.add_argument("-ce", "--cutoff_el", help="cutoff elevation in degrees (default = from .skd file)",
                        default="mask")
    parser.add_argument("-sx", "--snr_x", help="target SNR for band X (default = from .skd file)", type=float,

                        default=None)
    parser.add_argument("-ss", "--snr_s", help="target SNR for band S (default = from .skd file)", type=float,
                        default=None)
    parser.add_argument("-t", "--scan_duration", help="max scan duration [s] (default = from .skd file)", type=float,
                        default=None)
    parser.add_argument("-eta", help="efficiency factor (default = from .skd file)", type=float, default=None)
    parser.add_argument("-rx", "--rec_rate_x", help="recording rate [Mbps] for band X (default = from .skd file)",
                        type=float, default=None)
    parser.add_argument("-rs", "--rec_rate_s", help="recording rate [Mbps] for band S (default = from .skd file)",
                        type=float, default=None)
    parser.add_argument("-m", "--min_sta", help="minimum number of stations per scan (default = 2)", default=2,
                        type=int)
    parser.add_argument("-no", "--no_observations", help="do not draw actual observations (default = False)",
                        action='store_true')
    parser.add_argument("-y", "--yellow", nargs="+", help="highlight stations in yellow (can be multiple)")
    parser.add_argument("-c", "--cyan", nargs="+", help="highlight stations in cyan (can be multiple)")

    args = parser.parse_args()
    run(args.skd, args.cutoff_el, args.min_sta, args.snr_x, args.snr_s, args.scan_duration,
        args.rec_rate_x, args.rec_rate_s, args.no_observations, args.yellow, args.cyan)
