import argparse
import configparser
import datetime
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import traceback
import pandas as pd

import Helper
from Helper import Message
import Plotting
import SendMail
import Transfer
import post_scheduling_functions
import pre_scheduling_functions
import select_best_functions
import skd_parser.skd as skd_parser
from XML_manipulation import adjust_xml
from check_uploads import check_uploads


def find_session(master, settings):
    """

    Parameters
    ----------
    master list of all sessions in the master file
    settings settings for the observing program (from settings.ini file)

    Returns session(s) to be processed
    -------

    There are three options for settings.get("schedule_date"):
        - integer: the session with this offset in days from today is selected (default for operational execution)
        - "next": the next session in the master file is selected (e.g. when executing using test mode)
        - date: the session with this start date is selected (e.g. when executing with a date flag)
        - session code: the session with this session code is selected (e.g. when executing with a session flag)
    """

    target_session_string = settings.get("schedule_date", "10")

    today = datetime.date.today()
    sessions = []

    # this searches a session with a specific offset in days from today (DEFAULT behaviour in operational execution)
    if Helper.is_int(target_session_string):
        session_date = today + datetime.timedelta(days=int(target_session_string))
        sessions = [s for s in master if (s["type"] == settings.name) and s["date"].date() == session_date]

    # This searches the next session in case the -t test flag is used
    elif target_session_string == "next":
        offset = 0
        while not sessions:
            if offset > 0:
                Message.addMessage(f"no \"next\" schedule in master - checking {offset} days earlier", dump="program")
            if offset > 360:
                break
            for s in master:
                if s["date"].date() < today - datetime.timedelta(days=offset):
                    continue
                if s["type"] == settings.name:
                    sessions.append(s)
                    session_date = s["date"].date()
                    break
            offset += 30

    # this searches a session with a specific start date (e.g. when executing with a -d date flag)
    elif Helper.is_datetime(target_session_string):
        session_date = datetime.datetime.fromisoformat(target_session_string).date()
        sessions = [s for s in master if (s["type"] == settings.name) and s["date"].date() == session_date]

    # this searches a session with a specific session code (e.g. when executing with -s session flag)
    else:
        for session in master:
            if ((session["type"] == settings.name) and session["code"].upper() == target_session_string.upper()):
                session_date = session["date"].date()
                sessions.append(session)
                break

    # some logging about the found session(s)
    if sessions:
        Message.addMessage(f"target start time for {settings.name} session: {session_date:%B %d, %Y}", dump="program")
        Message.addMessage(f"{len(sessions)} session(s) will be processed", dump="program")
    else:
        Message.addMessage(f"No valid session found for {settings.name}", dump="program")

    return sessions


def start_scheduling(settings):
    """
    start VieSched++ AUTO processing

    :return: None
    """

    # some general logging about the execution environment
    Message.addMessage("VieSched++ AUTO report", dump="header")
    Message.addMessage(f"date: {datetime.date.today():%B %d, %Y}", dump="header")
    Message.addMessage(f"computer: {platform.node()}, Python {platform.python_version()}", dump="header")
    Message.addMessage(f"institution: {settings['general'].get('institute', 'unknown')}", dump="header")
    Message.addMessage("This is an automatically generated message. Do NOT reply to this email directly!",
                       dump="header")

    # download files
    if not args.no_download:
        Transfer.download_ftp()
        Transfer.download_http()
        Helper.merge_flux_cat_vgos_sx()
    else:
        Message.addMessage("no downloads", dump="header")

    # read all master files
    master = Helper.read_master()

    # start processing all programs
    for program in settings.sections():
        if program == "general":
            continue
        if program not in args.observing_programs:
            print(f"skipping scheduling observing program: {program}")
            continue

        # look for relevant session(s) in master file based on settings and command line arguments
        sessions = find_session(master, settings[program])
        try:
            # process all sessions found for this program
            for session in sessions:
                start(session, settings)

        except:
            Message.addMessage("#### ERROR ####")
            Message.addMessage(traceback.format_exc())
            emails = Helper.read_emails(settings[program], args.fallback_email)
            SendMail.writeErrorMail(emails)


