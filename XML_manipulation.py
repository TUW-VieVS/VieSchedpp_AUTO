import configparser
import datetime
import os
import re

from lxml import etree

from Helper import Message
from Helper import readMaster


def adjust_xml(template, session):
    """
    change template xml file with session specific entries
    
    :param template: path to xml template
    :param session: dictionary with session specific fields
    :return: adjusted xml tree
    """
    parser = etree.XMLParser(remove_blank_text=True)
    tree = etree.parse(template, parser)

    # adjust general parameters
    tree.find("./created/time").text = "{:%Y.%m.%d %H:%M:%S}".format(datetime.datetime.now())
    tree.find("./created/name").text = "VieSched++ AUTO"
    tree.find("./created/name").text = "matthias.schartner@geo.tuwien.ac.at"
    tree.find("./general/experimentName").text = session["code"]
    tree.find("./general/startTime").text = "{:%Y.%m.%d %H:%M:%S}".format(session["date"])
    tree.find("./general/endTime").text = "{:%Y.%m.%d %H:%M:%S}".format(
        session["date"] + datetime.timedelta(hours=session["duration"]))
    tree.find("./output/experimentDescription").text = session["name"]
    tree.find("./output/scheduler").text = session["scheduler"]
    tree.find("./output/correlator").text = session["correlator"]

    # catalogs to absolut path
    cwd = os.getcwd()
    folder = os.path.dirname(template)
    os.chdir(folder)
    tree.find("./catalogs/antenna").text = os.path.abspath(tree.find("./catalogs/antenna").text)
    tree.find("./catalogs/equip").text = os.path.abspath(tree.find("./catalogs/equip").text)
    tree.find("./catalogs/flux").text = os.path.abspath(tree.find("./catalogs/flux").text)
    tree.find("./catalogs/freq").text = os.path.abspath(tree.find("./catalogs/freq").text)
    tree.find("./catalogs/hdpos").text = os.path.abspath(tree.find("./catalogs/hdpos").text)
    tree.find("./catalogs/loif").text = os.path.abspath(tree.find("./catalogs/loif").text)
    tree.find("./catalogs/mask").text = os.path.abspath(tree.find("./catalogs/mask").text)
    tree.find("./catalogs/modes").text = os.path.abspath(tree.find("./catalogs/modes").text)
    tree.find("./catalogs/position").text = os.path.abspath(tree.find("./catalogs/position").text)
    tree.find("./catalogs/rec").text = os.path.abspath(tree.find("./catalogs/rec").text)
    tree.find("./catalogs/rx").text = os.path.abspath(tree.find("./catalogs/rx").text)
    tree.find("./catalogs/source").text = os.path.abspath(tree.find("./catalogs/source").text)
    tree.find("./catalogs/tracks").text = os.path.abspath(tree.find("./catalogs/tracks").text)
    os.chdir(cwd)

    settings = configparser.ConfigParser()
    settings.read("settings.ini")

    # add parameters
    add_parameter(tree, "tagalong", ["tagalong"], ["1"])
    add_parameter(tree, "down", ["available"], ["0"])

    # change setup for tagalong mode
    add_tagalong_time(session, tree)

    # change setup for downtimes
    if not session["intensive"]:
        include_down_time_ivs(session, tree, settings)
        add_custom_downtime(session, tree)

    if "OHIGGINS" in session["stations"]:
        add_oh_downtime(session, tree, settings)

    # remove setup if it refers to station that is not scheduled
    remove_unnecessary_station_setup(session, tree)

    # change priorities xml entries
    change_station_names_in_xml(session, tree)

    # adjust stations
    general = tree.find("./general")
    general.remove(general.find("./stations"))
    stations = etree.SubElement(general, "stations")
    for sta in session["stations"]:
        tmp = etree.SubElement(stations, "station")
        tmp.text = sta
    return tree


def include_down_time_ivs(session, tree, settings):
    """
    add down time based on IVS intensive schedule master

    it will extend the downtime based on entries in setting.ini file

    :param session: dictionary with session specific fields 
    :param tree: xml parameter tree
    :param settings:  content of settings.ini file
    :return: None
    """
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
                insert_setup_node_logic(int_start, int_end, s_start, s_end, session, tree, sta, "down", int["name"])


