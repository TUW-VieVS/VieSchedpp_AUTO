import configparser
import datetime
import shutil
from collections import defaultdict
from gettext import translation
from itertools import combinations, product
from pathlib import Path
import requests
import numpy as np
import pandas as pd
import healpy as hp
from string import ascii_uppercase
from util.coord_tranformation import rade2azel

from lxml import etree

from Helper import read_master, antennaLookupTable, Message, read_sources
from XML_manipulation import insert_station_setup_with_time, add_parameter, insert_setup_node, add_group
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch


def add_downtime_intensives(**kwargs):
    """
    add down time based on IVS intensive schedule master

    it will extend the downtime based on entries in setting.ini file

    :param kwargs: mandatory keyword-arguments: "tree", "session"
    :return: None
    """

    Message.addMessage("Look for Intensive downtime")
    settings = configparser.ConfigParser()
    settings.read("settings.ini")

    tree = kwargs["tree"]
    session = kwargs["session"]

    if settings.has_section("general"):
        pad = settings["general"].getint("ivs_int_downtime_extra_min", 10)
    else:
        pad = 10

    year = session["date"].year
    if year < 2023:
        master_ivs = Path("MASTER") / f"master{year % 100:02d}-int.txt"
    else:
        master_ivs = Path("MASTER") / f"master{year:04d}-int.txt"

    intensives = read_master([master_ivs])
    s_start = session["date"]
    s_end = session["date"] + datetime.timedelta(hours=session["duration"])
    for int in intensives:
        int_start = int["date"] - datetime.timedelta(minutes=pad)
        int_end = int["date"] + datetime.timedelta(hours=int["duration"]) + datetime.timedelta(minutes=pad)

        for sta in int["stations"]:
            if sta in session["stations"]:
                insert_station_setup_with_time(int_start, int_end, s_start, s_end, session, tree, sta, "down",
                                               int["name"])


def vgos_int_s(**kwargs):
    tree = kwargs["tree"]
    session = kwargs["session"]
    folder = kwargs["folder"]
    outdir = kwargs["outdir"]

    stations = {"WETTZ13S": {"name": "WETTZ13S", "lon": 12.88, "lat": 49.15},
                "MACGO12M": {"name": "MACGO12M", "lon": 255.99, "lat": 30.40}}

    sources = pd.read_csv("Templates/VGOS-INT-S/source.cat.vgoss", delim_whitespace=True, header=None, comment="*")
    sources.columns = ["name", "name2", "ra_h", "ra_m", "ra_s", "de_d", "de_m", "de_s", "a1", "a2", "a3", "a4"]
    sources["ra"] = sources["ra_h"] + sources["ra_m"] / 60 + sources["ra_s"] / 3600
    sources["de"] = sources["de_d"] + sources["de_m"] / 60 + sources["de_s"] / 3600

    mjd_2000_01_01 = 51544
    delta_days = session["date"] - datetime.datetime(2000, 1, 1)
    mjd = mjd_2000_01_01 + delta_days.total_seconds() / 86400

    def zazel_s(mjd, lon, lat, ra, de):
        tu = mjd - 51544.5
        frac = mjd - np.floor(mjd) + 0.5
        fac = 0.00273781191135448
        era = 2 * np.pi * (frac + 0.7790572732640 + fac * tu)
        era = np.mod(era, 2 * np.pi)

        # source vector CRF
        sid = np.sin(de)
        cod = np.cos(de)
        sir = np.sin(ra)
        cor = np.cos(ra)

        q = np.array([cod * cor, cod * sir, sid]).T

        # rotation matrix for rotation around z-axis
        caEra = np.cos(-era)
        siEra = np.sin(-era)

        t2c = np.array([[caEra, -siEra, 0], [siEra, caEra, 0], [0, 0, 1]])

        # source in TRS (c2t = t2c')
        rq = np.dot(t2c, q)

        # source in local system
        coLat = np.cos(np.pi / 2 - lat)
        siLat = np.sin(np.pi / 2 - lat)
        coLon = np.cos(lon)
        siLon = np.sin(lon)

        g2l = np.dot(np.array([[coLat, 0, -siLat], [0, -1, 0], [siLat, 0, coLat]]),
                     np.array([[coLon, siLon, 0], [-siLon, coLon, 0], [0, 0, 1]]))
        lq = np.dot(g2l, rq)

        zd = np.arccos(lq[2])
        el = np.pi / 2 - zd
        saz = np.arctan2(lq[1], lq[0])
        saz += (np.pi * 2) if saz < 0 else 0
        az = saz + np.pi
        az = np.mod(az, np.pi * 2)

        return (az, el)

    high_els = dict()
    for sta_name, station in stations.items():
        tmp = []
        for _, s in sources.iterrows():
            name = s["name"]
            ra = s["ra"] * 15 * np.pi / 180
            de = s["de"] * np.pi / 180
            az, el = zazel_s(mjd, station["lon"] * np.pi / 180, station["lat"] * np.pi / 180, ra, de)
            el = el * 180 / np.pi
            if el > 60:
                tmp.append((name, el))
            pass
        tmp = [k[0] for idx, k in enumerate(sorted(tmp, reverse=True, key=lambda x: x[1])) if
               (k[1] > 70 and idx < 7) or idx < 7]
        high_els[sta_name] = tmp

    mg_txt = [f"<member>{name}</member>" for name in high_els["MACGO12M"]]
    ws_txt = [f"<member>{name}</member>" for name in high_els["WETTZ13S"]]

    notes = tree.find("./output/notes")
    notes.text += f"Special high/low elevation scan mode used\\n"
    notes.text += f" - number of high elevation sources for MACGO12M: {len(high_els['MACGO12M'])}\\n"
    notes.text += f" - number of high elevation sources for WETTZ13S: {len(high_els['WETTZ13S'])}\\n\\n"


    # Find groups
    for group in tree.xpath("//group"):
        if group.get("name") == "high_el_Mg":
            group.text = ""  # Clear the placeholder text
            for member in mg_txt:
                group.append(etree.fromstring(member))  # Append members

        elif group.get("name") == "high_el_Ws":
            group.text = ""  # Clear the placeholder text
            for member in ws_txt:
                group.append(etree.fromstring(member))  # Append members


