import configparser
import os
import re
import shutil
import subprocess
import traceback
from pathlib import Path

import pexpect

from Helper import read_sources, Message


def _vex_in_sked_format(**kwargs):
    Message.addMessage("\nconvert .vex file to \"sked\" format for external parsers", dump="session")
    path_selected = kwargs["path"]
    code = kwargs["session"]["code"].lower()
    name_skd = (code + ".skd")
    name_vex = (code + ".vex")
    path_to_skd = Path(path_selected) / name_skd

    # create backup of original .vex file
    path_to_vex = (Path(path_selected) / name_vex).absolute()
    backup_vex = Path(path_selected) / (code + ".vex.orig.VieSchedpp")
    Message.addMessage("    - generate backup of {} to {}".format(path_to_vex, backup_vex), dump="session")
    shutil.copy(str(path_to_vex), str(backup_vex))

    settings = configparser.ConfigParser()
    settings.read("settings.ini")

    path_sked = settings["general"].get("path_sked")
    sked_executable = settings["general"].get("sked_executable")
    if sked_executable is None:
        Message.addMessage("no path to sked executable define - defaulting to 'sked'", dump="session")
        sked_executable = "sked"

    if path_sked is None:
        Message.addMessage("[WARNING] failed to generate .vex file in \"sked\" format! Undefined path to sked folder",
                           dump="session")
        return

    Message.addMessage("    - copy {} to {}".format(path_to_skd, Path(path_sked) / name_skd), dump="session")
    shutil.copy(str(path_to_skd), str(Path(path_sked) / name_skd))

    cwd = Path.cwd()
    try:
        Message.addMessage("    - change dir to {}".format(path_sked), dump="session")
        os.chdir(path_sked)
        if Path(name_vex).is_file():
            Message.addMessage("    - delete existing .vex file {}".format(name_vex), dump="session")
            Path(name_vex).unlink(missing_ok=True)
        Message.addMessage("    - execute sked to parse .vex file".format(path_sked), dump="session")
        child = pexpect.spawn(sked_executable + " " + name_skd)
        child.expect(r'\?')
        child.sendline("vwc " + name_vex)
        child.expect(r'\?')
        child.sendline("q")
        child.close()

        newVex = Path(path_sked) / name_vex
        Message.addMessage("    - copy new .vex file from {} to {}".format(newVex, path_to_vex), dump="session")
        shutil.copy(str(newVex), str(path_to_vex))
    except:
        Message.addMessage("[ERROR] failed to generate .vex file in \"sked\" format", dump="session")
        Message.addMessage(traceback.format_exc(), dump="session")

    finally:
        Message.addMessage("    - change dir to {}".format(cwd), dump="session")
        os.chdir(str(cwd))

    with open(path_to_vex) as f:
        all = f.readlines()
        all[1] = "*  schedule generated by VieSched++, converted with sked\n"

    with open(path_to_vex, 'w') as f:
        f.writelines(all)

    pass


def _vlba_vex_adjustments(**kwargs):
    Message.addMessage("adjust .vex file for VLBA needs", dump="session")
    path_selected = kwargs["path"]
    code = kwargs["session"]["code"].lower()
    name_vex = (code + ".vex")

    path_to_vex = (Path(path_selected) / name_vex).absolute()

    settings = configparser.ConfigParser()
    settings.read("settings.ini")

    path_script = settings["general"].get("path_vex_correction_script")

    if path_script is None:
        Message.addMessage("[ERROR] failed to execute \"vlba_vex_correct\" script - script not found", dump="session")
        return

    cwd = Path.cwd()

    try:
        Message.addMessage("    - change dir to {}".format(Path(path_script).parent), dump="session")
        os.chdir(Path(path_script).parent)

        Message.addMessage("    - execute {} {}".format(path_script, path_to_vex), dump="session")
        p = subprocess.run([path_script, path_to_vex], capture_output=True, text=True)
        log = p.stdout
        if log:
            Message.addMessage(log, dump="log")
        errlog = p.stderr
        if errlog:
            Message.addMessage(errlog, dump="log")
        p.check_returncode()
    except:
        Message.addMessage("[ERROR] failed to execute \"vlba_vex_correct\" script - returns error", dump="session")
        Message.addMessage(traceback.format_exc(), dump="session")
    finally:
        Message.addMessage("    - change dir to {}".format(cwd), dump="session")
        os.chdir(str(cwd))


