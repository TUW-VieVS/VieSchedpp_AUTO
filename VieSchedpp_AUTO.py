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

import pandas as pd

import Plotting
import Transfer
import skd_parser.skd as skd_parser
from Helper import Message
from Helper import addStatistics
from Helper import readMaster
from Helper import update_uploadScheduler
from SendMail import SendMail
from XML_manipulation import adjust_xml


def start_scheduling(args):
    """
    start VieSched++ AUTO processing

    :return: None
    """
    settings = configparser.ConfigParser()
    settings.read("settings.ini")

    path_scheduler = args.scheduler

    if not os.path.exists("upload_scheduler.txt"):
        with open("upload_scheduler.txt", "w"):
            pass

    Message.addMessage("VieSched++ AUTO report", dump="header")
    today = datetime.date.today()
    Message.addMessage("date: {:%B %d, %Y}".format(today), dump="header")
    Message.addMessage("computer: {}, Python {}".format(platform.node(), platform.python_version()), dump="header")
    if args.institution:
        Message.addMessage("institution: {}".format(args.institution), dump="header")

    # download files
    if not args.no_download:
        Transfer.download_ftp()
        Transfer.download_http()
    else:
        Message.addMessage("no downloads", dump="header")

    # start processing all programs
    for program in settings.sections():
        if program not in args.observing_programs:
            Message.addMessage("skipping scheduling observing program: {}".format(program), dump="header")
            continue

        s_program = settings[program]
        emails = s_program.get("contact", args.fallback_email).split(",")
        delta_days = s_program.getint("schedule", 10)
        delta_days_upload = s_program.getint("upload", 7)
        intensive = s_program.getboolean("intensive", False)

        # read master files
        target_day = today + datetime.timedelta(days=delta_days)
        year = target_day.year % 100
        if intensive:
            master = os.path.join("MASTER", "master{:02d}-int.txt".format(year))
        else:
            master = os.path.join("MASTER", "master{:02d}.txt".format(year))
        sessions = readMaster(master)

        try:
            pattern = s_program["pattern"]
            fun = s_program["function"]
            f = globals()[fun]

            start(sessions, path_scheduler, program, pattern, f, emails, delta_days, delta_days_upload, intensive)
        except BaseException as err:
            SendMail().writeErrorMail(emails)


def start(master, path_scheduler, code, codeRegex, selectBest, emails, delta_days, delta_days_upload, intensive=False):
    """
    start auto processing for one observing program

    :param master: list of dictionaries with session specific fields read from session master
    :param path_scheduler: path to VieSched++ executable
    :param code: observing program code
    :param codeRegex: regular expression to match session name
    :param selectBest: function to select best schedule from statistics dataframe
    :param emails: list of email addresses
    :param delta_days: time offset in days from where schedule should be generated
    :param delta_days_upload: time offset in days when schedule should be updated
    :return: None
    """

    Message.clearMessage("program")
    pattern = re.compile(codeRegex)

    Message.addMessage("=== {} observing program ===".format(code), dump="program")
    Message.addMessage("contact:", dump="program")
    for email in emails:
        Message.addMessage("    {}".format(email), dump="program")

    today = datetime.date.today()
    target_day = today + datetime.timedelta(days=delta_days)
    Message.addMessage("date offset: {} days".format(delta_days), dump="program")
    Message.addMessage("target start time: {:%B %d, %Y}".format(target_day), dump="program")

    Message.addMessage("schedule master contained {} sessions".format(len(master)), dump="program")
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
        session["intensive"] = intensive
        Message.clearMessage("session")
        Message.clearMessage("log")
        Message.addMessage("##### {} #####".format(session["code"].upper()))
        Message.addMessage("{name} ({code}) start {date} duration {duration}h stations {stations}".format(**session))
        xmls = adjustTemplate(session, templates)
        xml_dir = os.path.dirname(xmls[0])
        df_list = []

        # loop over all templates
        for xml in xmls:
            Message.addMessage("   processing file: {}".format(xml))
            xml = os.path.abspath(xml)
            p = subprocess.run([path_scheduler, xml], cwd=xml_dir, capture_output=True, text=True)
            p.check_returncode()
            log = p.stdout
            Message.addMessage(log, dump="log")

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

        # find best schedule based on statistics
        best_idx = selectBest(stats)
        Message.addMessage("best version: v{:03d}".format(best_idx))
        Message.addMessage("this session will be uploaded on: {:%B %d, %Y}".format(
            today + datetime.timedelta(days=delta_days - delta_days_upload)))
        summary_file = os.path.join(os.path.dirname(xml_dir), "summary.txt")
        summary_df = addStatistics(stats, best_idx, session["code"].upper(), summary_file)

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

        update_uploadScheduler(xml_dir_selected, delta_days - delta_days_upload)

        try:
            skdFile = os.path.join(xml_dir_selected, "{}.skd".format(session["code"].lower()))
            skd = skd_parser.skdParser(skdFile)
            skd.parse()
            Plotting.summary(summary_df, xml_dir_selected)
            Plotting.polar_plots(skd, xml_dir_selected, "duration")
            Plotting.polar_plots(skd, xml_dir_selected, "start_time")
        except BaseException as err:
            Message.addMessage("ERROR during plotting: {}".format(err))

        SendMail().writeMail(xml_dir_selected, emails)


