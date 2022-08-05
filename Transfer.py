import datetime
from pathlib import Path
import os
import time
import traceback
from ftplib import FTP, FTP_TLS
from ftplib import all_errors as ftp_errors
from bs4 import BeautifulSoup

import requests

from Helper import Message


def download_ftp():
    """
    download session master files

    :return: None
    """

    # master files are stored in "MASTER" directory
    path = Path("MASTER")
    path.mkdir(exist_ok=True, parents=True)

    # define files do download
    now = datetime.datetime.now()
    year = now.year % 100
    names = [f"master{year:02d}.txt",
             f"master{year:02d}-int.txt",
             f"mediamaster{year:02d}.txt"]

    # also download master file for next year in case today is December
    if now.month == 12:
        names.append(f"master{year + 1:02d}.txt")
        names.append(f"master{year + 1:02d}-int.txt")
        names.append(f"mediamaster{year + 1:02d}.txt")

    try:
        # connect to FTP server
        ftp = FTP("ivsopar.obspm.fr")
        ftp.login()
        ftp.cwd("pub/vlbi/ivscontrol")

        # get a list of all files at FTP server
        ftp_files = ftp.nlst()

        # download all files from FTP server
        for name in names:
            Message.addMessage(f"FTP download: {name}... ", dump="download", endLine=False)
            # skip files which are not present
            if name not in ftp_files:
                Message.addMessage("file not found", dump="download")
                continue
            out = path / name
            msg = ftp.retrbinary("RETR " + name, open(out, 'wb').write)
            Message.addMessage(f"msg: {msg}", dump="download")

    except ftp_errors as err:
        Message.addMessage(f"#### ERROR {err} ####", dump="download")
        Message.addMessage(traceback.format_exc(), dump="download")


def download_http():
    """
    download most recent CATALOG files

    :return: None
    """
    path = Path("MASTER")
    path.mkdir(exist_ok=True, parents=True)
    now = datetime.datetime.now()
    year = now.year % 100
    masters = []
    # masters = [(os.path.join(path, "master{:02d}-int-SI.txt".format(year)),
    #             "https://www.vlbi.at/wp-content/uploads/2020/06/master20-int-SI.txt")]

    for cat in masters:
        url_response(cat)

    Message.addMessage(f"HTTPS download of stp files", dump="download")
    try:
        path = Path("STP")
        path.mkdir(exist_ok=True, parents=True)
        archive_url = "http://astrogeo.org/cont/stp/"
        main_r = requests.get(archive_url)
        main_soup = BeautifulSoup(main_r.content, 'html5lib')
        astrogeo_links = main_soup.findAll('a')
        stp_links = [archive_url + l['href'] for l in astrogeo_links if l['href'].endswith(".stp")]

        for link in stp_links:
            name = link.split("/")[-1]
            url_response((path / name, link), False)
    except Exception as e:
        Message.addMessage(f"ERROR downloading STP files from astrogeo.org {e}")

    path = Path("CATALOGS")
    catalogs = [(path / "antenna.cat", "https://raw.githubusercontent.com/nvi-inc/sked_catalogs/main/antenna.cat"),
                (path / "equip.cat", "https://raw.githubusercontent.com/nvi-inc/sked_catalogs/main/equip.cat"),
                (path / "flux.cat", "https://raw.githubusercontent.com/nvi-inc/sked_catalogs/main/flux.cat"),
                (path / "freq.cat", "https://raw.githubusercontent.com/nvi-inc/sked_catalogs/main/freq.cat"),
                (path / "hdpos.cat", "https://raw.githubusercontent.com/nvi-inc/sked_catalogs/main/hdpos.cat"),
                (path / "loif.cat", "https://raw.githubusercontent.com/nvi-inc/sked_catalogs/main/loif.cat"),
                (path / "mask.cat", "https://raw.githubusercontent.com/nvi-inc/sked_catalogs/main/mask.cat"),
                (path / "modes.cat", "https://raw.githubusercontent.com/nvi-inc/sked_catalogs/main/modes.cat"),
                (path / "position.cat", "https://raw.githubusercontent.com/nvi-inc/sked_catalogs/main/position.cat"),
                (path / "rec.cat", "https://raw.githubusercontent.com/nvi-inc/sked_catalogs/main/rec.cat"),
                (path / "rx.cat", "https://raw.githubusercontent.com/nvi-inc/sked_catalogs/main/rx.cat"),
                (path / "source.cat.geodetic.good",
                 "https://raw.githubusercontent.com/nvi-inc/sked_catalogs/main/source.cat.geodetic.good"),
                (path / "tracks.cat", "https://raw.githubusercontent.com/nvi-inc/sked_catalogs/main/tracks.cat")]

    # catalogs = []

    # ThreadPool(13).imap_unordered(url_response, catalogs)

    for cat in catalogs:
        url_response(cat)


def url_response(cat, message_flag=True):
    """
    download a single file from https and store

    primarily used to download the CATALOG files

    :param cat: (output_path, download_url)
    :param message_flag: output message (default = True)
    :return: None
    """
    path, url = cat

    # only download file if current file was last modified longer than 23 hours ago
    if message_flag:
        Message.addMessage(f"HTTPS download: {path.name}... ", dump="download", endLine=False)
    if path.is_file():
        last_update = os.path.getmtime(path)
        now = datetime.datetime.now()
        new_update = time.mktime(now.timetuple())
        diff = new_update - last_update
        if diff < 23 * 3600:
            if message_flag:
                Message.addMessage(f"up to date (last modified {diff / 3600.0:.2f} hours ago) -> no download",
                                   dump="download")
            return

    try:
        # download new file
        r = requests.get(url, stream=True)
        if r.ok:
            with open(path, 'wb') as f:
                for ch in r:
                    f.write(ch)
                if message_flag:
                    Message.addMessage("successful", dump="download")
        else:
            Message.addMessage("ERROR", dump="download")

    except requests.exceptions.RequestException as err:
        Message.addMessage(f"#### ERROR {err} ####", dump="download")
        Message.addMessage(traceback.format_exc(), dump="download")