def retrieve_starlink_satellites(**kwargs):
    tree = kwargs["tree"]
    session = kwargs["session"]
    folder = kwargs["folder"]
    outdir = kwargs["outdir"]

    start_time = session["date"]
    end_time = start_time + datetime.timedelta(hours=session["duration"])

    url = 'https://satdb.ethz.ch/api/satellitedata'
    params = {
        'start-datetime': f"{start_time:%Y%m%dT%H%M}",
        'end-datetime': f"{end_time:%Y%m%dT%H%M}",
        'before': 14,
        'after': 7,
        'without-frequency-data': False,
        'frequency-list': "[10.7-10.8]",
    }
    Message.addMessage(f"\nDownloading satellite file (currently not applied)\n", dump="session")

    outfile = outdir / "satellites.tle"
    with open(outfile, "w") as f:
        try:
            # initial request
            response = requests.get(url, params)
            next, results = response.json()['next'], response.json()['results']
            f.write('\n'.join(item['norad_str'] for item in results))

            # make next request
            while next != None:
                response = requests.get(next)
                results = response.json()['results']
                f.write('\n')
                f.write('\n'.join(item['norad_str'] for item in results))
                next = response.json()['next']
        except Exception as e:
            Message.addMessage(f"ERROR downloading satellite file:\n    {e}\n", dump="session")

    # tree.find("./catalogs/satellite_avoid").text = str(outfile.resolve())


def adjust_INT_observing_mode_VLBA_256_8_RDV(**kwargs):
    tree = kwargs["tree"]
    session = kwargs["session"]
    folder = kwargs["folder"]

    flag_VLBA = any(["VLBA" in sta or "PIETOWN" in sta for sta in session["stations"]])

    if flag_VLBA:
        mode = "256-8(RDV)"
        tree.find("./mode/skdMode").text = mode
        # catalogs to absolut path
        tree.find("./catalogs/freq").text = str((folder / "freq.cat").resolve())
        tree.find("./catalogs/rx").text = str((folder / "./rx.cat").resolve())
        tree.find("./catalogs/tracks").text = str((folder / "./tracks.cat").resolve())

        Message.addMessage(f"Changing observing mode to \"{mode}\"")
        Message.addMessage("Changing freq, tracks and rx catalogs")


def adjust_INT1_observing_mode(**kwargs):
    tree = kwargs["tree"]
    session = kwargs["session"]
    folder = kwargs["folder"]


    flag = "ISHIOKA" in session["stations"]

    if flag:
        tree.find("./catalogs/rec").text = str((folder / "./rec.cat").resolve())
        Message.addMessage("Changing rec cat to include ISHIOKA")