def VGOS_procs_block(**kwargs):
    path = kwargs["path"]
    session = kwargs["session"]
    stations = session["stations"]
    program_code = kwargs["program_code"]

    procs_cat = Path("Templates") / program_code / "procs.cat"
    if not procs_cat.exists():
        Message.addMessage("[WARNING] procs.cat file not found!", dump="session")
        return

    skd_file = next(Path(path).glob("*.skd"))

    re_begin = re.compile(r"BEGIN\s+(\w+)")
    re_end = re.compile(r"END\s+(\w+)")
    with open(skd_file, 'a') as f_skd:
        f_skd.write("$PROCS\n")

        with open(procs_cat) as f_procs:
            flag_write = False
            for l in f_procs:
                re_begin_search = re_begin.search(l)
                if re_begin_search:
                    station = re_begin_search.group(1)
                    if station == "COMMON" or station in stations:
                        flag_write = True

                if re_end.search(l):
                    f_skd.write(l)
                    flag_write = False

                if flag_write:
                    f_skd.write(l)


def VGOS_Broadband_block_512_8192_4096(**kwargs):
    path = kwargs["path"]
    session = kwargs["session"]
    stations = session["stations"]

    broadband_string = "$BROADBAND\n"
    for sta in stations:
        broadband_string += "{:8s}   512.00    8192       4096\n".format(sta)

    skd_file = next(Path(path).glob("*.skd"))
    with open(skd_file, 'r') as f:
        skd_content = f.read()

    skd_content = skd_content.replace("$BROADBAND\n", broadband_string)

    with open(skd_file, 'w') as f:
        f.write(skd_content)


def VGOS_fake_256mbps_mode(**kwargs):
    path = kwargs["path"]
    session = kwargs["session"]
    program_code = kwargs["program_code"]
    path_codes = Path("Templates") / program_code / "dummy_CODES.txt"
    with open(path_codes, 'r') as f:
        codes = f.read()

    skd_file = next(Path(path).glob("*.skd"))
    with open(skd_file, 'r') as f:
        skd_content = f.read()

    skd_content = skd_content.replace("* no sked observind mode used! \n", codes)
    skd_content = re.sub(r'A\s+\d+\.?\d?\s+B\s+\d+\.?\d?\s+C\s+\d+\.?\d?\s+D\s+\d+\.?\d?', "X 2500.0 S 2500.0",
                         skd_content)
    skd_content = skd_content + "$PROCS\n$DUMMY\n"

    with open(skd_file, 'w') as f:
        f.write(skd_content)


def update_source_list(**kwargs):
    path = kwargs["path"]
    ds = kwargs["ds"]
    session = kwargs["session"]
    session_code = session["code"]
    program_code = kwargs["program_code"]

    target_source_list = Path("Templates") / program_code / "source.cat.target"
    calib_source_list = Path("Templates") / program_code / "source.cat.calib"

    targets, target_list, target_comment = read_sources(target_source_list)
    calibs, calib_list, calib_comment = read_sources(calib_source_list)

    target_comment = ["" if c.strip() == session_code else c.strip() for c in target_comment]
    calib_comment = ["" if c.strip() == session_code else c.strip() for c in calib_comment]

    _update_source_list_comment(ds, session_code, targets, target_comment)
    _update_source_list_comment(ds, session_code, calibs, calib_comment)

    _write_source_list(target_source_list, target_list, target_comment)
    _write_source_list(calib_source_list, calib_list, calib_comment)


def _update_source_list_comment(ds, session_code, name, comment):
    for idx, (n, c) in enumerate(zip(name, comment)):
        column_name = "n_src_scans_" + n
        if column_name in ds:
            val = ds[column_name]
            if val > 4:
                comment[idx] = session_code


def _write_source_list(path, list, comment):
    with open(path, 'w') as f:
        for l, c in zip(list, comment):
            c = c.strip()
            if c:
                f.write(l + "* " + c + "\n")
            else:
                f.write(l + "\n")