def start(session, settings):
    """
    start auto processing for one observing program

    :param session: session to be processed (dictionary with session specific fields)
    :param settings: settings (from settings.ini file)
    :return: None
    """
    # extract general settings
    output_path = Path(settings["general"].get("prefix_output_folder", "Schedules"))
    path_scheduler = settings["general"].get("path_to_scheduler")

    program = session["type"]
    settings_program = settings[program]
    emails = Helper.read_emails(settings_program, args.fallback_email)
    fun_select = Helper.find_function(select_best_functions, settings_program["function"])[0]
    fun_pre = Helper.find_function(pre_scheduling_functions, settings_program.get("pre_scheduling_functions", ""))
    fun_post = Helper.find_function(post_scheduling_functions, settings_program.get("post_scheduling_functions", ""))
    upload_date = session["date"].date() - datetime.timedelta(settings_program.getint("delta_days_upload", 7))

    # reset logging
    Message.clearMessage("program")
    Message.clearMessage("session")
    Message.clearMessage("log")

    # add basic logging
    Message.addMessage(f"=== {program} observing program ===", dump="program")
    Message.addMessage("{code} start {date} duration {duration}h stations {stations}".format(**session))
    Message.addMessage("contact:", dump="program")
    for email in emails:
        Message.addMessage(f"    {email}", dump="program")

    # get list of templates and adjust them with session specific fields, also execute pre-scheduling functions
    templates = list((Path("Templates") / program).glob("*.xml"))
    xmls = adjust_template(output_path, session, templates, fun_pre)

    # add post scheduling functions based on station network (for VLBA and DSS antennas)
    flag_VLBA = any(["VLBA" in sta or "PIETOWN" in sta for sta in session["stations"]])
    flag_DSS = any([sta.startswith("DSS") for sta in session["stations"]])
    if flag_VLBA or flag_DSS:
        fun_post.append(post_scheduling_functions._vex_in_sked_format)
    if flag_VLBA:
        fun_post.append(post_scheduling_functions._vlba_vex_adjustments)

    # loop over all templates and execute scheduling with them
    stats = []
    for xml in xmls:
        cwd = xml.parent
        Message.addMessage(f"   processing file: {xml}")
        p = subprocess.run([path_scheduler, str(xml.absolute())], cwd=cwd, capture_output=True, text=True)
        log = p.stdout
        if log:
            Message.addMessage(log, dump="log")
        errlog = p.stderr
        if errlog:
            Message.addMessage(errlog, dump="log")
        p.check_returncode()

        # rename statistics.csv and simulation_summary file to avoid name clashes
        statistic_in = cwd / "statistics.csv"
        statistic_out = cwd / f"statistics_{xml.name}.csv"
        if statistic_out.is_file():
            statistic_out.unlink()
        statistic_in.rename(statistic_out)

        simulation_summary_in = cwd / "simulation_summary.txt"
        simulation_summary_out = cwd / f"simulation_summary_{xml.name}.txt"
        if simulation_summary_out.is_file():
            simulation_summary_out.unlink()
        simulation_summary_in.rename(simulation_summary_out)

        # read statistics.csv file
        df = pd.read_csv(statistic_out, index_col=0)
        stats.append(df)

    # concatenate all statistics.csv files
    stats = pd.concat(stats)
    stats = stats.drop_duplicates()
    stats.sort_index(inplace=True)

    # find best schedule based on statistics
    best_idx = fun_select(stats)
    Message.addMessage(f"best version: v{int(best_idx):03d}")

    # update summary file with statistics of best schedule
    summary_file = cwd.parent / "summary.txt"
    summary_df = Helper.addStatistics(stats.loc[best_idx], session["code"].upper(), summary_file)

    # copy best schedule to "selected" folder
    version_pattern = f"_v{best_idx:03d}"
    version_pattern_regex = re.compile(version_pattern + r'[^\d]')
    bestFiles = [f for f in cwd.glob(f"*{version_pattern}*") if version_pattern_regex.search(f.name)]
    xml_dir_selected = cwd / "selected"
    if xml_dir_selected.is_dir():
        shutil.rmtree(xml_dir_selected)
    xml_dir_selected.mkdir(exist_ok=True, parents=True)
    for f in bestFiles:
        fname = f.name.replace(version_pattern, "")
        shutil.copy(f, xml_dir_selected / fname)
    stats.to_csv(xml_dir_selected / "merged_statistics.csv")

    # add session to the upload scheduler if upload is activated in settings.ini file
    if settings_program.get("upload", "no").lower() != "no":
        Message.addMessage(f"this session will be uploaded on: "
                           f"{upload_date:%B %d, %Y}")
        Helper.update_uploadScheduler(xml_dir_selected, upload_date)
        if upload_date < datetime.date.today():
            Message.addMessage("[WARNING]: upload date already passed!")
    else:
        Message.addMessage("this session will NOT be uploaded!")

    # start with some plotting based on the best schedule
    try:
        skdFile = xml_dir_selected / f"{session['code'].lower()}.skd"
        skd = skd_parser.skdParser(skdFile)
        skd.parse()
        fields = settings_program.get("statistics").split(",")
        Plotting.summary(summary_df, fields, xml_dir_selected)
        Plotting.polar_plots(skd, xml_dir_selected, "duration")
        Plotting.polar_plots(skd, xml_dir_selected, "start_time")
        Plotting.close_all()
    except:
        Message.addMessage("#### ERROR ####")
        Message.addMessage(traceback.format_exc())

    # execute post scheduling functions (e.g. to adjust the VEX file for VLBA sessions)
    for post_f in fun_post:
        post_f(path=xml_dir_selected, ds=stats.loc[best_idx, :], session=session, program=program, version=best_idx)

    # write email with best schedule attached
    SendMail.writeMail(xml_dir_selected, emails, date=session["date"])

    # delete all files in the cwd except for the "selected" folder and some special files to save storage space
    delete_files(cwd)
    Message.addMessage(f"finished processing session {session['code']}\n")