def selectBest_intensives(df):
    """
    logic to select best schedule for intensive sessions

    :param df: DataFrame of statistics.csv file
    :return: version number of best schedule
    """

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

    nobs = df["n_observations"]
    sky_cov = df["sky-coverage_average_37_areas_60_min"]
    dut1_mfe = df["sim_mean_formal_error_dUT1_[mus]"]
    dut1_rep = df["sim_repeatability_dUT1_[mus]"]
    # data = pd.concat([nobs, sky_cov, dut1_mfe, dut1_rep], axis=1)

    s_nobs = scale(nobs, minIsGood=False)
    s_sky_cov = scale(sky_cov, minIsGood=False)
    s_dut1_mfe = scale(dut1_mfe)
    s_dut1_rep = scale(dut1_rep)
    # scores = pd.concat([s_nobs, s_sky_cov, s_dut1_mfe, s_dut1_rep], axis=1)

    score = 1 * s_nobs + 1 * s_sky_cov + .5 * s_dut1_mfe + .5 * s_dut1_rep
    best = score.idxmax()
    return best


def selectBest_ohg(df):
    """
    logic to select best schedule for OHG sessions

    :param df: DataFrame of statistics.csv file
    :return: version number of best schedule
    """

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

    nobs = df["n_observations"]
    sky_cov = df["sky-coverage_average_25_areas_60_min"]
    avg_rep = df["sim_repeatability_average_3d_coordinates_[mm]"]
    ohg_rep = df["sim_repeatability_OHIGGINS"]
    avg_mfe = df["sim_mean_formal_error_average_3d_coordinates_[mm]"]
    ohg_mfe = df["sim_mean_formal_error_OHIGGINS"]
    # data = pd.concat([nobs, sky_cov, avg_rep, ohg_rep, avg_mfe, ohg_mfe], axis=1)

    s_nobs = scale(nobs, minIsGood=False)
    s_sky_cov = scale(sky_cov, minIsGood=False)
    s_rep_avg_sta = scale(avg_rep)
    s_rep_ohg = scale(ohg_rep)
    s_mfe_avg_sta = scale(avg_mfe)
    s_mfe_ohg = scale(ohg_mfe)
    # scores = pd.concat([s_nobs, s_sky_cov, s_rep_avg_sta, s_rep_ohg, s_mfe_avg_sta, s_mfe_ohg], axis=1)

    score = 1 * s_nobs + .25 * s_sky_cov + 1.5 * s_rep_ohg + 1 * s_mfe_ohg + .75 * s_rep_avg_sta + .5 * s_mfe_avg_sta
    best = score.idxmax()
    return best


