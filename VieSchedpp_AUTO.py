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
from string import Template

import pandas as pd

import Helper
import Plotting
import SendMail
import Transfer
import post_scheduling_functions
import pre_scheduling_functions
import select_best_functions
import skd_parser.skd as skd_parser
from Helper import Message
from XML_manipulation import adjust_xml
from check_uploads import check_uploads


def start_scheduling(settings):
    """
    start VieSched++ AUTO processing

    :return: None
    """
    prefix = Path(settings["general"].get("prefix_output_folder", "Schedules"))
    path_scheduler = settings["general"].get("path_to_scheduler")

    if not Path("upload_scheduler.txt").is_file():
        with open("upload_scheduler.txt", "w"):
            pass

    Message.addMessage("VieSched++ AUTO report", dump="header")
    today = datetime.date.today()
    Message.addMessage(f"date: {today:%B %d, %Y}", dump="header")
    Message.addMessage(f"computer: {platform.node()}, Python {platform.python_version()}", dump="header")
    if settings["general"].get("institute") is not None:
        Message.addMessage(f"institution: {settings['general'].get('institute')}", dump="header")
    Message.addMessage("This is an automatically generated message. Do NOT reply to this email directly!",
                       dump="header")
    # download files
    if not args.no_download:
        Transfer.download_ftp()
        Transfer.download_http()
    else:
        Message.addMessage("no downloads", dump="header")

    # start processing all programs
    for program in settings.sections():
        if program == "general":
            continue
        if program not in args.observing_programs:
            print(f"skipping scheduling observing program: {program}")
            continue

        s_program = settings[program]
        emails = Helper.read_emails(s_program, args.fallback_email)
        delta_days = s_program.get("schedule_date", "10")
        if args.date is not None:
            try:
                target_day = datetime.datetime.strptime(args.date, '%Y-%m-%d')
                delta_days = (target_day.date() - today).days
                syear = target_day.year % 100
                year = target_day.year
            except ValueError:
                print(f"ERROR while interpreting target date (-d option): {args.date}")
                print("    must be in format \"yyyy-mm-dd\" (e.g.: 2020-01-31)")
                return
        else:
            try:
                target_day = datetime.datetime.strptime(delta_days, '%Y-%m-%d')
                delta_days = (target_day.date() - today).days
                syear = target_day.year % 100
                year = target_day.year
            except ValueError:
                if delta_days.isnumeric():
                    delta_days = int(delta_days)
                    target_day = today + datetime.timedelta(days=delta_days)
                    syear = target_day.year % 100
                    year = target_day.year
                else:
                    delta_days = delta_days.lower()
                    syear = today.year % 100
                    year = today.year

        delta_days_upload = s_program.getint("upload_date", 7)
        statistic_field = s_program.get("statistics").split(",")
        upload = True
        if s_program.get("upload", "no").lower() == "no":
            upload = False

        # read master files
        template_master = Template(s_program.get("master", "master$YYYY.txt"))
        master = Path("MASTER") / template_master.substitute(YY=str(syear), YYYY=str(year))

        sessions = Helper.read_master(master)

        try:
            if sessions is None:
                raise FileNotFoundError

            pattern = s_program["pattern"]
            f = Helper.find_function(select_best_functions, s_program["function"])[0]
            f_pre = Helper.find_function(pre_scheduling_functions, s_program.get("pre_scheduling_functions", ""))
            f_post = Helper.find_function(post_scheduling_functions, s_program.get("post_scheduling_functions", ""))

            start(sessions, path_scheduler, program, pattern, f, emails, delta_days, delta_days_upload, statistic_field,
                  prefix, upload, f_pre, f_post)

        except:
            Message.addMessage("#### ERROR ####")
            Message.addMessage(traceback.format_exc())
            SendMail.writeErrorMail(emails)


