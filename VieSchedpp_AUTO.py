import argparse
import configparser
import datetime
import glob
import os
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


def start_scheduling(settings):
    """
    start VieSched++ AUTO processing

    :return: None
    """
    prefix = settings["general"].get("prefix_output_folder", "Schedules")
    if os.sep == "\\":
        prefix = prefix.replace("/", "\\")

    path_scheduler = settings["general"].get("path_to_scheduler")

    if not os.path.exists("upload_scheduler.txt"):
        with open("upload_scheduler.txt", "w"):
            pass

    Message.addMessage("VieSched++ AUTO report", dump="header")
    today = datetime.date.today()
    Message.addMessage("date: {:%B %d, %Y}".format(today), dump="header")
    Message.addMessage("computer: {}, Python {}".format(platform.node(), platform.python_version()), dump="header")
    if settings["general"].get("institute") is not None:
        Message.addMessage("institution: {}".format(settings["general"].get("institute")), dump="header")
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
            print("skipping scheduling observing program: {}".format(program))
            continue

        s_program = settings[program]
        emails = Helper.read_emails(s_program, args.fallback_email)
        delta_days = s_program.get("schedule_date", "10")
        if args.date is not None:
            try:
                target_day = datetime.datetime.strptime(args.date, '%Y-%m-%d')
                delta_days = (target_day.date() - today).days
                year = target_day.year % 100
            except ValueError:
                print("ERROR while interpreting target date (-d option): {}".format(args.date))
                print("    must be in format \"yyyy-mm-dd\" (e.g.: 2020-01-31)")
                return
        else:
            try:
                target_day = datetime.datetime.strptime(delta_days, '%Y-%m-%d')
                delta_days = (target_day.date() - today).days
                year = target_day.year % 100
            except ValueError:
                if delta_days.isnumeric():
                    delta_days = int(delta_days)
                    target_day = today + datetime.timedelta(days=delta_days)
                    year = target_day.year % 100
                else:
                    delta_days = delta_days.lower()
                    year = today.year % 100

        delta_days_upload = s_program.getint("upload_date", 7)
        statistic_field = s_program.get("statistics").split(",")
        upload = True
        if s_program.get("upload", "no").lower() == "no":
            upload = False

        # read master files
        template_master = Template(s_program.get("master", "master$YY.txt"))
        master = template_master.substitute(YY=str(year))

        master = os.path.join("MASTER", master)
        sessions = Helper.read_master(master)

        try:
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
          output_path="./Schedules/", upload=False, pre_fun=None, post_fun=None):
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

    Message.addMessage("=== {} observing program ===".format(code), dump="program")
    Message.addMessage("contact:", dump="program")
    for email in emails:
        Message.addMessage("    {}".format(email), dump="program")

    Message.addMessage("schedule master contained {} sessions".format(len(master)), dump="program")
    today = datetime.date.today()
    sessions = []
    if delta_days == "next":
        for s in master:
            if s["date"].date() < today:
                continue
            if pattern.match(s["name"]):
                sessions.append(s)
                break
        upload = False
    else:
        target_day = today + datetime.timedelta(days=delta_days)
        Message.addMessage("date offset: {} days".format(delta_days), dump="program")
        Message.addMessage("target start time: {:%B %d, %Y}".format(target_day), dump="program")
        sessions = [s for s in master if pattern.match(s["name"]) if s["date"].date() == target_day]
    Message.addMessage("{} session(s) will be processed".format(len(sessions)), dump="program")

    # get list of templates
    templates = []
    template_path = os.path.join("Templates", code)
    for file in os.listdir(template_path):
        if file.endswith(".xml"):
            templates.append(os.path.join(template_path, file))

    # loop over all sessions
    for session in sessions:
        Message.clearMessage("session")
        Message.clearMessage("log")
        Message.addMessage("##### {} #####".format(session["code"].upper()))
        Message.addMessage("{name} ({code}) start {date} duration {duration}h stations {stations}".format(**session))
        xmls = adjust_template(output_path, session, templates, pre_fun)
        xml_dir = os.path.dirname(xmls[0])
        df_list = []

        flag_VLBA = any(["VLBA" in sta or "PIETOWN" in sta for sta in session["stations"]])
        flag_DSS = any([sta.startswith("DSS") for sta in session["stations"]])
        if flag_VLBA or flag_DSS:
            post_fun.append(post_scheduling_functions._vex_in_sked_format)
        if flag_VLBA:
            post_fun.append(post_scheduling_functions._vlba_vex_adjustments)

        # loop over all templates
        for xml in xmls:
            Message.addMessage("   processing file: {}".format(xml))
            xml = os.path.abspath(xml)
            p = subprocess.run([path_scheduler, xml], cwd=xml_dir, capture_output=True, text=True)
            log = p.stdout
            if log:
                Message.addMessage(log, dump="log")
            errlog = p.stderr
            if errlog:
                Message.addMessage(errlog, dump="log")
            p.check_returncode()

            # rename statistics.csv and simulation_summary file to avoid name clashes
            statistic_in = os.path.join(xml_dir, "statistics.csv")
            statistic_out = "statistics_{}.csv".format(os.path.basename(os.path.splitext(xml)[0]))
            statistic_out = os.path.join(xml_dir, statistic_out)
            if os.path.exists(statistic_out):
                os.remove(statistic_out)
            os.rename(statistic_in, statistic_out)

            simulation_summary_in = os.path.join(xml_dir, "simulation_summary.txt")
            simulation_summary_out = "simulation_summary_{}.txt".format(os.path.basename(os.path.splitext(xml)[0]))
            simulation_summary_out = os.path.join(xml_dir, simulation_summary_out)
            if os.path.exists(simulation_summary_out):
                os.remove(simulation_summary_out)
            os.rename(simulation_summary_in, simulation_summary_out)

            # read statistics.csv file
            df = pd.read_csv(statistic_out, index_col=0)
            df_list.append(df)

        # concatenate all statistics.csv files
        stats = pd.concat(df_list)
        stats = stats.drop_duplicates()
        stats.sort_index(inplace=True)

        # find best schedule based on statistics
        best_idx = select_best(stats, template_path=template_path)
        Message.addMessage("best version: v{:03d}".format(best_idx))
        if upload:
            Message.addMessage("this session will be uploaded on: {:%B %d, %Y}".format(
                today + datetime.timedelta(days=delta_days - delta_days_upload)))
            if delta_days - delta_days_upload < 1:
                Message.addMessage("[WARNING]: upload date already passed!")
        else:
            Message.addMessage("this session will NOT be uploaded!")

        summary_file = os.path.join(os.path.dirname(xml_dir), "summary.txt")
        summary_df = Helper.addStatistics(stats, best_idx, statistic_field, session["code"].upper(), summary_file)

        # copy best schedule to selected folder
        version_pattern = "_v{:03d}".format(best_idx)
        bestFiles = glob.glob(os.path.join(xml_dir, "*{}*".format(version_pattern)))
        xml_dir_selected = os.path.join(xml_dir, "selected")

        if os.path.exists(xml_dir_selected):
            shutil.rmtree(xml_dir_selected)

        os.makedirs(xml_dir_selected)
        for f in bestFiles:
            fname = os.path.basename(f).replace(version_pattern, "")
            destination = os.path.join(xml_dir_selected, fname)
            shutil.copy(f, destination)
        stats.to_csv(os.path.join(xml_dir_selected, "merged_statistics.csv"))

        if upload:
            Helper.update_uploadScheduler(xml_dir_selected, delta_days - delta_days_upload, upload)

        try:
            skdFile = os.path.join(xml_dir_selected, "{}.skd".format(session["code"].lower()))
            skd = skd_parser.skdParser(skdFile)
            skd.parse()
            Plotting.summary(summary_df, xml_dir_selected)
            Plotting.polar_plots(skd, xml_dir_selected, "duration")
            Plotting.polar_plots(skd, xml_dir_selected, "start_time")
            Plotting.close_all()
        except:
            Message.addMessage("#### ERROR ####")
            Message.addMessage(traceback.format_exc())

        for post_f in post_fun:
            post_f(path=xml_dir_selected, ds=stats.loc[best_idx, :], session=session, program_code=code)

        SendMail.writeMail(xml_dir_selected, emails, date=session["date"])


