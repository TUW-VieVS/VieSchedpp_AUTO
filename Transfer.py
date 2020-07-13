import datetime
import glob
import os
import time
from ftplib import FTP
from ftplib import all_errors as ftp_errors
import traceback

import requests

from Helper import Message


def download_ftp():
    """
    download session master files

    :return: None
    """

    # master files are stored in "MASTER" directory
    path = "MASTER"
    if not os.path.exists(path):
        os.makedirs(path)

    # define files do download
    now = datetime.datetime.now()
    year = now.year % 100
    names = ["master{:02d}.txt".format(year),
             "master{:02d}-int.txt".format(year),
             "mediamaster{:02d}.txt".format(year)]

    # also download master file for next year in case today is December
    if now.month == 12:
        names.append("master{:02d}.txt".format(year + 1))
        names.append("master{:02d}-int.txt".format(year + 1))
        names.append("mediamaster{:02d}.txt".format(year + 1))

    try:
        # connect to FTP server
        ftp = FTP("cddis.gsfc.nasa.gov")
        ftp.login()
        ftp.cwd("pub/vlbi/ivscontrol")

        # get a list of all files at FTP server
        ftp_files = ftp.nlst()

        # download all files from FTP server
        for name in names:
            Message.addMessage("FTP download: {}... ".format(name), dump="download", endLine=False)
            # skip files which are not present
            if name not in ftp_files:
                Message.addMessage("file not found", dump="download")
                continue
            out = os.path.join(path, name)
            msg = ftp.retrbinary("RETR " + name, open(out, 'wb').write)
            Message.addMessage("msg: {}".format(msg), dump="download")

    except ftp_errors as err:
        Message.addMessage("#### ERROR {} ####".format(err), dump="download")
        Message.addMessage(traceback.format_exc(), dump="download")
    except:
        Message.addMessage("#### ERROR ####", dump="download")
        Message.addMessage(traceback.format_exc(), dump="download")


def download_http():
    """
    download most recent CATALOG files

    :return: None
    """
    path = "MASTER"
    if not os.path.exists(path):
        os.makedirs(path)
    now = datetime.datetime.now()
    year = now.year % 100
    masters = [(os.path.join(path, "master{:02d}-int-SI.txt".format(year)),
                "https://www.vlbi.at/wp-content/uploads/2020/06/master20-int-SI.txt")]

    for cat in masters:
        url_response(cat)

    path = "CATALOGS"
    if not os.path.exists(path):
        os.makedirs(path)

    catalogs = [(os.path.join(path, "antenna.cat"), "https://ivscc.gsfc.nasa.gov/IVS_AC/sked_cat/antenna.cat"),
                (os.path.join(path, "equip.cat"), "https://ivscc.gsfc.nasa.gov/IVS_AC/sked_cat/equip.cat"),
                (os.path.join(path, "flux.cat"), "https://ivscc.gsfc.nasa.gov/IVS_AC/sked_cat/flux.cat"),
                (os.path.join(path, "freq.cat"), "https://ivscc.gsfc.nasa.gov/IVS_AC/sked_cat/freq.cat"),
                (os.path.join(path, "hdpos.cat"), "https://ivscc.gsfc.nasa.gov/IVS_AC/sked_cat/hdpos.cat"),
                (os.path.join(path, "loif.cat"), "https://ivscc.gsfc.nasa.gov/IVS_AC/sked_cat/loif.cat"),
                (os.path.join(path, "mask.cat"), "https://ivscc.gsfc.nasa.gov/IVS_AC/sked_cat/mask.cat"),
                (os.path.join(path, "modes.cat"), "https://ivscc.gsfc.nasa.gov/IVS_AC/sked_cat/modes.cat"),
                (os.path.join(path, "position.cat"), "https://ivscc.gsfc.nasa.gov/IVS_AC/sked_cat/position.cat"),
                (os.path.join(path, "rec.cat"), "https://ivscc.gsfc.nasa.gov/IVS_AC/sked_cat/rec.cat"),
                (os.path.join(path, "rx.cat"), "https://ivscc.gsfc.nasa.gov/IVS_AC/sked_cat/rx.cat"),
                (os.path.join(path, "source.cat.geodetic.good"),
                 "https://ivscc.gsfc.nasa.gov/IVS_AC/sked_cat/source.cat.geodetic.good"),
                (os.path.join(path, "tracks.cat"), "https://ivscc.gsfc.nasa.gov/IVS_AC/sked_cat/tracks.cat")]

    # ThreadPool(13).imap_unordered(url_response, catalogs)

    for cat in catalogs:
        url_response(cat)


