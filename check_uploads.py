import datetime
import re
from string import Template
from pathlib import Path
from ftplib import FTP_TLS
from ftplib import all_errors as ftp_errors
from SendMail import missing_schedule, network_changed
import skd_parser.skd as skd_parser

from Helper import read_emails, read_master


def check_uploads(settings, fallback_email=""):
    today = datetime.date.today()
    root = Path("tmp_download")
    root.mkdir(exist_ok=True, parents=True)

    for program in settings.sections():
        if program == "general":
            continue
        if program.startswith("GOW"):
            continue
        if settings[program].get("upload").lower() != "ivs":
            continue

        s_program = settings[program]
        pattern = re.compile(s_program["pattern"])
        emails = read_emails(s_program, fallback_email)
        delta_days = s_program.getint("upload_date", 10)

        for dt in range(delta_days):
            target_day = today + datetime.timedelta(days=dt)
            year = target_day.year % 100
            year_long = target_day.year

            # read master files
            template_master = Template(s_program.get("master", "master$YY.txt"))
            master = template_master.substitute(YY=str(year), YYYY=str(year_long))

            master = Path("MASTER") / master
            sessions = read_master(master)
            if not sessions:
                continue

            sessions = [s for s in sessions if s["date"].date() == target_day and pattern.match(s["name"])]

            for s in sessions:
                name = f"{s['code'].lower()}.skd"
                folder = f"pub/vlbi/ivsdata/aux/{2000 + year}/{s['code'].lower()}/"

                # download skd file
                try:
                    # connect to FTP server
                    ftp = FTP_TLS("ivs.bkg.bund.de", user="anonymous", passwd="anonymous")
                    ftp.prot_p()
                    ftp.set_pasv(True)

                    ftp.cwd(folder)

                    out = root / name

                    msg = ftp.retrbinary("RETR " + name, open(out, 'wb').write)

                except ftp_errors as err:
                    missing_schedule(s, program, emails)
                    continue

                # read .skd file to get network
                skd = skd_parser.skdParser(out)
                skd.parse()
                skd_stations = [s.name for s in skd.stations]
                master_stations = s["stations"]

                # check if networks are the same
                network_same = True
                for sta in master_stations:
                    if sta not in skd_stations:
                        network_same = False
                for sta in skd_stations:
                    if sta not in master_stations:
                        network_same = False

                # if not write email
                if not network_same:
                    network_changed(s, program, skd_stations, emails)

    # delete all downloads
    for f in root.iterdir():
        f.unlink()
    pass
