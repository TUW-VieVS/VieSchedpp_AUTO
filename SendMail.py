import datetime
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from Helper import Message


def changeSendMailsFlag(flag):
    """
    change sendMail flag

    :param flag: boolean flag
    :return: None
    """
    SendMail.flag_sendMail = flag


def delegate_send(slot):
    """
    change delegate send() function to different function (e.g.: send via gmail-server or bkg-server)

    :param slot: name ("Gmail", "BKG")
    :return: None
    """
    if slot.lower() == "gmail":
        SendMail.send = send_gmail
        print("Send mails via [GMAIL]")
    elif slot.lower() == "bkg":
        SendMail.send = send_bkg
        print("Send mails via [BKG]")
    else:
        Message.addMessage(f"ERROR: SMTP server slot \"{slot:}\" not found")


def writeMail_upload(code, emails):
    """
    write email with upload message

    :param code: session code
    :param emails: list of email addresses
    :return:
    """
    body = Message.msg_header + "\n" + \
           Message.msg_program + "\n" + \
           Message.msg_session + "\n" + \
           Message.msg_download + "\n" + \
           Message.msg_log

    if SendMail.flag_sendMail:
        msg = MIMEMultipart()
        msg['From'] = "VieSched++ AUTO"
        msg['To'] = ", ".join(emails)
        today = datetime.date.today()
        msg['Subject'] = f"[upload] [VieSched++ AUTO] {code} ({today:%B %d, %Y})"
        msg.attach(MIMEText(body))
        SendMail.send(msg)


def missing_schedule(session, program, to):
    if SendMail.flag_sendMail:
        msg = MIMEMultipart()
        msg['From'] = "VieSched++ AUTO"
        try:
            msg['To'] = ", ".join(to)
        except:
            msg['To'] = to

        msg['Subject'] = f"[WARNING] [VieSched++ AUTO] {session['code']} schedule missing"
        body = f"missing schedule for session {session['code']}\n\n" \
               f"generate it using: \n" \
               f"$ python VieSchedpp_AUTO.py -nu -p {program} -d {session['date'].date()}\n\n" \
               f"after inspection, upload it manually or change date in `upload_scheduler.txt` file " \
               f"to {datetime.date.today()} and execute: \n" \
               f"$ python VieSchedpp_AUTO.py -ns"
        msg.attach(MIMEText(body))

        SendMail.send(msg)


def network_changed(session, program, skd_network, to):
    if SendMail.flag_sendMail:
        master_network = session["stations"]

        msg = MIMEMultipart()
        msg['From'] = "VieSched++ AUTO"
        try:
            msg['To'] = ", ".join(to)
        except:
            msg['To'] = to

        stations = set(skd_network) | set(master_network)

        msg['Subject'] = f"[WARNING] [VieSched++ AUTO] {session['code']} network changed"
        body = f"network of session {session['code']} changed according to schedule master file\n\n" \
               f"station  schedule master\n"

        for sta in stations:
            bool_skd = "False"
            if sta in skd_network:
                bool_skd = "True"

            bool_master = "False"
            if sta in master_network:
                bool_master = "True"

            body += f"{sta:<8s} {bool_skd:<8s} {bool_master:<8s}\n"

        body += f"\n" \
                f"regenerate schedule using: \n" \
                f"$ python VieSchedpp_AUTO.py -nu -p {program} -d {session['date'].date()}\n\n" \
                f"after inspection, upload it manually or change date in `upload_scheduler.txt` file " \
                f"to {datetime.date.today()} and execute: \n" \
                f"$ python VieSchedpp_AUTO.py -ns \n\n" \
                f"also consider to contact the participating stations to ensure that they pick the correct schedule"
        msg.attach(MIMEText(body))

        SendMail.send(msg)


def writeMail(path_str, emails, body=None, date=None):
    """
    write an email

    :param path_str: path to "selected" folder
    :param emails: list of email addresses
    :param body: email body text. If None text will be taken from Message object
    :return: None
    """
    path = Path(path_str)
    skdFile = list(path.glob("*.skd"))[0]
    operationNotesFile = skdFile.with_suffix('.txt')
    vexFile = skdFile.with_suffix('.vex')
    files = [skdFile, operationNotesFile, vexFile]
    source_stat = path / (skdFile.stem + "_sourceStatistics.txt")
    if source_stat.exists():
        files.append(source_stat)

    figures = path.glob("*.png")
    if body is None:
        body = Message.msg_header + "\n" + \
               Message.msg_program + "\n" + \
               Message.msg_session + "\n" + \
               Message.msg_download + "\n" + \
               Message.msg_log

        with open(path / "email.txt", "w") as f:
            f.write(body)

    if SendMail.flag_sendMail:
        msg = MIMEMultipart()
        msg['From'] = "VieSched++ AUTO"
        msg['To'] = ", ".join(emails)
        sessionCode = path.parent.name
        program = path.parents[1].name
        subject = f"[VieSched++ AUTO] [{program}] {sessionCode}"
        if date is not None:
            subject += f" ({date:%B %d, %Y})"
        msg['Subject'] = subject

        msg.attach(MIMEText(body))

        for f in [*files, *figures]:
            with open(f, "rb") as fil:
                part = MIMEApplication(fil.read(), Name=f.name)
            # After the file is closed
            part['Content-Disposition'] = f'attachment; filename="{f.name}"'
            msg.attach(part)

        SendMail.send(msg)


def writeErrorMail(to):
    """
    write an email in case an error raised

    :param to: list of email addresses
    :return: None
    """
    if SendMail.flag_sendMail:
        msg = MIMEMultipart()
        msg['From'] = "VieSched++ AUTO"
        try:
            msg['To'] = ", ".join(to)
        except:
            msg['To'] = to

        today = datetime.date.today()
        msg['Subject'] = f"[ERROR] [VieSched++ AUTO] {today:%B %d, %Y}"
        body = Message.msg_header + "\n" + \
               Message.msg_program + "\n" + \
               Message.msg_session + "\n" + \
               Message.msg_download + "\n" + \
               Message.msg_log
        msg.attach(MIMEText(body))

        SendMail.send(msg)


def send_gmail(message):
    """
    send an email message via default gmail server

    :param message: email message
    :return: None
    """
    message['From'] = "VieSched++ AUTO"
    if SendMail.flag_sendMail:
        print("Send email (Gmail) to: " + message['To'], end="... ")
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.ehlo()
        server.login("vieschedpp.auto@gmail.com", "vlbi2000")
        server.send_message(message)
        server.quit()
        print("finished!")


def send_bkg(message):
    """
    send an email message via bkg server (for Wettzell)

    :param message: email message
    :return: None
    """
    message['From'] = "vieschedpp.auto@wettzell.de"
    if SendMail.flag_sendMail:
        print("Send email (BKG) to: " + message['To'], end="... ")
        # server = smtplib.SMTP('localhost', 25)
        server = smtplib.SMTP('141.74.2.1', 25)
        server.ehlo()
        server.send_message(message)
        server.quit()
        print("finished!")


def undefined():
    print("ERROR: email is undefined!")


class SendMail:
    flag_sendMail = True
    send = undefined


if __name__ == "__main__":
    msg = MIMEMultipart()
    msg['To'] = "mschartner@ethz.ch"
    msg['Subject'] = "Test mail"
    msg.attach(MIMEText("This is a test email"))
    send_bkg(msg)
    pass