def start(master, path_scheduler, code, code_regex, select_best, emails, delta_days, delta_days_upload, statistic_field,
          output_path=Path("./Schedules/"), upload=False, pre_fun=None, post_fun=None):
    """
    start auto processing for one observing program

    :param master: list of dictionaries with session specific fields read from session master
    :param path_scheduler: path to VieSched++ executable
    :param code: observing program code
    :param code_regex: regular expression to match session name
    :param select_best: function to select best schedule from statistics dataframe
    :param emails: list of email addresses
    :param statistic_field: fields to be stored in statistics file
    :param delta_days: time offset in days from where schedule should be generated
    :param delta_days_upload: time offset in days when schedule should be updated
    :param output_path: prefix for output path
    :param upload: flag if session needs to be uploaded
    :param pre_fun: list of functions executed prior to scheduling
    :param post_fun: list of functions executed after to scheduling
    :return: None
    """

    Message.clearMessage("program")
    pattern = re.compile(code_regex)

    Message.addMessage(f"=== {code} observing program ===", dump="program")
    Message.addMessage("contact:", dump="program")
    for email in emails:
        Message.addMessage(f"    {email}", dump="program")

    Message.addMessage(f"schedule master contained {len(master)} sessions", dump="program")
    today = datetime.date.today()
    sessions = []
    if delta_days == "next":
        offset = 0
        while not sessions:
            if offset > 0:
                Message.addMessage(f"no \"next\" schedule in master - checking {offset} days earlier", dump="program")
            if offset > 360:
                return
            for s in master:
                if s["date"].date() < today - datetime.timedelta(days=offset):
                    continue
                if s["type"] == code or pattern.match(s["name"]):
                    sessions.append(s)
                    break
            offset += 30
        upload = False
    else:
        target_day = today + datetime.timedelta(days=delta_days)
        Message.addMessage(f"date offset: {delta_days} days", dump="program")
        Message.addMessage(f"target start time: {target_day:%B %d, %Y}", dump="program")
        sessions = [s for s in master if (s["type"] == code or pattern.match(s["name"]))
                    and s["date"].date() == target_day]
    Message.addMessage(f"{len(sessions)} session(s) will be processed", dump="program")

    # get list of templates
    templates = list((Path("Templates") / code).glob("*.xml"))

    # loop over all sessions
    for session in sessions:
        if Helper.skip_session(code, session):
            continue
        Message.clearMessage("session")
        Message.clearMessage("log")
        Message.addMessage(f"##### {session['code'].upper()} #####")
        Message.addMessage("{name} ({code}) start {date} duration {duration}h stations {stations}".format(**session))
        xmls = adjust_template(output_path, session, templates, pre_fun)
        xml_dir = xmls[0].parent
        df_list = []

        flag_VLBA = any(["VLBA" in sta or "PIETOWN" in sta for sta in session["stations"]])
        flag_DSS = any([sta.startswith("DSS") for sta in session["stations"]])
        if flag_VLBA or flag_DSS:
            post_fun.append(post_scheduling_functions._vex_in_sked_format)
        if flag_VLBA:
            post_fun.append(post_scheduling_functions._vlba_vex_adjustments)

        # loop over all templates
        for xml in xmls:
            Message.addMessage(f"   processing file: {xml}")
            p = subprocess.run([path_scheduler, str(xml.absolute())], cwd=xml_dir, capture_output=True, text=True)
            log = p.stdout
            if log:
                Message.addMessage(log, dump="log")
            errlog = p.stderr
            if errlog:
                Message.addMessage(errlog, dump="log")
            p.check_returncode()

            # rename statistics.csv and simulation_summary file to avoid name clashes
            statistic_in = xml_dir / "statistics.csv"
            statistic_out = f"statistics_{xml.name}.csv"
            statistic_out = xml_dir/ statistic_out
            if statistic_out.is_file():
                statistic_out.unlink()
            statistic_in.rename(statistic_out)

            simulation_summary_in = xml_dir / "simulation_summary.txt"
            simulation_summary_out = f"simulation_summary_{xml.name}.txt"
            simulation_summary_out = xml_dir / simulation_summary_out
            if simulation_summary_out.is_file():
                simulation_summary_out.unlink()
            simulation_summary_in.rename(simulation_summary_out)

            # read statistics.csv file
            df = pd.read_csv(statistic_out, index_col=0)
            df_list.append(df)

        # concatenate all statistics.csv files
        stats = pd.concat(df_list)
        stats = stats.drop_duplicates()
        stats.sort_index(inplace=True)

        # find best schedule based on statistics
        best_idx = select_best(stats, template_path=xml.parent)
        Message.addMessage(f"best version: v{int(best_idx):03d}")
        if upload:
            Message.addMessage(f"this session will be uploaded on: {today + datetime.timedelta(days=delta_days - delta_days_upload):%B %d, %Y}")
            if delta_days - delta_days_upload < 1:
                Message.addMessage("[WARNING]: upload date already passed!")
        else:
            Message.addMessage("this session will NOT be uploaded!")

        summary_file = xml_dir.parent / "summary.txt"
        summary_df = Helper.addStatistics(stats, best_idx, session["code"].upper(), summary_file)

        # copy best schedule to selected folder
        version_pattern = f"_v{best_idx:03d}"
        version_pattern_regex = re.compile(version_pattern + r'[^\d]')
        bestFiles = [f for f in xml_dir.glob(f"*{version_pattern}*") if version_pattern_regex.search(f.name)]
        xml_dir_selected = xml_dir / "selected"

        if xml_dir_selected.is_dir():
            shutil.rmtree(xml_dir_selected)

        xml_dir_selected.mkdir(exist_ok=True, parents=True)
        for f in bestFiles:
            fname = f.name.replace(version_pattern, "")
            destination = xml_dir_selected / fname
            shutil.copy(f, destination)
        stats.to_csv(xml_dir_selected / "merged_statistics.csv")

        if upload:
            Helper.update_uploadScheduler(xml_dir_selected, delta_days - delta_days_upload, upload)

        try:
            skdFile = xml_dir_selected / f"{session['code'].lower()}.skd"
            skd = skd_parser.skdParser(skdFile)
            skd.parse()
            fields = settings[code].get("statistics").split(",")
            Plotting.summary(summary_df, fields, xml_dir_selected)
            Plotting.polar_plots(skd, xml_dir_selected, "duration")
            Plotting.polar_plots(skd, xml_dir_selected, "start_time")
            Plotting.close_all()
        except:
            Message.addMessage("#### ERROR ####")
            Message.addMessage(traceback.format_exc())

        for post_f in post_fun:
            post_f(path=xml_dir_selected, ds=stats.loc[best_idx, :], session=session, program_code=code, version=best_idx)

        SendMail.writeMail(xml_dir_selected, emails, date=session["date"])
        delete_files(xml_dir)


def delete_files(folder):
    for f in folder.iterdir():
        if "VieSchedpp" in f.name or f.is_dir() or f.suffix == ".csv":
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
    parser.add_argument("-nc", "--no_master_checks", action="store_true",
                        help="use this option if you do not want to do checks of changes in the master file")
    parser.add_argument("-t", "--test_mode", action="store_true",
                        help="use this option if you want to quickly process all templates with one schedule")
    parser.add_argument("-d", "--date", help="target schedule start date in format yyyy-mm-dd (e.g.: 2020-01-31). "
                                             "If omitted (default), information is taken from settings.ini file")

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
        if not args.no_master_checks:
            print("===== START CHECKING MASTER SCHEDULE =====")
            check_uploads(settings)
        print("VieSched++ AUTO finished")

    except BaseException as err:
        Message.addMessage("#### ERROR ####")
        Message.addMessage(traceback.format_exc())
        SendMail.writeErrorMail(args.fallback_email)