def delete_files(folder):
    for f in folder.iterdir():
        if "VieSchedpp" in f.name or f.is_dir() or f.suffix == ".csv" or f.suffix == ".tle" or f.suffix == ".xml":
            continue
        else:
            f.unlink()
        pass

def adjust_template(output_path:Path, session, templates, pre_scheduling_functions):
    """
    adjustes the template XML file with session specific fields

    :param output_path: fields to be stored in statistics file
    :param session: dictionary with session specific fields
    :param templates: list of templates for this session type
    :return: list of all generated XML files
    """
    folder = output_path / templates[0].parent.name
    if not folder.is_dir():
        folder.mkdir(parents=True)
        with open(folder / ".gitignore.", "w") as f:
            f.write("*\n!summary.txt\n!.gitignore")
        with open(folder / "summary.txt", "w") as f:
            f.write("")

    out = []
    for template in templates:
        output_dir = folder / session["code"]
        output_dir.mkdir(exist_ok=True, parents=True)
        tree = adjust_xml(template, session, pre_scheduling_functions, output_dir)
        Message.log(False)

        newFile = output_dir / template.name
        out.append(newFile)
        tree.write(str(newFile), pretty_print=True)
    Message.log(True)
    return out


def start_uploading(settings):
    """
    start uploading process based on "upload_scheduler.txt"

    :return: None
    """
    today = datetime.date.today()
    with open("upload_scheduler.txt", "r") as f:
        lines = [l for l in f if l.strip()]

        for i, lin in enumerate(lines):
            path, time, status = lin.split()
            path = Path(path)
            program = path.parent.name
            target_date = datetime.datetime.strptime(time, "%Y-%m-%d").date()

            if status == "pending" and target_date == today:
                if program not in args.observing_programs:
                    Message.addMessage(f"skipping uploading program: {program} ({path.name})", dump="header")
                    continue

                Message.clearMessage("program")
                Message.clearMessage("session")
                Message.clearMessage("download")
                Message.clearMessage("log")

                upload = settings[program].get("upload", "no").lower()
                if upload == "ivs":
                    code = path.parent.name
                    Transfer.upload(path)
                    emails = Helper.read_emails(settings[program], args.fallback_email)
                    SendMail.writeMail_upload(code, emails)
                elif upload == "no":
                    pass
                elif upload == "gow":
                    code = path.parent.name
                    Transfer.upload_GOW_ftp(path)
                    emails = Helper.read_emails(settings[program], args.fallback_email)
                    SendMail.writeMail_upload(code, emails)
                else:
                    emails = upload.split(",")
                    with open(path / "selected" / "email.txt", "r") as f:
                        body = f.read()
                    SendMail.writeMail(path / "selected", emails, body, date=target_date)

                lines[i] = lin.replace("pending", "uploaded")

    with open("upload_scheduler.txt", "w") as f:
        for lout in lines:
            path, time, status = lout.split()
            target_date = datetime.datetime.strptime(time, "%Y-%m-%d").date()
            # do not list sessions older than 1 year in upload_scheduler.txt
            if target_date + datetime.timedelta(days=365) > today:
                f.write(lout)


