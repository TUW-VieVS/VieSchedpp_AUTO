from ftplib import FTP_TLS
from pathlib import Path
import argparse
from Transfer import read_pw_from_file


def upload(folder, force):
    skdFile = list(folder.glob("*.skd"))
    txtFile = list(folder.glob("*.txt"))
    vexFile = list(folder.glob("*.vex"))

    print(f"skd files: {len(skdFile)}, txt files: {len(txtFile)}, vex files: {len(vexFile)}")
    print(f"    {[n.name for n in skdFile]}")
    print(f"    {[n.name for n in txtFile]}")
    print(f"    {[n.name for n in vexFile]}")

    i = 0
    while i < 2:
        if not force:
            answer = input("Should these files be uploaded? (yes or no)")
        if force or any(answer.lower() == f for f in ["yes", 'y', '1', 'ye']):
            _upload(skdFile, txtFile, vexFile)
            break
        elif any(answer.lower() == f for f in ['no', 'n', '0']):
            print("No")
            break
        else:
            i += 1
            if i < 2:
                print('Please enter yes or no')
            else:
                print("Nothing done")


def _upload(skdFile, txtFile, vexFile):
    user, pw = read_pw_from_file(Path("BKG_pw.txt"))
    if pw is not None:
        ftp = FTP_TLS("ivs.bkg.bund.de", user=user, passwd=pw)
        ftp.prot_p()

        ftp.login(user, pw)  # *** INSERT USER AND PASSWORD HERE (replace user, pw) ***
        ftp.set_pasv(True)

        print("uploading files to BKG server")

        print("uploading:")
        for file in [*skdFile, *txtFile, *vexFile]:
            print(f"    {file}... ", end="")
            with open(file, 'rb') as f:
                msg = ftp.storbinary(f'STOR {file.name}', f)
            print(msg)

        # get a list of all files at FTP server
    else:
        print("No password for IVS BKG server was provided. Please store username and password in a "
              "\"BKG_pw.txt\" file  (seperated by a whitespace) or insert password in source code "
              "(See file \"Transfer.py\" line with comment "
              "\"*** INSERT PASSWORD HERE (replace pw) ***\"", dump="log")


if __name__ == "__main__":
    doc = "upload all files in this folder."

    parser = argparse.ArgumentParser(description=doc)
    parser.add_argument("--folder", help="folder including all files to be uploaded", required=True)
    parser.add_argument("--force", help="force upload", default=False, type=bool)

    args = parser.parse_args()

    upload(Path(args.folder), args.force)