def url_response(cat):
    """
    download a single file from https and store

    primarily used to download the CATALOG files

    :param cat: (output_path, download_url)
    :return: None
    """
    path, url = cat

    # only download file if current file was last modified longer than 23 hours ago
    Message.addMessage("HTTPS download: {}... ".format(os.path.basename(path)), dump="download", endLine=False)
    if os.path.exists(path):
        last_update = os.path.getmtime(path)
        now = datetime.datetime.now()
        new_update = time.mktime(now.timetuple())
        diff = new_update - last_update
        if diff < 23 * 3600:
            Message.addMessage("up to date (last modified {:.2f} hours ago) -> no download".format(diff / 3600.0),
                               dump="download")
            return

    try:
        # download new file
        r = requests.get(url, stream=True)
        if r.ok:
            with open(path, 'wb') as f:
                for ch in r:
                    f.write(ch)
                Message.addMessage("successful", dump="download")
        else:
            Message.addMessage("ERROR", dump="download")

    except requests.exceptions.RequestException as err:
        Message.addMessage("#### ERROR {} ####".format(err), dump="download")
        Message.addMessage(traceback.format_exc(), dump="download")


def upload(path):
    """
    upload to IVS-BKG server using ftp

    :param path: path to session
    :return: None
    """
    flag = True
    path = os.path.join(path, "selected")
    code = os.path.basename(os.path.dirname(path))

    skdFile = glob.glob(os.path.join(path, "*.skd"))[0]
    txtFile = os.path.splitext(skdFile)[0] + ".txt"

    today = datetime.date.today()
    Message.addMessage("##### {} #####\n".format(code), dump="download")
    Message.addMessage("connecting to: ivs.bkg.bund.de\n", dump="download")

    pw = read_bkg_pw_from_file()
    if pw is not None:
        ftp = FTP("ivs.bkg.bund.de")

        ftp.login("ivsincoming", pw)  # *** INSERT PASSWORD HERE (replace pw) ***
        ftp.set_pasv(True)

        Message.addMessage("uploading files to BKG server", dump="download")

        Message.addMessage("\nserver content before upload:", dump="log")
        # get a list of all files at FTP server
        content = []
        ftp.retrlines('LIST', content.append)
        for l1 in content:
            Message.addMessage(l1, dump="log")

        Message.addMessage("\nuploading:", dump="download")
        for file in [skdFile, txtFile]:
            Message.addMessage("    {}... ".format(file), endLine=False, dump="download")
            with open(file, 'rb') as f:
                msg = ftp.storbinary('STOR {}'.format(os.path.basename(file)), f)
            Message.addMessage(msg, dump="download")

        # get a list of all files at FTP server
        Message.addMessage("\nserver content after upload:", dump="log")
        content = []
        ftp.retrlines('LIST', content.append)
        for l2 in content:
            Message.addMessage(l2, dump="log")
    else:
        Message.addMessage("No password for IVS BKG server was provided. Please store password in a \"BKG_pw.txt\" "
                           "file or insert password in source code (See file \"Transfer.py\" line with comment "
                           "\"*** INSERT PASSWORD HERE (replace pw) ***\"", dump="log")


def read_bkg_pw_from_file():
    if os.path.exists("BKG_pw.txt"):
        with open('BKG_pw.txt') as f:
            return f.read().strip()
    else:
        return None