def setup():
    settings = configparser.ConfigParser()
    if not Path("settings.ini").is_file():
        print("Please first generate a settings.ini file.")
        print("Have a look at the settings.ini.template file for further information.")
        print("VieSched++ AUTO is shutting down!")
        sys.exit(0)
    settings.read("settings.ini")

    if not Path("upload_scheduler.txt").is_file():
        with open("upload_scheduler.txt", "w"):
            pass

    if not (args.no_email or settings["general"].get("email_server","none").lower() != "none"):
        setup_mail(settings)

    if settings["general"].get("path_to_scheduler") is None:
        print("Path to scheduler not defined in settings.ini file!")
        print("Please list the path to the VieSched++ execuatable under the \"general\" block!")
        print("VieSched++ AUTO is shutting down!")
        sys.exit(0)

    if not Path(settings["general"].get("path_to_scheduler")).is_file():
        print(f"VieSched++ executable ({settings['general'].get('path_to_scheduler')} not found!")
        print("Pass path to VieSched++ executable via the '-s' flag")
        print("e.g.: python VieSchedpp_AUTO.py -s \"path/to/VieSched++/executable\"")
        print("VieSched++ AUTO is shutting down!")
        sys.exit(0)

    if (args.observing_programs is None) or ("ALL" in args.observing_programs):
        programs = []
        for group in settings:
            if group == "general" or group == "DEFAULT":
                continue
            programs.append(group)
        args.observing_programs = programs

    if args.date:
        for group in settings:
            if group == "general" or group == "DEFAULT":
                continue
            settings.set(group, "schedule_date", args.date)

    if args.session:
        for group in settings:
            if group == "general" or group == "DEFAULT":
                continue
            settings.set(group, "schedule_date", args.session)

    if args.test_mode:
        programs = []
        settings.set("general", "prefix_output_folder", "TEST")
        for group in settings:
            if group == "general" or group == "DEFAULT":
                continue
            programs.append(group)
            settings.set(group, "schedule_date", "next")
            settings.set(group, "upload", "No")
            try:
                f_pre = settings.get(group, "pre_scheduling_functions", fallback="")
                f_pre += ",test_mode"
                settings.set(group, "pre_scheduling_functions", f_pre)
                f_post = settings.get(group, "post_scheduling_functions", fallback="")
                if "update_source_list" in f_post:
                    f_post = f_post.replace("update_source_list", "")
                    f_post = f_post.replace(",,", ",")
                    settings.set(group, "post_scheduling_functions", f_post)
            except:
                settings.set(group, "pre_scheduling_functions", "test_mode")
        if not args.observing_programs:
            args.observing_programs = programs
        args.no_upload = True

    return settings


