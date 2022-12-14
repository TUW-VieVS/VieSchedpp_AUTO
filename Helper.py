import datetime
import inspect
import re
import traceback
from collections import defaultdict
from pathlib import Path

import pandas as pd


class Message:
    msg_program = ""
    msg_session = ""
    msg_download = ""
    msg_header = ""
    msg_log = ""
    flag = True

    def __init__(self):
        pass

    @staticmethod
    def log(bool):
        Message.flag = bool

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

        if Message.flag:
            if dump == "session":
                Message.msg_session += str
            elif dump == "program":
                Message.msg_program += str
            elif dump == "header":
                Message.msg_header += str
            elif dump == "log":
                if len(str) > 2000:
                    Message.msg_log += str[1:2000]
                    Message.msg_log += "\n[WARNING] log too long!\n\n"
                else:
                    Message.msg_log += str
            elif dump == "download":
                Message.msg_download += str
            else:
                print(f"message dump place \"{dump}\" not recognized")

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


def read_master_v1(path):
    sessions = []
    # extract year
    year = [int(s) for s in re.findall(r'\d{2}', path.name)]
    if len(year) != 1:
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
                dur = float(tmp[6])
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
                            Message.addMessage(f"Antenna {stations_tlc[i]} not found in antenna.cat file",
                                               dump="header")
                    continue

                sessions.append({"name": tmp[1].strip(),
                                 "code": tmp[2].strip(),
                                 "type": "unknown",
                                 "date": date,
                                 "duration": dur,
                                 "stations_tlc": stations_tlc,
                                 "stations": stations_name,
                                 "scheduler": tmp[8].strip(),
                                 "correlator": tmp[9].strip()})

            except:
                Message.addMessage(f"#### ERROR reading session: {line} from file: {path} ####",
                                   dump="header")
                Message.addMessage(traceback.format_exc(), dump="header")
    return sessions


def read_master_v2(path):
    sessions = []
    # extract year
    year = [int(s) for s in re.findall(r'\d{4}', path.name)]
    if len(year) != 1:
        return
    else:
        year = year[0]

    tlc2name = antennaLookupTable()

    with open(path) as f:
        for line in f:
            if not line.startswith("|"):
                continue
            try:
                tmp = line.split('|')
                date = datetime.datetime.strptime(f"{tmp[2]} {tmp[5]}", "%Y%m%d %H:%M")

                dur_hour, dur_min = [int(s) for s in tmp[6].split(":")]
                dur = dur_hour + dur_min / 60
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
                            Message.addMessage(f"Antenna {stations_tlc[i]} not found in antenna.cat file",
                                               dump="header")
                    continue

                sessions.append({"name": tmp[3].strip(),
                                 "code": tmp[3].strip(),
                                 "type": tmp[1].strip(),
                                 "date": date,
                                 "duration": dur,
                                 "stations_tlc": stations_tlc,
                                 "stations": stations_name,
                                 "scheduler": tmp[8].strip(),
                                 "correlator": tmp[9].strip()})

            except:
                Message.addMessage(f"#### ERROR reading session: {line} from file: {path} ####",
                                   dump="header")
                Message.addMessage(traceback.format_exc(), dump="header")
    return sessions


def read_master(paths):
    """
    read session master

    :param paths: path to session master file (list of paths or single string)
    :return: list of all sessions
    """
    if isinstance(paths, Path):
        paths = [paths]

    sessions = []
    for path in paths:
        if not path.is_file():
            Message.addMessage(f"[Error] reading session master file: {path}", dump="header")
            return

        with open(path) as f:
            l = f.readline()
            if l.startswith("## Master file format version 1.0"):
                sessions += read_master_v1(path)
            elif l.startswith("## Master file format version 2.0"):
                sessions += read_master_v2(path)
            else:
                Message.addMessage(f"#### ERROR reading master: {path} unknown format ####",
                                   dump="header")
                Message.addMessage(traceback.format_exc(), dump="header")

    return sessions