def add_oh_downtime(session, tree, settings):
    """
    add OHIGGINS downtime necessary for satellite observations with higher priority
    
    :param session: dictionary with session specific fields 
    :param tree: xml parameter tree
    :param settings:  content of settings.ini file
    :return: None
    """
    if settings.has_section("general"):
        pad = settings["general"].getint("Oh_down_extra_min", 5)
    else:
        pad = 5
    path = settings["general"].get("Oh_down")
    if not path or not os.path.exists(path):
        Message.addMessage("WARNING: OH down time file \"{}\" not found!".format(path))
        return

    s_start = session["date"]
    s_end = session["date"] + datetime.timedelta(hours=session["duration"])
    pattern = re.compile(
        r'(APPROVED|SCHEDULED|PLANNED).*(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}).(\d{4}-\d{2}-\d{2}T\d{2}:\d{2})')

    with open(path) as f:
        for l in f:
            g = pattern.search(l)
            if g is not None:
                start = datetime.datetime.strptime(g.group(2), "%Y-%m-%dT%H:%M") - datetime.timedelta(minutes=pad)
                end = datetime.datetime.strptime(g.group(3), "%Y-%m-%dT%H:%M") + datetime.timedelta(minutes=pad)

                insert_setup_node_logic(start, end, s_start, s_end, session, tree, "OHIGGINS", "down",
                                        "satellite observation")


def add_custom_downtime(session, tree):
    """
    add downtime listed in './downtime.txt' file
    
    :param session: dictionary with session specific fields 
    :param tree: xml parameter tree
    :return: None
    """
    read_parameter_change_from_text_file(session, tree, "./downtime.txt", "down")


def add_tagalong_time(session, tree):
    """
    add tagalong time listed in './tagalong.txt' file

    :param session: dictionary with session specific fields 
    :param tree: xml parameter tree
    :return: None
    """
    read_parameter_change_from_text_file(session, tree, "./tagalong.txt", "tagalong")


def read_parameter_change_from_text_file(session, tree, path, parameter_name):
    """
    parse parameter change to xml tree

    :param session: dictionary with session specific fields 
    :param tree: xml parameter tree
    :param path: path to textfile containing parameter changes and timestamps
    :param parameter_name:  name of the parameter in xml file
    :return: None
    """
    s_start = session["date"]
    s_end = session["date"] + datetime.timedelta(hours=session["duration"])
    with open(path) as f:
        for l in f:
            if l.startswith("#"):
                continue

            station, start, end, *comment = l.split()
            if station in session["stations"]:
                start = datetime.datetime.fromisoformat(start)
                end = datetime.datetime.fromisoformat(end)

                comment = " ".join(comment)
                insert_setup_node_logic(start, end, s_start, s_end, session, tree, station, parameter_name, comment)


def insert_setup_node_logic(p_start, p_end, session_start, session_end, session, tree, station, parameter_name,
                            comment=""):
    """
    base logic to add new setup node

    :param p_start: start time of parameter change
    :param p_end: end time of parameter change
    :param session_start: session start time
    :param session_end: session end time
    :param session: dictionary with session specific fields 
    :param tree: xml parameter tree
    :param station: station name
    :param parameter_name:  name of the parameter in xml file
    :param comment: 
    :return: None
    """
    b_in = p_start >= session_start and p_end <= session_end
    b_start_in = session_start <= p_start <= session_end
    b_end_in = session_start <= p_end <= session_end
    b_cover = p_start <= session_start and p_end >= session_end
    if b_in or b_start_in or b_end_in or b_cover:
        if station in session["stations"]:
            p_start = max(session_start, p_start)
            p_end = min(session_end, p_end)
            add_comment(station, p_start, p_end, parameter_name, comment)
            insert_setup_node(session, station, p_start, p_end, tree, parameter_name)


def insert_setup_node(session, station, p_start, p_end, tree, parameter_name):
    """
    add new setup node
    
    :param session: dictionary with session specific fields 
    :param station: station name
    :param p_start: start time of parameter change
    :param p_end: end time of parameter change
    :param tree: xml parameter tree
    :param parameter_name:  name of the parameter in xml file
    :return: None
    """
    setup = tree.find("./station/setup")
    s_start = session["date"]
    s_end = session["date"] + datetime.timedelta(hours=session["duration"])
    root = find_root_setup(station, p_start, p_end, s_start, s_end, setup)
    node = etree.Element("setup")
    etree.SubElement(node, "member").text = station
    etree.SubElement(node, "start").text = "{:%Y.%m.%d %H:%M:%S}".format(p_start)
    etree.SubElement(node, "end").text = "{:%Y.%m.%d %H:%M:%S}".format(p_end)
    etree.SubElement(node, "parameter").text = parameter_name
    etree.SubElement(node, "transition").text = "hard"
    root.insert(len(root), node)


