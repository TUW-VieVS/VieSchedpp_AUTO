import configparser
import datetime
from itertools import combinations
from pathlib import Path
import requests
import numpy as np
import pandas as pd

from lxml import etree

from Helper import read_master, antennaLookupTable, Message, read_sources
from XML_manipulation import insert_station_setup_with_time, add_parameter, insert_setup_node, add_group


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

    insert_setup_node(session, "high_high", tree.find("./baseline/setup"), "low_snr", tag="group")
    insert_setup_node(session, "high_low", tree.find("./baseline/setup"), "mid_snr", tag="group")
    insert_setup_node(session, "low_low", tree.find("./baseline/setup"), "high_snr", tag="group")


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
