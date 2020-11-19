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
        Message.addMessage("ERROR: SMTP server slot \"{:}\" not found".format(slot))


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
        msg['Subject'] = "[upload] [VieSched++ AUTO] {} ({:%B %d, %Y})".format(code, today)
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
        subject = "[VieSched++ AUTO] [{}] {}".format(program, sessionCode)
        if date is not None:
            subject += " ({:%B %d, %Y})".format(date)
        msg['Subject'] = subject

        msg.attach(MIMEText(body))

        for f in [*files, *figures]:
            with open(f, "rb") as fil:
                part = MIMEApplication(fil.read(), Name=f.name)
            # After the file is closed
            part['Content-Disposition'] = 'attachment; filename="%s"' % f.name
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
        msg['Subject'] = "[ERROR] [VieSched++ AUTO] {:%B %d, %Y}".format(today)
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
        server = smtplib.SMTP('localhost', 25)
        server.ehlo()
        server.send_message(message)
        server.quit()
        print("finished!")


def undefined():
    print("ERROR: email is undefined!")

class SendMail:
    flag_sendMail = True
    send = undefined