def find_root_setup(station, p_start, p_end, session_start, session_end, tree_node):
    """
    recursively find the root entry point for new setup node

    :param station: station name
    :param p_start: start time of parameter change
    :param p_end: end time of parameter change
    :param session_start: session start time
    :param session_end: session end time
    :param tree_node: xml parameter tree node
    :return: None
    """
    root = tree_node
    for s in tree_node:
        if s.tag == "setup":
            if is_valid_root_setup(station, p_start, p_end, session_start, session_end, s):
                root = find_root_setup(station, p_start, p_end, session_start, session_end, s)
                break

    return root


def is_valid_root_setup(station, p_start, p_end, session_start, session_end, tree_node):
    """
    check if this tree node is valid root entry point for new setup node
    
    :param station: station name
    :param p_start: start time of parameter change
    :param p_end: end time of parameter change
    :param session_start: session start time
    :param session_end: session end time
    :param tree_node: xml parameter tree node
    :return: True if it is a valid setup start point, otherwise False
    """
    member = "__all__"
    setup_start = session_start
    setup_end = session_end

    for s in tree_node:
        if s.tag == "member":
            member = s.text
        if s.tag == "start":
            setup_start = datetime.datetime.strptime(s.text, "%Y.%m.%d %H:%M:%S")
        if s.tag == "end":
            setup_end = datetime.datetime.strptime(s.text, "%Y.%m.%d %H:%M:%S")

    flag = True
    if not (member == "__end__" or member == station):
        flag = False
    if not (p_start >= setup_start and p_end <= setup_end):
        flag = False

    if setup_start < p_start < setup_end < p_end:
        Message.addMessage("   ERROR: overlapping parameter setups!")
    if p_start < setup_start < p_end < setup_end:
        Message.addMessage("   ERROR: overlapping parameter setups!")

    return flag


def remove_unnecessary_station_setup(session, tree):
    """
    remove all parameters related to stations not observing in this session
    
    :param session: dictionary with session specific fields 
    :param tree: xml parameter tree
    :return: None
    """
    setup = tree.find("./station/setup")
    for s in setup:
        if s.tag == "setup":
            for ss in s:
                if ss.tag == "member":
                    if not (ss.text == "__all__" or ss.text in session["stations"]):
                        setup.remove(s)
                        break


def add_comment(station, p_start, p_end, parameter_name, comment=""):
    """
    add comment to email in case of parameter change

    :param station: station name
    :param p_start: start time of parameter change
    :param p_end: end time of parameter change
    :param parameter_name:  name of the parameter in xml file
    :param comment: optional comment
    :return: None
    """
    start_str = "{:%Y.%m.%d %H:%M:%S}".format(p_start)
    end_str = "{:%Y.%m.%d %H:%M:%S}".format(p_end)
    dur = (p_end - p_start).total_seconds() / 60
    if comment:
        comment = "- " + comment

    if parameter_name == "down":
        parameter_name = "downtime"

    Message.addMessage("   add {}: {:8s} {:s} {:s} ({:.0f} minutes) {:s}".format(
        parameter_name, station, start_str, end_str, dur, comment))


def add_parameter(tree, parameter_name, fieldnames, values):
    """
    add new parameter to xml tree

    :param tree: xml parameter tree
    :param parameter_name:  name of the parameter in xml file
    :param fieldnames: list of fieldnames in xml parameter block
    :param values: list of corresponding values in xml parameter block
    :return: None
    """
    root = tree.find("./station/parameters")
    for s in root:
        if s.tag == "parameter" and s.attrib["name"] == parameter_name:
            break
    else:
        node = etree.Element("parameters", name=parameter_name)
        for fieldname, value in zip(fieldnames, values):
            etree.SubElement(node, fieldname).text = value
        root.insert(len(root), node)


def change_station_names_in_xml(session, tree):
    """
    Change priorities entries (add/remove stations) + change reference clock

    :param session: dictionary with session specific fields
    :param tree: xml parameter tree
    :return: None
    """
    stations = session["stations"]

    # change reference clock
    ref_clock = tree.find("./solver/reference_clock")
    if ref_clock is not None:
        ref_clock.text = stations[0]

    # change priority entries
    root = tree.find("./priorities")
    if root is not None:
        fixed = ["#obs", "XPO", "YPO", "dUT1", "NUTX", "NUTY"]
        for s in root:
            if s.tag == "variable" and s.attrib["name"] not in fixed and s.attrib["name"] not in stations:
                root.remove(s)

        for sta in stations:
            for s in root:
                if s.tag == "variable" and s.attrib["name"] == sta:
                    break
            else:
                node = etree.Element("variable", name=sta)
                node.text = "0.0"
                root.insert(len(root), node)