def upload(path):
    """
    upload to IVS-BKG server using ftp

    :param path: path to session
    :return: None
    """
    path = path / "selected"
    code = path.parent.name

    skdFile = list(path.glob("*.skd"))[0]
    txtFile = skdFile.parent / (skdFile.stem + ".txt")
    vexFile = skdFile.parent / (skdFile.stem + ".vex")

    today = datetime.date.today()
    Message.addMessage(f"##### {code} #####\n", dump="download")
    Message.addMessage("connecting to: ivs.bkg.bund.de\n", dump="download")

    user, pw = read_pw_from_file(Path("BKG_pw.txt"))
    if pw is not None:
        ftp = FTP_TLS("ivs.bkg.bund.de", user=user, passwd=pw)
        ftp.prot_p()

        ftp.login(user, pw)  # *** INSERT USER AND PASSWORD HERE (replace user, pw) ***
        ftp.set_pasv(True)

        Message.addMessage("uploading files to BKG server", dump="download")

        Message.addMessage("\nserver content before upload:", dump="log")
        # get a list of all files at FTP server
        content = []
        ftp.retrlines('LIST', content.append)
        for l1 in content:
            Message.addMessage(l1, dump="log")

        Message.addMessage("\nuploading:", dump="download")
        for file in [skdFile, txtFile, vexFile]:
            Message.addMessage(f"    {file}... ", endLine=False, dump="download")
            with open(file, 'rb') as f:
                msg = ftp.storbinary(f'STOR {file.name}', f)
            Message.addMessage(msg, dump="download")

        # get a list of all files at FTP server
        Message.addMessage("\nserver content after upload:", dump="log")
        content = []
        ftp.retrlines('LIST', content.append)
        for l2 in content:
            Message.addMessage(l2, dump="log")
    else:
        Message.addMessage("No password for IVS BKG server was provided. Please store username and password in a "
                           "\"BKG_pw.txt\" file  (seperated by a whitespace) or insert password in source code "
                           "(See file \"Transfer.py\" line with comment "
                           "\"*** INSERT PASSWORD HERE (replace pw) ***\"", dump="log")


def upload_GOW_ftp(path):
    """
    upload to GOW server using ftp

    :param path: path to session
    :return: None
    """
    flag = True
    path = path / "selected"
    code = path.parent.name

    skdFile = list(path.glob("*.skd"))[0]
    txtFile = skdFile.parent / (skdFile.stem + ".txt")
    vexFile = skdFile.parent / (skdFile.stem + ".vex")

    today = datetime.date.today()
    Message.addMessage(f"##### {code} #####\n", dump="download")
    Message.addMessage("connecting to: 141.74.2.12\n", dump="download")

    user, pw = read_pw_from_file("GOW_ftp_pw.txt")
    if pw is not None:
        ftp = FTP("141.74.1.12")
        ftp.login(user, pw)  # *** INSERT USER AND PASSWORD HERE (replace user, pw) ***
        ftp.set_pasv(True)

        Message.addMessage("uploading files to GOW ftp server", dump="download")

        Message.addMessage("\nserver content before upload:", dump="log")
        # get a list of all files at FTP server
        content = []
        ftp.retrlines('LIST', content.append)
        for l1 in content:
            Message.addMessage(l1, dump="log")

        Message.addMessage("\nuploading:", dump="download")
        ftp.mkd(code)
        ftp.cwd(code)
        for file in [skdFile, txtFile, vexFile]:
            Message.addMessage(f"    {file}... ", endLine=False, dump="download")
            with open(file, 'rb') as f:
                msg = ftp.storbinary(f'STOR {file.name}', f)
            Message.addMessage(msg, dump="download")
        ftp.cwd("..")

        # get a list of all files at FTP server
        Message.addMessage("\nserver content after upload:", dump="log")
        content = []
        ftp.retrlines('LIST', content.append)
        for l2 in content:
            Message.addMessage(l2, dump="log")
    else:
        Message.addMessage("No password for GOW FTP server was provided. Please store password in a \"GOW_ftp_pw.txt\" "
                           "file or insert password in source code (See file \"Transfer.py\" line with comment "
                           "\"*** INSERT PASSWORD HERE (replace pw) ***\"", dump="log")


def read_pw_from_file(file):
    if file.is_file():
        with open(file) as f:
            return f.read().strip().split()
    else:
        return ("", "")


if __name__ == "__main__":
    user, pw = read_pw_from_file(Path("BKG_pw.txt"))
    ftp = FTP_TLS("ivs.bkg.bund.de", user=user, passwd=pw)
    content = []
    ftp.retrlines('LIST', content.append)

    for file in [Path("/home/mschartner/tmp/s22130.skd")]:
        with open(file, 'rb') as f:
            msg = ftp.storbinary(f'STOR {file.name}', f)

    content2 = []
    ftp.retrlines('LIST', content2.append)
    pass