def setup_mail(settings):
    email_slot = settings["general"].get("email_server", "gmail").lower()
    if email_slot != "fromfile":
        SendMail.delegate_send(email_slot)
    else:
        if Path("email_function.txt").is_file():
            with open('email_function.txt') as f:
                c = f.read().strip().lower()
                SendMail.delegate_send(c)


if __name__ == "__main__":

    doc = "This program automatically generates VLBI schedules and uploads them to the IVS servers." \
          "Examples: python VieSchedpp_AUTO.py  -p INT2 INT3 " \
          "-e max.mustermann@outlook.com john.doe@gmail.com; would process INT2 and INT3 sessions. " \
          "The two email addresses provided are contacted in case an error occurred and VieSchedpp_AUTO.py crashes. " \
          "Processing parameters of the sessions are taken from the settings.ini file. "

    parser = argparse.ArgumentParser(description=doc)
    parser.add_argument("-e", "--fallback_email", default="mschartner@ethz.ch", nargs='+',
                        metavar="address",
                        help="potential error messages will be sent to these email addresses; "
                             "multiple email addresses can be given; "
                             "default: \"mschartner@ethz.ch\"")
    parser.add_argument("-p", "--observing_programs", nargs='+', metavar="programs",
                        help="list of observing programs that should be scheduled or uploaded (use \"ALL\" for all)")
    parser.add_argument("-ne", "--no_email", action="store_true",
                        help="use this option if you do not want to write any emails")
    parser.add_argument("-nd", "--no_download", action="store_true",
                        help="use this option if you do not want to download any catalogs or session masters")
    parser.add_argument("-nu", "--no_upload", action="store_true",
                        help="use this option if you do not want to upload any files (scheduling only)")
    parser.add_argument("-ns", "--no_scheduling", action="store_true",
                        help="use this option if you do not want generate any schedules (upload only)")
    # parser.add_argument("-nc", "--no_master_checks", action="store_true",
    #                     help="use this option if you do not want to do checks of changes in the master file")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-d", "--date", help="target schedule start date in format yyyy-mm-dd (e.g.: 2020-01-31). "
                                             "If omitted (default), information is taken from settings.ini file")
    group.add_argument("-s", "--session", help="Session name to be processed (from current year's master file).")
    group.add_argument("-t", "--test_mode", action="store_true",
                       help="use this option if you want to quickly process all templates with one schedule")

    args = parser.parse_args()
    try:

        if (args.fallback_email.count("@") == 1):
            args.fallback_email = [args.fallback_email]

        settings = setup()

        if args.observing_programs is None:
            print("No observing programs selected!")
            print("Pass observing program name as written in settings.ini file using the '-p' flag")
            print("e.g.: python VieSchedpp_AUTO.py -p INT1 INT2 INT3")
            sys.exit(0)

        if args.no_email:
            SendMail.changeSendMailsFlag(False)

        if not args.no_scheduling:
            print("===== START SCHEDULING =====")
            start_scheduling(settings)
        if not args.no_upload:
            print("===== START UPLOADING =====")
            start_uploading(settings)
        # if not args.no_master_checks:
        # print("===== START CHECKING MASTER SCHEDULE =====")
        # check_uploads(settings)
        print("VieSched++ AUTO finished")

    except BaseException as err:
        Message.addMessage("#### ERROR ####")
        Message.addMessage(traceback.format_exc())
        SendMail.writeErrorMail(args.fallback_email)
