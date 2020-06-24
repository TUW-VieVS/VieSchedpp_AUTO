import datetime
import os
import re
import configparser

import pandas as pd
from SendMail import delegate_send


class Message:
    msg_program = ""
    msg_session = ""
    msg_download = ""
    msg_header = ""
    msg_log = ""

    def __init__(self):
        pass

    @staticmethod
    def addMessage(str="", dump="session", endLine=True):
        """
        print and store message

        :param str: message
        :param dump: message type ("session", "program", "header", "log" or "download")
        :param endLine: flag if line-break should be added after message
        :return: None
        """
        if endLine:
            print(str)
            str += "\n"
        else:
            print(str, end="")

        if dump == "session":
            Message.msg_session += str
        elif dump == "program":
            Message.msg_program += str
        elif dump == "header":
            Message.msg_header += str
        elif dump == "log":
            Message.msg_log += str
        elif dump == "download":
            Message.msg_download += str
        else:
            print("message dump place \"{}\" not recognized".format(dump))

    @staticmethod
    def clearMessage(type):
        """
        clear stored messages

        :param type: message type ("session", "program", "download" or "log")
        :return: None
        """

        if type == "session":
            Message.msg_session = ""
        elif type == "program":
            Message.msg_program = ""
        elif type == "download":
            Message.msg_download = ""
        elif type == "log":
            Message.msg_log = ""


def readMaster(paths):
    """
    read session master

    :param paths: list of paths to session master files
    :return: list of all sessions
    """
    sessions = []
    for path in paths:
        if not os.path.exists(path):
            Message.addMessage("Error reading session master file: {}".format(path), dump="header")

        # extract year
        year = [int(s) for s in re.findall(r'\d{2}', os.path.basename(path))]
        if len(year) is not 1:
            return
        else:
            year = year[0] + 2000

        tlc2name = antennaLookupTable()

        with open(path) as f:
            for line in f:
                if not line.startswith("|"):
                    continue
                try:
                    tmp = line.split('|')

                    doy = int(tmp[4])
                    hour, min = [int(s) for s in tmp[5].split(":")]
                    date = datetime.datetime(year, 1, 1, hour, min, 0)
                    date = date + datetime.timedelta(days=doy - 1)
                    dur = int(tmp[6])
                    stations_tlc = tmp[7].strip().split()[0]
                    stations_tlc = [stations_tlc[i:i + 2].upper() for i in range(0, len(stations_tlc), 2)]

                    for tlc in stations_tlc:
                        if tlc == "VA":
                            stations_tlc.remove("VA")
                            stations_tlc += ["BR", "FD", "HN", "KP", "LA", "MK", "NL", "OV", "PT", "SC"]
                            break

                    if all(tlc in tlc2name for tlc in stations_tlc):
                        stations_name = [tlc2name[tlc] for tlc in stations_tlc]
                    else:
                        missing = [tlc not in tlc2name for tlc in stations_tlc]
                        for i, flag in enumerate(missing):
                            if flag:
                                Message.addMessage("Antenna {} not found in antenna.cat file".format(stations_tlc[i]),
                                                   dump="header")
                        continue

                    sessions.append({"name": tmp[1].strip(),
                                     "code": tmp[2].strip(),
                                     "date": date,
                                     "duration": dur,
                                     "stations_tlc": stations_tlc,
                                     "stations": stations_name,
                                     "scheduler": tmp[8].strip(),
                                     "correlator": tmp[9].strip()})

                except BaseException as err:
                    Message.addMessage("ERROR reading session: {} from file: {}".format(line, path), dump="header")
                    Message.addMessage(err, dump="header")
    return sessions


def antennaLookupTable():
    """
    create lookup table from antenna two-leter-code (TLC) to antenna name

    :return: dictionary["TLC"] -> "antenna_name"
    """
    dict = {}
    with open(os.path.join("CATALOGS", "antenna.cat")) as f:
        for line in f:

            # skip comments
            if line.startswith("*"):
                continue
            tmp = line.split()

            # skip other comments not marked with asterisk (*)
            if len(tmp) != 16:
                continue

            # add to dictonary
            dict[tmp[13].upper()] = tmp[1]

    return dict


def field2name(field):
    name = field
    if name.startswith("n_"):
        name = "#" + name[2:]
    if name.startswith("sky-coverage_average"):
        name = name.replace("sky_coverage_average", "sky-coverage")
        name = name.replace("average_", "")
        name = name.replace("_areas_", "@")
        name = name[:-4]
    if name.startswith("time_average"):
        name = name.replace("average_", "")
        name = name + " [%]"
    if name.startswith("sim"):
        name = name[4:]
        name = name.replace("repeatability", "rep")
        name = name.replace("mean_formal_error", "mfe")
    name = name.replace("_", " ")
    return name