def adjust_R1_observing_mode(**kwargs):
    """
    change target SNR based on baseline sensitivity

    :param kwargs: mandatory keyword-arguments: "tree", "session"
    :return: None
    """
    tree = kwargs["tree"]
    session = kwargs["session"]
    mediamaster = Path("MASTER") / f"mediamaster{session['date'].year % 100:02d}.txt"
    if not mediamaster.is_file():
        mediamaster = Path("MASTER") / f"mediamaster{session['date'].year :d}.txt"

    flag_512 = False
    with open(mediamaster) as f:
        for l in f:
            l = l.strip()
            if l.startswith("|"):
                l = l.strip("|")
                code = l.split("|")[2].strip()
                if code == session["name"]:
                    stations = l.split("|")[6]
                    stations = stations.split()[0]
                    stations = [stations[i:i + 4] for i in range(0, len(stations), 4)]
                    g_module = sum(sta[3] == "G" for sta in stations)
                    if g_module == len(stations):
                        flag_512 = True
                    elif g_module > 0:
                        Message.addMessage(f"WARNING: undefined observing mode! {g_module:d} stations with 512 Mbps, "
                                           f"{len(stations) - g_module:d} stations with 256 Mbps. Defaulting to 256 "
                                           f"Mbps",
                                           dump="header")
                    break

    if flag_512:
        mode = "512-16(CONT11)"
        tree.find("./mode/skdMode").text = mode
        Message.addMessage(f"Changing observing mode to \"{mode}\"")


def sefd_based_snr(**kwargs):
    """
    change target SNR based on baseline sensitivity

    :param kwargs: mandatory keyword-arguments: "tree", "session"
    :return: None
    """
    tree = kwargs["tree"]
    session = kwargs["session"]

    high_high, high_low, low_low = get_baseline_sensitivity_groups(session["stations"])
    add_group(tree.find("./baseline"), "high_high", high_high)
    add_group(tree.find("./baseline"), "high_low", high_low)
    add_group(tree.find("./baseline"), "low_low", low_low)

    notes = tree.find("./output/notes")
    notes.text += f"Adjust target SNR based on station SEFDs\\n"
    notes.text += f" - number of high-high SEFD baselines {len(high_high):2d}: (low SNR target)\\n"
    notes.text += f" - number of high-low  SEFD baselines {len(high_low):2d}: (mid SNR target)\\n"
    notes.text += f" - number of low-low   SEFD baselines {len(low_low):2d}: (high SNR target)\\n\\n"


    Message.addMessage("add baseline SEFD based SNR targets")
    Message.addMessage(f"    new baseline group \"{'high_high':2}\" with {len(high_high):d} members")
    Message.addMessage(f"    new baseline group \"{'high_low':2}\" with {len(high_low):d} members")
    Message.addMessage(f"    new baseline group \"{'low_low':2}\" with {len(low_low):d} members")

    add_parameter(tree.find("./baseline/parameters"), "low_snr", ["minSNR", "minSNR"], ["18", "13"],
                  [("band", "X"), ("band", "S")])
    add_parameter(tree.find("./baseline/parameters"), "mid_snr", ["minSNR", "minSNR"], ["20", "15"],
                  [("band", "X"), ("band", "S")])
    add_parameter(tree.find("./baseline/parameters"), "high_snr", ["minSNR", "minSNR"], ["22", "17"],
                  [("band", "X"), ("band", "S")])

    insert_setup_node(session, "high_high", tree.find("./baseline/setup"), "low_snr", )
    insert_setup_node(session, "high_low", tree.find("./baseline/setup"), "mid_snr", )
    insert_setup_node(session, "low_low", tree.find("./baseline/setup"), "high_snr", )


def vgos_ops_magic(**kwargs):
    tree = kwargs["tree"]
    session = kwargs["session"]
    folder = kwargs["folder"]
    outdir = kwargs["outdir"]

    sources = VGOS_source(tree, folder, outdir, session, plot=True)
    _dummy_flux(tree, folder, outdir, session, sources)
    VGOS_src_groups(tree, sources)

    VGOS_sta_setup(tree, session)
    VGOS_sites(tree, session["stations"])
    VGOS_calib(tree, session)