def adjust_template(output_path, session, templates, pre_scheduling_functions):
    """
    adjustes the template XML file with session specific fields

    :param output_path: fields to be stored in statistics file
    :param session: dictionary with session specific fields
    :param templates: list of templates for this session type
    :return: list of all generated XML files
    """
    folder = os.path.join(output_path, os.path.basename(os.path.dirname(templates[0])))
    if not os.path.exists(folder):
        os.makedirs(folder)
        with open(os.path.join(folder, ".gitignore."), "w") as f:
            f.write("*\n!summary.txt\n!.gitignore")
        with open(os.path.join(folder, "summary.txt"), "w") as f:
            f.write("")

    out = []
    for template in templates:
        tree = adjust_xml(template, session, pre_scheduling_functions)
        Message.log(False)

        output_dir = os.path.join(folder, session["code"])
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        newFile = os.path.join(output_dir, os.path.basename(template))
        out.append(newFile)
        tree.write(newFile, pretty_print=True)
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
            program = os.path.basename(os.path.dirname(path))
            target_date = datetime.datetime.strptime(time, "%Y-%m-%d").date()

            if status == "pending" and target_date == today:
                if program not in args.observing_programs:
                    Message.addMessage("skipping uploading program: {} ({})".format(program, os.path.basename(path)),
                                       dump="header")
                    continue

                Message.clearMessage("program")
                Message.clearMessage("session")
                Message.clearMessage("download")
                Message.clearMessage("log")

                upload = settings[program].get("upload", "no").lower()
                if upload == "ivs":
                    code = os.path.basename(os.path.dirname(path))
                    Transfer.upload(path)
                    emails = Helper.read_emails(settings[program], args.fallback_email)
                    SendMail.writeMail_upload(code, emails)
                elif upload == "no":
                    pass
                elif upload == "gow":
                    code = os.path.basename(os.path.dirname(path))
                    Transfer.upload_GOW_ftp(path)
                    emails = Helper.read_emails(settings[program], args.fallback_email)
                    SendMail.writeMail_upload(code, emails)
                else:
                    emails = upload.split(",")
                    with open(os.path.join(path, "selected", "email.txt"), "r") as f:
                        body = f.read()
                    SendMail.writeMail(os.path.join(path, "selected"), emails, body, date=target_date)

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
    if not os.path.exists("settings.ini"):
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

    if not os.path.exists(settings["general"].get("path_to_scheduler")):
        print("VieSched++ executable ({}) not found!".format(settings["general"].get("path_to_scheduler")))
        print("Pass path to VieSched++ executable via the '-s' flag")
        print("e.g.: python VieSchedpp_AUTO.py -s \"path/to/VieSched++/executable\"")
        print("VieSched++ AUTO is shutting down!")
        sys.exit(0)

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
                f_pre = settings.get(group, "pre_scheduling_functions")
                f_pre += ",test_mode"
                settings.set(group, "pre_scheduling_functions", f_pre)
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
        if os.path.exists("email_function.txt"):
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
    parser.add_argument("-e", "--fallback_email", default="matthias.schartner@geo.tuwien.ac.at", nargs='+',
                        metavar="address",
                        help="potential error messages will be sent to these email addresses; "
                             "multiple email addresses can be given; "
                             "default: \"matthias.schartner@geo.tuwien.ac.at\"")
    parser.add_argument("-p", "--observing_programs", nargs='+', metavar="programs",
                        help="list of observing programs that should be scheduled or uploaded")
    parser.add_argument("-ne", "--no_email", action="store_true",
                        help="use this option if you do not want to write any emails")
    parser.add_argument("-nd", "--no_download", action="store_true",
                        help="use this option if you do not want to download any catalogs or session masters")
    parser.add_argument("-nu", "--no_upload", action="store_true",
                        help="use this option if you do not want to upload any files (scheduling only)")
    parser.add_argument("-ns", "--no_scheduling", action="store_true",
                        help="use this option if you do not want generate any schedules (upload only)")
    parser.add_argument("-t", "--test_mode", action="store_true",
                        help="use this option if you want to quickly process all templates with one schedule")
    parser.add_argument("-d", "--date", help="target schedule start date in format yyyy-mm-dd (e.g.: 2020-01-31). "
                                             "If omitted (default), information is taken from settings.ini file")

    args = parser.parse_args()

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

    try:
        if not args.no_scheduling:
            print("===== START SCHEDULING =====")
            start_scheduling(settings)
        if not args.no_upload:
            print("===== START UPLOADING =====")
            start_uploading(settings)
        print("VieSched++ AUTO finished")

    except BaseException as err:
        Message.addMessage("#### ERROR ####")
        Message.addMessage(traceback.format_exc())
        SendMail.writeErrorMail(args.fallback_email)
