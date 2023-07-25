import configparser
import datetime
import re
from pathlib import Path

from lxml import etree

from Helper import Message


def adjust_xml(template, session, pre_scheduling_functions, outdir):
    """
    change template xml file with session specific entries
    
    :param template: path to xml template
    :param session: dictionary with session specific fields
    :return: adjusted xml tree
    """
    parser = etree.XMLParser(remove_blank_text=True)
    tree = etree.parse(str(template), parser)

    # adjust general parameters
    tree.find("./created/time").text = f"{datetime.datetime.now():%Y.%m.%d %H:%M:%S}"
    tree.find("./created/name").text = "VieSched++ AUTO"
    tree.find("./general/experimentName").text = session["code"]
    tree.find("./general/startTime").text = f"{session['date']:%Y.%m.%d %H:%M:%S}"
    tree.find("./general/endTime").text = f"{session['date'] + datetime.timedelta(hours=session['duration']):%Y.%m.%d %H:%M:%S}"
    tree.find("./output/experimentDescription").text = session["name"]
    tree.find("./output/scheduler").text = session["scheduler"]
    tree.find("./output/correlator").text = session["correlator"]

    # catalogs to absolut path
    folder = template.parent
    tree.find("./catalogs/antenna").text = str((folder / tree.find("./catalogs/antenna").text).resolve())
    tree.find("./catalogs/equip").text = str((folder / tree.find("./catalogs/equip").text).resolve())
    tree.find("./catalogs/flux").text = str((folder / tree.find("./catalogs/flux").text).resolve())
    tree.find("./catalogs/freq").text = str((folder / tree.find("./catalogs/freq").text).resolve())
    tree.find("./catalogs/hdpos").text = str((folder / tree.find("./catalogs/hdpos").text).resolve())
    tree.find("./catalogs/loif").text = str((folder / tree.find("./catalogs/loif").text).resolve())
    tree.find("./catalogs/mask").text = str((folder / tree.find("./catalogs/mask").text).resolve())
    tree.find("./catalogs/modes").text = str((folder / tree.find("./catalogs/modes").text).resolve())
    tree.find("./catalogs/position").text = str((folder / tree.find("./catalogs/position").text).resolve())
    tree.find("./catalogs/rec").text = str((folder / tree.find("./catalogs/rec").text).resolve())
    tree.find("./catalogs/rx").text = str((folder / tree.find("./catalogs/rx").text).resolve())
    tree.find("./catalogs/source").text = str((folder / tree.find("./catalogs/source").text).resolve())
    tree.find("./catalogs/tracks").text = str((folder / tree.find("./catalogs/tracks").text).resolve())

    # add parameters
    add_parameter(tree.find("./station/parameters"), "tagalong", ["tagalong"], ["1"])
    add_parameter(tree.find("./station/parameters"), "down", ["available"], ["0"])
    for f in pre_scheduling_functions:
        f(tree=tree, session=session, folder=template.parent, outdir=outdir)

    # change setup for tagalong mode
    add_tagalong_time(session, tree)

    # change setup for downtimes
    add_custom_downtime(session, tree)

    if "OHIGGINS" in session["stations"]:
        add_oh_downtime(session, tree)

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


def add_oh_downtime(session, tree):
    """
    add OHIGGINS downtime necessary for satellite observations with higher priority
    
    :param session: dictionary with session specific fields 
    :param tree: xml parameter tree
    :param settings:  content of settings.ini file
    :return: None
    """
    settings = configparser.ConfigParser()
    settings.read("settings.ini")
    if settings.has_section("general"):
        pad = settings["general"].getint("Oh_down_extra_min", 5)
    else:
        pad = 5
    path = Path(settings["general"].get("Oh_down"))
    if not path or not path.is_file():
        Message.addMessage(f"WARNING: OH down time file \"{path}\" not found!")
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

                insert_station_setup_with_time(start, end, s_start, s_end, session, tree, "OHIGGINS", "down",
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
            l = l.strip()
            if not l:
                continue

            station, start, end, *comment = l.split()
            if station in session["stations"]:
                start = datetime.datetime.fromisoformat(start)
                end = datetime.datetime.fromisoformat(end)

                comment = " ".join(comment)
                insert_station_setup_with_time(start, end, s_start, s_end, session, tree, station, parameter_name,
                                               comment)


def insert_station_setup_with_time(p_start, p_end, session_start, session_end, session, tree, station, parameter_name,
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
            insert_setup_node(session, station, tree.find("./station/setup"), parameter_name, p_start, p_end)


def insert_setup_node(session, member, root, parameter_name, p_start=None, p_end=None, tag="member"):
    """
    add new setup node
    
    :param session: dictionary with session specific fields 
    :param member: member name
    :param p_start: start time of parameter change
    :param p_end: end time of parameter change
    :param root: xml parameter tree
    :param parameter_name:  name of the parameter in xml file
    :return: None
    """
    s_start = session["date"]
    s_end = session["date"] + datetime.timedelta(hours=session["duration"])
    if p_start is None:
        p_start = s_start
    if p_end is None:
        p_end = s_end
    root = find_root_setup(member, p_start, p_end, s_start, s_end, root)
    node = etree.Element("setup")
    etree.SubElement(node, tag).text = member
    if p_start != s_start:
        etree.SubElement(node, "start").text = f"{p_start:%Y.%m.%d %H:%M:%S}"
    if p_end != s_end:
        etree.SubElement(node, "end").text = f"{p_end:%Y.%m.%d %H:%M:%S}"
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


def add_group(root, name, members):
    """
    add a new group to parameter setup

    Parameters
    ----------
    root: xml tree root
    name: group name
    members: group members

    Returns
    -------
    None
    """
    for s in root:
        if s.tag == "groups":
            root_group = s
            break
    else:
        node = etree.Element("groups")
        root.insert(len(root), node)
        root_group = node

    for s in root_group:
        if s.tag == "group" and s.attrib["name"] == name:
            root_group.remove(s)

    node = etree.Element("group", name=name)
    for member in members:
        etree.SubElement(node, "member").text = member
    root_group.insert(len(root_group), node)


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
    start_str = f"{p_start:%Y.%m.%d %H:%M:%S}"
    end_str = f"{p_end:%Y.%m.%d %H:%M:%S}"
    dur = (p_end - p_start).total_seconds() / 60
    if comment:
        comment = "- " + comment

    if parameter_name == "down":
        parameter_name = "downtime"

    Message.addMessage(
        f"   add {parameter_name}: {station:8s} {start_str:s} {end_str:s} ({dur:.0f} minutes) {comment:s}")


def add_parameter(root, parameter_name, fieldnames, values, attriutes=None):
    """
    add new parameter to xml tree

    :param root: xml parameter tree
    :param parameter_name:  name of the parameter in xml file
    :param fieldnames: list of fieldnames in xml parameter block
    :param values: list of corresponding values in xml parameter block
    :return: None
    """
    if attriutes is None:
        attriutes = [None] * len(fieldnames)

    for s in root:
        if s.tag == "parameter" and s.attrib["name"] == parameter_name:
            break
    else:
        node = etree.Element("parameter", name=parameter_name)
        for fieldname, value, attriute in zip(fieldnames, values, attriutes):
            ele = etree.SubElement(node, fieldname)
            ele.text = value
            if attriute is not None:
                ele.set(attriute[0], attriute[1])
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