def VGOS_src_groups(tree, sources):
    root = tree.getroot()
    groups = root.find("source/groups")  # XPath, in case it's nested

    for grp in ["core", "good", "test"]:
        type_group = etree.SubElement(groups, "group", name=grp)
        type = sources.loc[sources["type"].str.contains(grp, case=False)]
        for name in type["name2"]:
            etree.SubElement(type_group, "member").text = name

        for loc, type_loc in zip(["northern", "southern"],
                                 [type.loc[type["de_deg"] >= -15], type.loc[type["de_deg"] < -15]]):
            type_loc_group = etree.SubElement(groups, "group", name=f"{grp}_{loc}")
            for name in type_loc["name2"]:
                etree.SubElement(type_loc_group, "member").text = name

            flux2name = {
                "VGOS": "vgos_flux",
                "SX": "sx_flux",
                "NONE": "no_flux",
            }
            for flux in ["VGOS", "SX", "NONE"]:
                type_loc_flux_group = etree.SubElement(groups, "group", name=f"{grp}_{loc}_{flux2name[flux]}")
                type_loc_flux = type_loc.loc[type_loc["flux"] == flux]
                for name in type_loc_flux["name2"]:
                    etree.SubElement(type_loc_flux_group, "member").text = name
                pass

    for grp in ["calib1", "calib2", "test"]:
        type_group = etree.SubElement(groups, "group", name=grp)
        type = sources.loc[sources["type"].str.contains(grp, case=False)]
        for name in type["name2"]:
            etree.SubElement(type_group, "member").text = name
    pass


def VGOS_sta_setup(tree, session):
    stations = session["stations"]
    sta2equip = {}
    slow = ["GGAO12M", "WESTFORD", "MACGO12M", "KOKEE12M"]

    notes = tree.find("./output/notes")
    notes.text += f"The following stations require buffer-flush time (4 Gbps data write speed instead of 8 Gbps):\\n"

    with open("CATALOGS_VieSchedpp/equip.cat.vgos") as f:
        for l in f:
            l = l.strip()
            if l.startswith("*"):
                continue
            sta = l.split()[0]
            equip = l.split()[-1]
            if sta in stations:
                # hard-coded MARK6 for American stations
                if sta in slow:
                    sta2equip[sta] = "MARK6"
                else:
                    sta2equip[sta] = "FLEXBUFF"
                # sta2equip[sta] = equip

    root = tree.getroot()
    station_node = root.find("station")  # XPath, in case it's nested
    setup_node = station_node.find("setup")  # XPath, in case it's nested
    for station, equip in sta2equip.items():
        if equip.upper() in ["MARK6", "MARK5B"]:
            setup = etree.SubElement(setup_node, "setup")
            etree.SubElement(setup, "member").text = station
            etree.SubElement(setup, "parameter").text = "buffer_flush"
            etree.SubElement(setup, "transition").text = "hard"
            notes.text += f" - {station}\\n"

    notes.text += f"\\n"
    pass


