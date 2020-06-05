import datetime
import glob
import os
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from Helper import Message


class SendMail:
    _flag_sendMail = True

    def __init__(self):
        """
        initialize flags
        """
        pass

    @classmethod
    def changeSendMailsFlag(cls, flag):
        """
        change sendMail flag

        :param flag: boolean flag
        :return: None
        """
        cls._flag_sendMail = flag

    @classmethod
    def writeMail_upload(self, code, emails):
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

        if SendMail._flag_sendMail:
            msg = MIMEMultipart()
            msg['From'] = "VieSched++ AUTO"
            msg['To'] = ", ".join(emails)
            today = datetime.date.today()
            msg['Subject'] = "[upload] [VieSched++ AUTO] {} ({:%B %d, %Y})".format(code, today)
            msg.attach(MIMEText(body))
            self.send(msg)

    @classmethod
    def writeMail(self, path, emails, body=None):
        """
        write an email

        :param path: path to "selected" folder
        :param emails: list of email addresses
        :param body: email body text. If None text will be taken from Message object
        :return: None
        """
        skdFile = glob.glob(os.path.join(path, "*.skd"))[0]
        operationNotesFile = skdFile.replace(".skd", ".txt")

        figures = glob.glob(os.path.join(path, "*.png"))
        if body is None:
            body = Message.msg_header + "\n" + \
                   Message.msg_program + "\n" + \
                   Message.msg_session + "\n" + \
                   Message.msg_download + "\n" + \
                   Message.msg_log

            with open(os.path.join(path, "email.txt"), "w") as f:
                f.write(body)

        if SendMail._flag_sendMail:
            msg = MIMEMultipart()
            msg['From'] = "VieSched++ AUTO"
            msg['To'] = ", ".join(emails)
            sessionCode = os.path.basename(os.path.dirname(path))
            msg['Subject'] = "[VieSched++ AUTO] {}".format(sessionCode)

            msg.attach(MIMEText(body))

            for f in [skdFile, operationNotesFile, *figures]:
                with open(f, "rb") as fil:
                    part = MIMEApplication(fil.read(), Name=os.path.basename(f))
                # After the file is closed
                part['Content-Disposition'] = 'attachment; filename="%s"' % os.path.basename(f)
                msg.attach(part)

            self.send(msg)

    @classmethod
    def writeErrorMail(self, to):
        """
        write an email in case an error raised

        :param to: list of email addresses
        :return: None
        """
        if SendMail._flag_sendMail:
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

            self.send(msg)

    @classmethod
    def send(self, message):
        """
        send an email message

        :param message: email message
        :return: None
        """
        if SendMail._flag_sendMail:
            server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
            server.ehlo()
            server.login("vieschedpp.auto@gmail.com", "vlbi2000")
            server.send_message(message)