def addStatistics(stats, best_idx, statistic_field, code, summary_file):
    """
    list statistics for best schedule

    :param stats: DataFrame for statistics.csv file
    :param best_idx: version number of selected schedule
    :param code: session code
    :param statistic_field: field names for summary file
    :param summary_file: path to summary file
    :return: summary DataFrame
    """

    Message.addMessage("\n")
    stats_dict = dict()
    for field in statistic_field:
        if field in stats:
            val = stats.loc[best_idx, field]
            name = field2name(field)
            stats_dict[name] = val
            Message.addMessage("{}: {}".format(name, val))

    # number of scans per station
    nscans_sta = {}
    filter_col = [col for col in stats if col.startswith('n_sta_scans_')]
    for col in filter_col:
        name = col.split("_")[-1]
        nscans_sta[name] = stats.loc[best_idx, col]

    # number of observations per station
    nobs_sta = {}
    filter_col = [col for col in stats if col.startswith('n_sta_obs_')]
    for col in filter_col:
        name = col.split("_")[-1]
        nobs_sta[name] = stats.loc[best_idx, col]

    # output station dependent statistics
    nsta = len(nscans_sta)
    Message.addMessage("\nparticipating stations: {}".format(nsta))
    for stas in nscans_sta.keys():
        Message.addMessage(
            "    {:8} ({:d} scans, {:d} obs)".format(stas, int(round(nscans_sta[stas])), int(round(nobs_sta[stas]))))

    # number of observations per baseline
    nobs_bl = {}
    filter_col = [col for col in stats if col.startswith('n_bl_obs_')]
    for col in filter_col:
        name = col.split("_")[-1]
        name = (name[0:2], name[3:5])
        nobs_bl[name] = stats.loc[best_idx, col]

    # output baseline dependend statistics
    tlcs = [i for n in nobs_bl.keys() for i in n]
    seen = set()
    tlcs = [x for x in tlcs if not (x in seen or seen.add(x))]
    nobs_perBaseline = pd.DataFrame(index=tlcs[0:-1], columns=tlcs[1:])
    for n, e in nobs_bl.items():
        sta1 = n[0]
        sta2 = n[1]
        nobs_perBaseline.loc[sta1, sta2] = e
    nobs_perBaseline = "    " + str(nobs_perBaseline).replace("NaN", "   ").replace("\n", "\n    ")
    Message.addMessage("\nnumber of observations per baseline:\n{}".format(nobs_perBaseline))

    # number of scans per source
    nscans_src = {}
    filter_col = [col for col in stats if col.startswith('n_src_scans_')]
    for col in filter_col:
        scans = stats.loc[best_idx, col]
        if scans in nscans_src:
            nscans_src[scans] += 1
        else:
            nscans_src[scans] = 0

    # output source dependent statistics
    Message.addMessage("\nnumber of scans per source")
    nsrc = 0
    for k, e in nscans_src.items():
        if k == 0:
            continue
        nsrc += e
        Message.addMessage("    {} source(s) observed in {} scans ".format(e, k))

    tlcs = "".join(tlcs)
    stats_dict["stations"] = tlcs
    with open(summary_file, "r") as f:
        if f.read():
            summary = pd.read_csv(summary_file, index_col=0)
        else:
            summary = pd.DataFrame()

    new = pd.DataFrame(index=[code], data=stats_dict)
    if code in summary.index:
        summary = summary.drop(code)
    summary = summary.append(new)
    summary.to_csv(summary_file)

    # reverse and output
    Message.addMessage("\ncomparison with previous schedules:\n{}".format(summary[::-1].head(10).to_string()))
    return summary.tail(10)


def update_uploadScheduler(path, delta_days, upload=False):
    path = os.path.dirname(path)

    today = datetime.date.today()
    target_day = today + datetime.timedelta(days=delta_days)

    flag = "pending"
    if not upload:
        flag = "uploaded"

    txt = ""
    with open("upload_scheduler.txt", "r") as f:
        for l in f:
            if not l.strip():
                continue
            if not l.startswith(path):
                txt += l

    txt += "{} {} {}\n".format(path, target_day, flag)

    with open("upload_scheduler.txt", "w") as f:
        f.write(txt)


def scale(s, minIsGood=True):
    if minIsGood:
        q = s.quantile(.75)
        r = (s - s.min()) / (q - s.min())
        r.loc[r > 1] = 1
        r = 1 - r
    else:
        q = s.quantile(.25)
        r = (s - q) / (s.max() - q)
        r.loc[r < 0] = 0
    return r


def setup_email():
    settings = configparser.ConfigParser()
    settings.read("settings.ini")
    email_slot = settings["general"].get("email_server", "gmail").lower()
    if email_slot != "fromfile":
        delegate_send(email_slot)
    else:
        if os.path.exists("email_function.txt"):
            with open('email_function.txt') as f:
                c = f.read().strip().lower()
                delegate_send(c)