def VGOS_calib(tree, session):
    # source 4C39.25
    ra = 2.474223394708588
    de = 0.68136127710676

    # station positions
    stations = pd.read_csv("CATALOGS/position.cat", comment="*", header=None,
                           usecols=[1, 6, 7], names=["name", "lon", "lat"], sep="\s+")
    stations["lon"] = 360 - stations["lon"]
    stations.set_index("name", inplace=True)
    stations = stations.loc[session["stations"]]
    stations["lon_rad"] = np.radians(stations["lon"])
    stations["lat_rad"] = np.radians(stations["lat"])

    # extract potential times for calibration scans to 4C39.25
    start = session["date"]
    duration = datetime.timedelta(hours=session["duration"])
    end = start + duration
    index = pd.date_range(start=start, end=end, freq="15min", inclusive="neither")
    index = index[index.minute != 0]

    # save elevation of all stations (in case > 10 deg)
    df = pd.DataFrame(index=index, columns=stations.index)
    for ts in index:
        jd = ts.to_julian_date()
        mjd = jd - 2400000.5

        for sta, s in stations.iterrows():
            lon = s["lon_rad"]
            lat = s["lat_rad"]
            az, el = rade2azel(mjd, lat, lon, ra, de)
            el = np.degrees(el)
            if el > 5:
                df.loc[ts, sta] = el
            pass
        pass
    df = df.dropna(how="all", axis=1)

    best_pair = None
    best_non_nan_count = -1
    best_min_value = -np.inf

    # Iterate over all unique pairs of rows
    for i, j in combinations(df.index, 2):
        row1 = df.loc[i]
        row2 = df.loc[j]

        # Combine rows with priority to non-NaN
        combined = row1.combine_first(row2)  # row1 if not NaN, else row2

        # Check rule 1: each column must have at least one non-NaN
        if combined.isna().any():
            continue  # skip if any column is still NaN

        # Rule 2: count total non-NaN values in both rows
        total_non_nan = row1.notna().sum() + row2.notna().sum()

        # Rule 3: calculate minimal value across combined non-NaNs
        min_value = combined.min()

        # Apply rule 2 and 3 to select best
        if (total_non_nan > best_non_nan_count or
                (total_non_nan == best_non_nan_count and min_value > best_min_value)):
            best_pair = (i, j)
            best_non_nan_count = total_non_nan
            best_min_value = min_value

    if best_pair:
        times_4C39p25 = [int((best_pair[0] - start).total_seconds()), int((best_pair[1] - start).total_seconds())]
    else:
        times_4C39p25 = []

    notes = tree.find("./output/notes")
    notes.text += (f"CALIBRATION blocks every full hour\\n"
                   f" - every 3 hours: 120-second long scans to CALIB2 source list (for imaging calibration) \\n"
                   f" - every other block: 30-second long scans to CALIB1 source list (for correlation and fringe finders) \\n"
                   f" - two special scans to 4C39.25 (for cross-polarization bandpass calibration - at {best_pair[0]} and {best_pair[1]})\\n\\n")

    dur_seconds = int(duration.total_seconds())
    calib = sorted(list(set(times_4C39p25 + list(range(1 * 3600, dur_seconds, 1 * 3600)))))

    # add calibraiton blocks
    root = tree.getroot()
    rules = root.find("rules")
    calibration = etree.SubElement(rules, "calibration")

    for start_time in calib:
        block = etree.SubElement(calibration, "block")
        etree.SubElement(block, "startTime").text = str(start_time)

        if start_time in times_4C39p25:
            etree.SubElement(block, "scans").text = "1"
            etree.SubElement(block, "duration").text = "120"
            etree.SubElement(block, "sources").text = "4C39.25"
            etree.SubElement(block, "overlap").text = "0"
            etree.SubElement(block, "rigorosOverlap").text = "false"
        elif start_time % (3 * 3600) == 0:
            etree.SubElement(block, "scans").text = "3"
            etree.SubElement(block, "duration").text = "120"
            etree.SubElement(block, "sources").text = "calib2"
            etree.SubElement(block, "overlap").text = "1"
            etree.SubElement(block, "rigorosOverlap").text = "true"
        else:
            etree.SubElement(block, "scans").text = "3"
            etree.SubElement(block, "duration").text = "30"
            etree.SubElement(block, "sources").text = "calib1"
            etree.SubElement(block, "overlap").text = "2"
            etree.SubElement(block, "rigorosOverlap").text = "false"

    etree.SubElement(calibration, "tryToIncludeAllStations").text = "true"
    etree.SubElement(calibration, "tryToIncludeAllStations_factor").text = "3"
    etree.SubElement(calibration, "numberOfObservations_factor").text = "1"
    etree.SubElement(calibration, "numberOfObservations_offset").text = "0"
    etree.SubElement(calibration, "averageStations_factor").text = "2"
    etree.SubElement(calibration, "averageStations_offset").text = "1"
    etree.SubElement(calibration, "averageBaseline_factor").text = "0.5"
    etree.SubElement(calibration, "averageBaseline_offset").text = "1"
    etree.SubElement(calibration, "duration_factor").text = "0.20000000000000001"
    etree.SubElement(calibration, "duration_offset").text = "1"

    pass


def VGOS_sites(tree, station_list):
    joint = [("NYALE13N", "NYALE13S"),
             ("ONSA13NE", "ONSA13SW"),
             ("WETTZ13N", "WETTZ13S"),
             ("SESHAN13", "TIANMA13"),
             ]

    def generate_ids():
        for size in range(1, 3):  # Up to 2-letter IDs: A-Z, AA-ZZ
            for letters in product(ascii_uppercase, repeat=size):
                yield ''.join(letters)

    id_gen = generate_ids()

    root = tree.getroot()  # If you're parsing from file, use etree.parse()
    sites_elem = etree.SubElement(root, "sites")
    # === Process station list with joint logic ===
    processed = set()

    notes = tree.find("./output/notes")
    notes.text += f"The following stations are co-located and count as one site only:\\n"

    for name in station_list:
        if name in processed:
            continue

        # Check if part of a joint station
        found_joint = False
        for pair in joint:
            if name in pair:
                other = pair[1] if name == pair[0] else pair[0]
                if other in station_list:
                    site_elem = etree.SubElement(sites_elem, "site", ID=next(id_gen))
                    etree.SubElement(site_elem, "station").text = name
                    etree.SubElement(site_elem, "station").text = other
                    processed.update({name, other})
                    found_joint = True
                    notes.text += f" - {name} {other}\\n"

                    break

        if not found_joint:
            site_elem = etree.SubElement(sites_elem, "site", ID=next(id_gen))
            etree.SubElement(site_elem, "station").text = name
            processed.add(name)

    notes.text += f"\\n"
    pass