def antennaLookupTable(reverse=False):
    """
    create lookup table from antenna two-leter-code (TLC) to antenna name

    :return: dictionary["TLC"] -> "antenna_name"
    """
    dict = {}
    with open(Path("CATALOGS") / "antenna.cat") as f:
        for line in f:

            # skip comments
            if line.startswith("*"):
                continue
            tmp = line.split()

            # skip other comments not marked with asterisk (*)
            if len(tmp) != 16:
                continue

            # add to dictonary
            if reverse:
                dict[tmp[1]] = tmp[13].upper()
            else:
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


def addStatistics(stats, best_idx, code, summary_file):
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
    Message.addMessage(f"\nparticipating stations: {nsta}")
    for stas in nscans_sta.keys():
        Message.addMessage(
            f"    {stas:8} ({int(round(nscans_sta[stas])):d} scans, {int(round(nobs_sta[stas])):d} obs)")

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
    Message.addMessage(f"\nnumber of observations per baseline:\n{nobs_perBaseline}")

    # number of scans per source
    nscans_src = defaultdict(int)
    filter_col = [col for col in stats if col.startswith('n_src_scans_')]
    for col in filter_col:
        scans = stats.loc[best_idx, col]
        nscans_src[scans] += 1

    # output source dependent statistics
    Message.addMessage("\nnumber of scans per source")
    for i in range(1, max(nscans_src.keys()) + 1):
        if nscans_src[i] > 0:
            Message.addMessage(f"    {nscans_src[i]:2d} source(s) observed in {i} scans ")

    tlcs = "".join(tlcs)
    with open(summary_file, "r") as f:
        if f.read():
            summary = pd.read_csv(summary_file, index_col=0)
        else:
            summary = pd.DataFrame()

    new = stats.loc[best_idx, :].to_frame().T
    new.index = [code]
    new['stations'] = tlcs
    if code in summary.index:
        summary = summary.drop(code)
    summary = summary.append(new)
    summary.to_csv(summary_file)

    # reverse and output
    return summary.tail(10)


def update_uploadScheduler(path, delta_days, upload=False):
    path = path.parent

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
            if not l.startswith(str(path)):
                txt += l

    txt += f"{path} {target_day} {flag}\n"

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
    if r.isna().all():
        r = r.fillna(0)
    return r


def read_emails(program, fallback):
    emails = program.get("contact", "")
    if not emails:
        emails = fallback
    else:
        emails = emails.split(",")
    return emails


def find_function(module, function_names):
    f = []

    if not function_names:
        return f

    for function_name in function_names.split(","):
        function_name = function_name.strip()
        if not function_name:
            continue
        functions_list = [f for n, f in inspect.getmembers(module) if inspect.isfunction(f) and n == function_name]
        if len(functions_list) == 1:
            f.append(functions_list[0])
        else:
            Message.addMessage(f"[ERROR] function \"{function_name}\" not found", dump="header")
    return f


def read_sources(path, session_name=None):
    source_name = []
    source_list = []
    comment_list = []
    with open(path, "r") as f:
        for l in f:
            l = l.strip()

            # check if source was observed by previous session
            list_comment = l.split("*")
            list = list_comment[0]
            if len(list_comment) == 1:
                comment = ""
            else:
                comment = list_comment[1]

            if session_name is not None and comment and session_name != comment:
                continue

            src = list.split()[0]
            source_name.append(src)
            source_list.append(list)
            comment_list.append(comment)

    return source_name, source_list, comment_list


def skip_session(program, session):
    if program.startswith("GOW"):
        stations_tlc = session["stations_tlc"]
        if program == "GOW08" and ("AG" in stations_tlc or "OH" in stations_tlc):
            return True
        if program == "GOW16" and ("AG" not in stations_tlc or "OH" in stations_tlc):
            return True
        if program == "GOW17" and "OH" not in stations_tlc:
            return True
    return False
