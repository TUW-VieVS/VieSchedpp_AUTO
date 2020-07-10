import configparser
import os
import datetime
from lxml import etree
from itertools import combinations

from Helper import readMaster, antennaLookupTable, Message
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

    year = session["date"].year % 100
    master_ivs = os.path.join("MASTER", "master{:02d}-int.txt".format(year))
    master_si = os.path.join("MASTER", "master{:02d}-int-SI.txt".format(year))
    intensives = readMaster([master_ivs, master_si])
    s_start = session["date"]
    s_end = session["date"] + datetime.timedelta(hours=session["duration"])
    for int in intensives:
        int_start = int["date"] - datetime.timedelta(minutes=pad)
        int_end = int["date"] + datetime.timedelta(hours=int["duration"]) + datetime.timedelta(minutes=pad)

        for sta in int["stations"]:
            if sta in session["stations"]:
                insert_station_setup_with_time(int_start, int_end, s_start, s_end, session, tree, sta, "down",
                                               int["name"])


def alternate_R1_observing_mode(**kwargs):
    """
    change target SNR based on baseline sensitivity

    :param kwargs: mandatory keyword-arguments: "tree", "session"
    :return: None
    """
    tree = kwargs["tree"]
    session = kwargs["session"]
    number = int(session["name"][-3:])
    if number % 2 == 1:
        mode = "512-16(CONT11)"
        tree.find("./mode/skdMode").text = mode
        Message.addMessage("Changing observing mode to \"{}\"".format(mode))


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
    Message.addMessage("    new baseline group \"{:2}\" with {:d} members".format("high_high", len(high_high)))
    Message.addMessage("    new baseline group \"{:2}\" with {:d} members".format("high_low", len(high_low)))
    Message.addMessage("    new baseline group \"{:2}\" with {:d} members".format("low_low", len(low_low)))

    add_parameter(tree.find("./baseline/parameters"), "low_snr", ["minSNR", "minSNR"], ["20", "15"],
                  [("band", "X"), ("band", "S")])
    add_parameter(tree.find("./baseline/parameters"), "mid_snr", ["minSNR", "minSNR"], ["22", "17"],
                  [("band", "X"), ("band", "S")])
    add_parameter(tree.find("./baseline/parameters"), "high_snr", ["minSNR", "minSNR"], ["25", "20"],
                  [("band", "X"), ("band", "S")])

    insert_setup_node(session, "high_high", tree.find("./baseline/setup"), "low_snr", tag="group")
    insert_setup_node(session, "high_low", tree.find("./baseline/setup"), "mid_snr", tag="group")
    insert_setup_node(session, "low_low", tree.find("./baseline/setup"), "high_snr", tag="group")


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
            high_high.append("{}-{}".format(tlc1_c, tlc2_c))
        elif tlc1 in low and tlc2 in low:
            low_low.append("{}-{}".format(tlc1_c, tlc2_c))
        elif (tlc1 in high and tlc2 in low) or (tlc1 in low and tlc2 in high):
            high_low.append("{}-{}".format(tlc1_c, tlc2_c))

    return high_high, high_low, low_low