def VGOS_source(tree, folder, outdir, session, plot=True):
    # some helper functions:
    def read_srclist(path):
        df = pd.read_csv(path, header=None, dtype=str, comment="*", sep="\s+",
                         names="name name2 ra_h ra_m ra_s de_d de_m de_s 2000.0 0.0 type".split(),
                         index_col="name")
        df["sign_dec"] = df["de_d"].str.contains("-").replace({True: -1, False: 1})
        df["ra_deg"] = (df["ra_h"].astype(float) + df["ra_m"].astype(float) / 60 + df["ra_s"].astype(
            float) / 3600) * 15
        df["de_deg"] = df["sign_dec"] * (
                abs(df["de_d"].astype(float)) + df["de_m"].astype(float) / 60 + df["de_s"].astype(
            float) / 3600)
        df["ra"] = np.radians(df["ra_deg"])
        df['ra'] = np.where(df['ra'] > np.pi, df['ra'] - 2 * np.pi, df['ra'])
        df["de"] = np.radians(df["de_deg"])
        theta = np.pi / 2 - df["de"]  # colatitude
        phi = df['ra']  # longitude
        pix = hp.ang2pix(2, theta.values, phi.values)
        df["pix"] = pix
        return df

    def select_n(preselected, df, n, seed=42):
        selected = []
        for idx, tmp in df.groupby("pix"):
            if preselected is not None:
                n_grp = n - sum(preselected["pix"] == idx)
            else:
                n_grp = n
            items = tmp.sample(n=min(tmp.shape[0], n_grp), random_state=seed).index.to_list()
            selected += items
            pass
        return df.loc[selected, :]

    def select_calib(preselected, all):
        all = pd.concat(all)
        calib = all.loc[all["type"].str.contains("CALIB", case=False)]
        extra_calib = calib.loc[calib.index.difference(preselected.index)]
        extra_calib['type'] = extra_calib['type'].str.replace(r'_GOOD|_TEST|_CORE', '', regex=True)
        return extra_calib

    # read source lists
    core = read_srclist(folder / "source_core.cat")
    good = read_srclist(folder / "source_good.cat")
    test = read_srclist(folder / "source_test.cat")

    # select certain number of sources
    selected_good = select_n(None, good, 6, seed=int(session['date'].timestamp()))
    selected_test = select_n(selected_good, test, 7, seed=int(session['date'].timestamp()))

    sources = pd.concat([core, selected_good, selected_test])
    extra_calib = select_calib(sources, [core, good, test])
    sources = pd.concat([sources, extra_calib])

    notes = tree.find("./output/notes")
    notes.text += (f"Balanced sources selection:\\n"
                   f" - CORE list: {core.shape[0]} sources\\n"
                   f" - GOOD list: {selected_good.shape[0]} sources (from {good.shape[0]})\\n"
                   f" - TEST list: {selected_test.shape[0]} sources (from {test.shape[0]})\\n"
                   f" - plus an additional {extra_calib.shape[0]} sources for calibration purposes only\\n"
                   f"Note that not all of these 'selected' sources are also scheduled!\\n\\n")

    # write source list based on the selected sources
    with open(folder / f"source_{session['code']}.cat", "w") as f:
        f.write("* ========== CORE ========== \n")
        for name, s in core.iterrows():
            f.write(
                f"{name:<8s} {s['name2']:<8s}      {s['ra_h']:<3s} {s['ra_m']:<3s} {s['ra_s']:<12s}       {s['de_d']:>3s} {s['de_m']:<3s} {s['de_s']:<11s}     2000.0 0.0    {s['type']} \n")
        f.write("* ========== GOOD ========== \n")
        for name, s in selected_good.iterrows():
            f.write(
                f"{name:<8s} {s['name2']:<8s}      {s['ra_h']:<3s} {s['ra_m']:<3s} {s['ra_s']:<12s}       {s['de_d']:>3s} {s['de_m']:<3s} {s['de_s']:<11s}     2000.0 0.0    {s['type']} \n")
        f.write("* ========== TEST ========== \n")
        for name, s in selected_test.iterrows():
            f.write(
                f"{name:<8s} {s['name2']:<8s}      {s['ra_h']:<3s} {s['ra_m']:<3s} {s['ra_s']:<12s}       {s['de_d']:>3s} {s['de_m']:<3s} {s['de_s']:<11s}     2000.0 0.0    {s['type']} \n")
        f.write("* ========== EXTRA CALIB ========== \n")
        for name, s in extra_calib.iterrows():
            f.write(
                f"{name:<8s} {s['name2']:<8s}      {s['ra_h']:<3s} {s['ra_m']:<3s} {s['ra_s']:<12s}       {s['de_d']:>3s} {s['de_m']:<3s} {s['de_s']:<11s}     2000.0 0.0    {s['type']} \n")
    shutil.copy(folder / f"source_{session['code']}.cat", outdir / f"source_{session['code']}.cat")
    tree.find("./catalogs/source").text = str((outdir / f"source_{session['code']}.cat").resolve())

    if plot:
        # optional generate a plot of source selection
        def quickplot(df, title="sources", outpath=outdir):
            fig = plt.figure(figsize=(8, 4))
            fig.add_subplot(111, projection='mollweide')
            plt.grid(True)
            counters = defaultdict(int)
            for i, row in df.iterrows():
                marker = '*'
                size = 100 if 'DEF' in row['type'] else 30
                color = 'C0'  # default
                edgecolor = 'none'
                alpha = 0.5

                if 'DEF' not in row['type']:
                    marker = 'o'
                    counters["NORMAL"] += 1
                else:
                    counters[("DEF")] += 1

                if 'CALIB1' in row['type']:
                    color = 'C1'
                    counters["CALIB1"] += 1
                if 'CORE' in row['type']:
                    alpha = 1.0
                    edgecolor = 'black'
                    counters["CORE"] += 1
                if 'CALIB2' in row['type']:
                    color = 'C2'
                    counters["CALIB2"] += 1
                if 'CALIB1' in row['type'] and 'CALIB2' in row['type']:
                    color = "C3"
                if 'TEST' in row['type']:
                    color = "gray"
                    counters["TEST"] += 1
                if 'GOOD' in row['type']:
                    alpha = 1.0
                    counters["GOOD"] += 1
                counters["TOTAL"] += 1
                plt.scatter(row['ra'], row['de'], marker=marker, s=size, color=color, edgecolors=edgecolor,
                            linewidths=1, alpha=alpha)

            legend_elements = [
                Line2D([0], [0], marker='*', color='C0', label=f'DEF ({counters["DEF"]})', markersize=10,
                       linestyle='None'),
                Line2D([0], [0], marker='o', color='C0', label=f'STD ({counters["NORMAL"]})', markersize=6,
                       linestyle='None'),
                Patch(facecolor='C0', edgecolor='k', label=f'CORE ({counters["CORE"]})'),
                Patch(facecolor='C1', edgecolor='none', label=f'CALIB1 ({counters["CALIB1"]})'),
                Patch(facecolor='C0', edgecolor='none', label=f'GOOD ({counters["GOOD"]})', ),
                Patch(facecolor='C2', edgecolor='none', label=f'CALIB2 ({counters["CALIB2"]})'),
                Patch(facecolor='gray', edgecolor='none', label=f'TEST ({counters["TEST"]})', alpha=0.5),
                Patch(facecolor='C3', edgecolor='none', label=f'CALIB1&2'),
            ]
            plt.legend(handles=legend_elements, loc='upper center', bbox_to_anchor=(0.5, -0.05), ncol=4)
            plt.title(f"{title} ({counters['TOTAL']})")
            plt.tight_layout()
            plt.savefig(outpath, dpi=300)
            pass

        outpath = outdir / f"{session['code']}.png"
        quickplot(sources, f"{session['code']}", outpath)
        shutil.copy(outpath, folder / outpath.name)

    return sources