def adjustTemplate(session, templates):
    """
    adjustes the template XML file with session specific fields

    :param session: dictionary with session specific fields
    :param templates: list of templates for this session type
    :return: list of all generated XML files
    """
    folder = os.path.join("Schedules", os.path.basename(os.path.dirname(templates[0])))
    if not os.path.exists(folder):
        os.makedirs(folder)
        with open(os.path.join(folder, ".gitignore."), "w") as f:
            f.write("*\n!summary.txt\n!.gitignore")
        with open(os.path.join(folder, "summary.txt"), "w") as f:
            f.write(",nsta,nsrc,nobs,nscans,skycov,stations\n")

    out = []
    for template in templates:
        tree = adjust_xml(template, session)

        output_dir = os.path.join(folder, session["code"])
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        newFile = os.path.join(output_dir, os.path.basename(template))
        out.append(newFile)
        tree.write(newFile, pretty_print=True)

    return out


def start_uploading():
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

                code = os.path.basename(os.path.dirname(path))
                Transfer.upload(path)
                SendMail().writeMail_upload(code, ["matthias.schartner@geo.tuwien.ac.at"])
                lines[i] = lin.replace("pending", "uploaded")

    with open("upload_scheduler.txt", "w") as f:
        for lout in lines:
            path, time, status = lout.split()
            target_date = datetime.datetime.strptime(time, "%Y-%m-%d").date()
            # do not list sessions older than 1 year in upload_scheduler.txt
            if target_date + datetime.timedelta(days=365) > today:
                f.write(lout)


if __name__ == "__main__":

    doc = "This program automatically generates VLBI schedules and uploads them to the IVS servers." \
          "Examples: python VieSchedpp_AUTO.py -s ../VieSchedpp/bin/VieSchedpp.exe -p INT2 INT3  -i \"TU Wien\" " \
          "-e max.mustermann@outlook.com john.doe@gmail.com; would process INT2 and INT3 sessions. " \
          "The two email addresses provided are contacted in case an error occurred and VieSchedpp_AUTO.py crashes. " \
          "Processing parameters of the sessions is taken from the settings.ini file. "

    parser = argparse.ArgumentParser(description=doc)
    parser.add_argument("-s", "--scheduler", default="./VieSchedpp.exe",
                        metavar="path_to_executable",
                        help="full path to the VieSched++ executable. Default: \"./VieSchedpp.exe\"")
    parser.add_argument("-e", "--fallback_email", default="matthias.schartner@geo.tuwien.ac.at", nargs='+',
                        metavar="address",
                        help="potential error messages will be sent to these email addresses; "
                             "multiple email addresses can be given; "
                             "default: \"matthias.schartner@geo.tuwien.ac.at\"")
    parser.add_argument("-p", "--observing_programs", nargs='+', metavar="programs",
                        help="list of observing programs that should be scheduled or uploaded")
    parser.add_argument("-i", "--institution", metavar="institution",
                        help='optional: define your institution name to be listed in the reports')
    parser.add_argument("-ne", "--no_email", action="store_true",
                        help="use this option if you do not want to write any emails")
    parser.add_argument("-nd", "--no_download", action="store_true",
                        help="use this option if you do not want to download any catalogs or session masters")
    parser.add_argument("-nu", "--no_upload", action="store_true",
                        help="use this option if you do not want to upload any files (scheduling only)")
    parser.add_argument("-ns", "--no_scheduling", action="store_true",
                        help="use this option if you do not want generate any schedules (upload only)")
    args = parser.parse_args()

    if not os.path.exists(args.scheduler):
        print("VieSched++ executable ({}) not found!".format(args.scheduler))
        print("Pass path to VieSched++ executable via the '-s' flag")
        print("e.g.: python VieSchedpp_AUTO.py -s \"path/to/VieSched++/executable\"")
        sys.exit(0)

    if args.no_email:
        SendMail().changeSendMailsFlag(False)

    if args.observing_programs is None:
        print("No observing program selected!")
        print("Pass observing program name as written in settings.ini file using the '-p' flag")
        print("e.g.: python VieSchedpp_AUTO.py -p INT1 INT2 INT3")
        sys.exit(0)

    try:
        if not args.no_scheduling:
            print("===== START SCHEDULING =====")
            start_scheduling(args)
        if not args.no_upload:
            print("===== START UPLOADING =====")
            start_uploading()
        print("VieSched++ AUTO finished")

    except BaseException as err:
        print(err)
        print(traceback.print_exc())
        SendMail().writeErrorMail(args.fallback_email)