def _dummy_flux(tree, folder, outdir, session, sources):
    flux_cat = tree.find("./catalogs/flux").text

    all_names = sources.index.to_list() + sources["name2"].to_list()
    all_names = list(set(all_names))
    translation_table = {}
    for name, s in sources.iterrows():
        name2 = s["name2"]
        if name != name2:
            translation_table[name] = name2
        pass

    # generate flux catalogs
    def read_flux_cat(file):
        data = defaultdict(list)
        comments = []
        with open(file) as f:
            for l in f:
                l = l.strip()
                if not l or l.startswith("*"):
                    comments.append(l)
                    continue
                name = l.split()[0]
                data[name].append(l)
        return data, comments

    flux, comments = read_flux_cat(flux_cat)

    sources["flux"] = "NONE"
    n_none = 0
    with open(folder / f"flux_{session['code']}.cat", "w") as f:
        for comment in comments:
            f.write(comment + "\n")

        for src, ls in flux.items():
            if src in translation_table:
                src = translation_table[src]
            if src in all_names:
                idx = sources[sources["name2"] == src].index[0]
                if sorted([tmp.split()[1] for tmp in ls]) == ["A", "B", "C", "D"]:
                    sources.loc[idx, "flux"] = "VGOS"
                else:
                    sources.loc[idx, "flux"] = "SX"
                for l in ls:
                    f.write(l + "\n")

        f.write("* ========== DUMMY VALUES ========== \n")
        for src, s in sources.iterrows():
            if s["flux"] == "NONE":
                n_none += 1
                f.write(f"{src:<8s}  A   B   0.0  0.15  13000 * DUMMY VALUE\n")
                f.write(f"{src:<8s}  B   B   0.0  0.15  13000 * DUMMY VALUE\n")
                f.write(f"{src:<8s}  C   B   0.0  0.15  13000 * DUMMY VALUE\n")
                f.write(f"{src:<8s}  D   B   0.0  0.15  13000 * DUMMY VALUE\n")

    if n_none > 0:
        notes = tree.find("./output/notes")
        notes.text += (f" - {n_none} sources do not have a source flux density model -> add DUMMY model. \\n"
                       f" - these sources will be observed for 30-seconds straight. \\n\\n")

    shutil.copy(folder / f"flux_{session['code']}.cat", outdir / f"flux_{session['code']}.cat")
    tree.find("./catalogs/flux").text = str((outdir / f"flux_{session['code']}.cat").resolve())
    return


def prepare_source_list_crf(**kwargs):
    """
    prepare for CRF session

    :param kwargs: mandatory keyword-arguments: "tree", "session"
    :return: None
    """
    tree = kwargs["tree"]
    session = kwargs["session"]
    folder = kwargs["folder"]

    target, target_list, _ = read_sources(folder / "source.cat.target", session["name"])
    calib, calib_list, _ = read_sources(folder / "source.cat.calib", session["name"])
    add_group(tree.find("./source"), "target", target)
    add_group(tree.find("./source"), "calib", calib)

    source_list = folder / f"source.cat.{session['code']}"
    with open(source_list, 'w') as f:
        f.write("* targets:\n")
        for l in target_list:
            f.write(l + "\n")
        f.write("* calibrators:\n")
        for l in calib_list:
            f.write(l + "\n")

    tree.find("./catalogs/source").text = str(source_list.resolve())


def test_mode(**kwargs):
    """
    run in test mode (only one schedule per parameter file)

    :param kwargs: mandatory keyword-arguments: "tree"
    :return: None
    """
    tree = kwargs["tree"]
    for multisched in tree.findall("multisched"):
        for maxNumber in multisched.findall("maxNumber"):
            maxNumber.text = str(1)
            break
        else:
            etree.SubElement(multisched, "maxNumber").text = str(1)

        for genetic in multisched.findall("genetic"):
            for population_size in genetic.findall("population_size"):
                population_size.text = str(1)
                break
            else:
                etree.SubElement(genetic, "maxNumber").text = str(1)

            for population_size in genetic.findall("evolutions"):
                population_size.text = str(2)
                break
            else:
                etree.SubElement(genetic, "evolutions").text = str(2)


def get_baseline_sensitivity_groups(stations, threshold=5000):
    name2tlc = antennaLookupTable(True)
    high = []
    low = []
    with open("CATALOGS/equip.cat") as f:
        for l in f:
            l = l.strip()
            if not l or l.startswith("*"):
                continue
            l = list(filter(None, l.split()))
            name = l[0]
            if name in stations and len(l) > 8 and l[6].isnumeric() and l[8].isnumeric():
                tlc = name2tlc[name]
                SEFD1 = int(l[6])
                SEFD2 = int(l[8])
                if SEFD1 > threshold or SEFD2 > threshold:
                    high.append(tlc)
                else:
                    low.append(tlc)

    tlcs = [name2tlc[name] for name in stations]
    high_high = []
    high_low = []
    low_low = []
    for tlc1, tlc2 in combinations(tlcs, 2):
        tlc1_c = tlc1[0] + tlc1[1].lower()
        tlc2_c = tlc2[0] + tlc2[1].lower()

        if tlc1 in high and tlc2 in high:
            high_high.append(f"{tlc1_c}-{tlc2_c}")
        elif tlc1 in low and tlc2 in low:
            low_low.append(f"{tlc1_c}-{tlc2_c}")
        elif (tlc1 in high and tlc2 in low) or (tlc1 in low and tlc2 in high):
            high_low.append(f"{tlc1_c}-{tlc2_c}")

    return high_high, high_low, low_low
