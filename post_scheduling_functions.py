import configparser
import datetime
import os
import re
import shutil
import subprocess
import traceback
from pathlib import Path

import pexpect

from Helper import read_sources, Message


def vex_simple_mode_to_std_VGOS(**kwargs):
    session = kwargs["session"]
    path_selected = kwargs["path"]
    code = kwargs["session"]["code"].lower()
    name_vex = code + ".vex"
    path_to_vex = (Path(path_selected) / name_vex).resolve()

    # generate backup of vex file
    backup_vex = Path(path_selected) / (code + ".vex.orig.VieSchedpp")
    Message.addMessage(f"    - generate backup of {path_to_vex} to {backup_vex}", dump="session")
    shutil.copy(path_to_vex, backup_vex)

    vex_new = []
    flag_mode = False
    with open(path_to_vex, "r") as f:
        for l in f:
            if flag_mode and l.startswith("$"):
                flag_mode = False
            if not flag_mode:
                l = l.replace("mode = type", "mode = VGOS")
                vex_new.append(l)
            if l.startswith("$MODE"):
                flag_mode = True
                vex_new.append(
                    "*=========================================================================================================\n")
                vex_new.append("    def VGOS;\n")
                tlcs = " : ".join([f"{sta[0]}{sta[1].lower()}" for sta in session["stations_tlc"]])
                vex_new.append(f"        ref $FREQ   = VGOS_std : {tlcs} ;\n")
                vex_new.append(f"        ref $BBC    = VGOS_std : {tlcs} ;\n")
                vex_new.append(f"        ref $IF     = VGOS_std : {tlcs} ;\n")
                vex_new.append(f"        ref $TRACKS = VDIF     : {tlcs} ;\n")
                vex_new.append("    enddef;\n")
                vex_new.append(
                    "*=========================================================================================================\n")
    vex_new = "".join(vex_new)

    bbc_vgos_std = """$BBC;
  def VGOS_std;
    BBC_assign = &BBC01 : 01 : &IF_1N;
    BBC_assign = &BBC02 : 02 : &IF_1N;
    BBC_assign = &BBC03 : 03 : &IF_1N;
    BBC_assign = &BBC04 : 04 : &IF_1N;
    BBC_assign = &BBC05 : 05 : &IF_1N;
    BBC_assign = &BBC06 : 06 : &IF_1N;
    BBC_assign = &BBC07 : 07 : &IF_1N;
    BBC_assign = &BBC08 : 08 : &IF_1N;
    BBC_assign = &BBC09 : 09 : &IF_3N;
    BBC_assign = &BBC10 : 10 : &IF_3N;
    BBC_assign = &BBC11 : 11 : &IF_3N;
    BBC_assign = &BBC12 : 12 : &IF_3N;
    BBC_assign = &BBC13 : 13 : &IF_3N;
    BBC_assign = &BBC14 : 14 : &IF_3N;
    BBC_assign = &BBC15 : 15 : &IF_3N;
    BBC_assign = &BBC16 : 16 : &IF_3N;
    BBC_assign = &BBC17 : 01 : &IF_1N;
    BBC_assign = &BBC18 : 02 : &IF_1N;
    BBC_assign = &BBC19 : 03 : &IF_1N;
    BBC_assign = &BBC20 : 04 : &IF_1N;
    BBC_assign = &BBC21 : 05 : &IF_1N;
    BBC_assign = &BBC22 : 06 : &IF_1N;
    BBC_assign = &BBC23 : 07 : &IF_1N;
    BBC_assign = &BBC24 : 08 : &IF_1N;
    BBC_assign = &BBC25 : 09 : &IF_3N;
    BBC_assign = &BBC26 : 10 : &IF_3N;
    BBC_assign = &BBC27 : 11 : &IF_3N;
    BBC_assign = &BBC28 : 12 : &IF_3N;
    BBC_assign = &BBC29 : 13 : &IF_3N;
    BBC_assign = &BBC30 : 14 : &IF_3N;
    BBC_assign = &BBC31 : 15 : &IF_3N;
    BBC_assign = &BBC32 : 16 : &IF_3N;
    BBC_assign = &BBC33 : 01 : &IF_1N;
    BBC_assign = &BBC34 : 02 : &IF_1N;
    BBC_assign = &BBC35 : 03 : &IF_1N;
    BBC_assign = &BBC36 : 04 : &IF_1N;
    BBC_assign = &BBC37 : 05 : &IF_1N;
    BBC_assign = &BBC38 : 06 : &IF_1N;
    BBC_assign = &BBC39 : 07 : &IF_1N;
    BBC_assign = &BBC40 : 08 : &IF_1N;
    BBC_assign = &BBC41 : 09 : &IF_3N;
    BBC_assign = &BBC42 : 10 : &IF_3N;
    BBC_assign = &BBC43 : 11 : &IF_3N;
    BBC_assign = &BBC44 : 12 : &IF_3N;
    BBC_assign = &BBC45 : 13 : &IF_3N;
    BBC_assign = &BBC46 : 14 : &IF_3N;
    BBC_assign = &BBC47 : 15 : &IF_3N;
    BBC_assign = &BBC48 : 16 : &IF_3N;
    BBC_assign = &BBC49 : 01 : &IF_1N;
    BBC_assign = &BBC50 : 02 : &IF_1N;
    BBC_assign = &BBC51 : 03 : &IF_1N;
    BBC_assign = &BBC52 : 04 : &IF_1N;
    BBC_assign = &BBC53 : 05 : &IF_1N;
    BBC_assign = &BBC54 : 06 : &IF_1N;
    BBC_assign = &BBC55 : 07 : &IF_1N;
    BBC_assign = &BBC56 : 08 : &IF_1N;
    BBC_assign = &BBC57 : 09 : &IF_3N;
    BBC_assign = &BBC58 : 10 : &IF_3N;
    BBC_assign = &BBC59 : 11 : &IF_3N;
    BBC_assign = &BBC60 : 12 : &IF_3N;
    BBC_assign = &BBC61 : 13 : &IF_3N;
    BBC_assign = &BBC62 : 14 : &IF_3N;
    BBC_assign = &BBC63 : 15 : &IF_3N;
    BBC_assign = &BBC64 : 16 : &IF_3N;
  enddef;"""

    if_vgos_std = """$IF;
  def VGOS_std;
    if_def = &IF_1N : 3N : X : 8080.0 MHz : U : 5 MHz : 0 Hz;
    if_def = &IF_3N : 3N : Y : 8080.0 MHz : U : 5 MHz : 0 Hz;
  enddef;"""

    tracks_vgos_std = """$TRACKS;
  def VDIF;
    track_frame_format = VDIF/8032/2;
  enddef;"""

    freq_vgos_std = """$FREQ;
  def VGOS_std;
    chan_def = &X : 3480.40 MHz : L : 32.000 MHz : &Ch01 : &BBC01 : &L_cal;
    chan_def = &X : 3448.40 MHz : L : 32.000 MHz : &Ch02 : &BBC02 : &L_cal;
    chan_def = &X : 3384.40 MHz : L : 32.000 MHz : &Ch03 : &BBC03 : &L_cal;
    chan_def = &X : 3320.40 MHz : L : 32.000 MHz : &Ch04 : &BBC04 : &L_cal;
    chan_def = &X : 3224.40 MHz : L : 32.000 MHz : &Ch05 : &BBC05 : &L_cal;
    chan_def = &X : 3096.40 MHz : L : 32.000 MHz : &Ch06 : &BBC06 : &L_cal;
    chan_def = &X : 3064.40 MHz : L : 32.000 MHz : &Ch07 : &BBC07 : &L_cal;
    chan_def = &X : 3032.40 MHz : L : 32.000 MHz : &Ch08 : &BBC08 : &L_cal;
    chan_def = &X : 3480.40 MHz : L : 32.000 MHz : &Ch09 : &BBC09 : &L_cal;
    chan_def = &X : 3448.40 MHz : L : 32.000 MHz : &Ch10 : &BBC10 : &L_cal;
    chan_def = &X : 3384.40 MHz : L : 32.000 MHz : &Ch11 : &BBC11 : &L_cal;
    chan_def = &X : 3320.40 MHz : L : 32.000 MHz : &Ch12 : &BBC12 : &L_cal;
    chan_def = &X : 3224.40 MHz : L : 32.000 MHz : &Ch13 : &BBC13 : &L_cal;
    chan_def = &X : 3096.40 MHz : L : 32.000 MHz : &Ch14 : &BBC14 : &L_cal;
    chan_def = &X : 3064.40 MHz : L : 32.000 MHz : &Ch15 : &BBC15 : &L_cal;
    chan_def = &X : 3032.40 MHz : L : 32.000 MHz : &Ch16 : &BBC16 : &L_cal;
    chan_def = &X : 5720.40 MHz : L : 32.000 MHz : &Ch17 : &BBC17 : &L_cal;
    chan_def = &X : 5688.40 MHz : L : 32.000 MHz : &Ch18 : &BBC18 : &L_cal;
    chan_def = &X : 5624.40 MHz : L : 32.000 MHz : &Ch19 : &BBC19 : &L_cal;
    chan_def = &X : 5560.40 MHz : L : 32.000 MHz : &Ch20 : &BBC20 : &L_cal;
    chan_def = &X : 5464.40 MHz : L : 32.000 MHz : &Ch21 : &BBC21 : &L_cal;
    chan_def = &X : 5336.40 MHz : L : 32.000 MHz : &Ch22 : &BBC22 : &L_cal;
    chan_def = &X : 5304.40 MHz : L : 32.000 MHz : &Ch23 : &BBC23 : &L_cal;
    chan_def = &X : 5272.40 MHz : L : 32.000 MHz : &Ch24 : &BBC24 : &L_cal;
    chan_def = &X : 5720.40 MHz : L : 32.000 MHz : &Ch25 : &BBC25 : &L_cal;
    chan_def = &X : 5688.40 MHz : L : 32.000 MHz : &Ch26 : &BBC26 : &L_cal;
    chan_def = &X : 5624.40 MHz : L : 32.000 MHz : &Ch27 : &BBC27 : &L_cal;
    chan_def = &X : 5560.40 MHz : L : 32.000 MHz : &Ch28 : &BBC28 : &L_cal;
    chan_def = &X : 5464.40 MHz : L : 32.000 MHz : &Ch29 : &BBC29 : &L_cal;
    chan_def = &X : 5336.40 MHz : L : 32.000 MHz : &Ch30 : &BBC30 : &L_cal;
    chan_def = &X : 5304.40 MHz : L : 32.000 MHz : &Ch31 : &BBC31 : &L_cal;
    chan_def = &X : 5272.40 MHz : L : 32.000 MHz : &Ch32 : &BBC32 : &L_cal;
    chan_def = &X : 6840.40 MHz : L : 32.000 MHz : &Ch33 : &BBC33 : &L_cal;
    chan_def = &X : 6808.40 MHz : L : 32.000 MHz : &Ch34 : &BBC34 : &L_cal;
    chan_def = &X : 6744.40 MHz : L : 32.000 MHz : &Ch35 : &BBC35 : &L_cal;
    chan_def = &X : 6680.40 MHz : L : 32.000 MHz : &Ch36 : &BBC36 : &L_cal;
    chan_def = &X : 6584.40 MHz : L : 32.000 MHz : &Ch37 : &BBC37 : &L_cal;
    chan_def = &X : 6456.40 MHz : L : 32.000 MHz : &Ch38 : &BBC38 : &L_cal;
    chan_def = &X : 6424.40 MHz : L : 32.000 MHz : &Ch39 : &BBC39 : &L_cal;
    chan_def = &X : 6392.40 MHz : L : 32.000 MHz : &Ch40 : &BBC40 : &L_cal;
    chan_def = &X : 6840.40 MHz : L : 32.000 MHz : &Ch41 : &BBC41 : &L_cal;
    chan_def = &X : 6808.40 MHz : L : 32.000 MHz : &Ch42 : &BBC42 : &L_cal;
    chan_def = &X : 6744.40 MHz : L : 32.000 MHz : &Ch43 : &BBC43 : &L_cal;
    chan_def = &X : 6680.40 MHz : L : 32.000 MHz : &Ch44 : &BBC44 : &L_cal;
    chan_def = &X : 6584.40 MHz : L : 32.000 MHz : &Ch45 : &BBC45 : &L_cal;
    chan_def = &X : 6456.40 MHz : L : 32.000 MHz : &Ch46 : &BBC46 : &L_cal;
    chan_def = &X : 6424.40 MHz : L : 32.000 MHz : &Ch47 : &BBC47 : &L_cal;
    chan_def = &X : 6392.40 MHz : L : 32.000 MHz : &Ch48 : &BBC48 : &L_cal;
    chan_def = &X : 10680.40 MHz : L : 32.000 MHz : &Ch49 : &BBC49 : &L_cal;
    chan_def = &X : 10648.40 MHz : L : 32.000 MHz : &Ch50 : &BBC50 : &L_cal;
    chan_def = &X : 10584.40 MHz : L : 32.000 MHz : &Ch51 : &BBC51 : &L_cal;
    chan_def = &X : 10520.40 MHz : L : 32.000 MHz : &Ch52 : &BBC52 : &L_cal;
    chan_def = &X : 10424.40 MHz : L : 32.000 MHz : &Ch53 : &BBC53 : &L_cal;
    chan_def = &X : 10296.40 MHz : L : 32.000 MHz : &Ch54 : &BBC54 : &L_cal;
    chan_def = &X : 10264.40 MHz : L : 32.000 MHz : &Ch55 : &BBC55 : &L_cal;
    chan_def = &X : 10232.40 MHz : L : 32.000 MHz : &Ch56 : &BBC56 : &L_cal;
    chan_def = &X : 10680.40 MHz : L : 32.000 MHz : &Ch57 : &BBC57 : &L_cal;
    chan_def = &X : 10648.40 MHz : L : 32.000 MHz : &Ch58 : &BBC58 : &L_cal;
    chan_def = &X : 10584.40 MHz : L : 32.000 MHz : &Ch59 : &BBC59 : &L_cal;
    chan_def = &X : 10520.40 MHz : L : 32.000 MHz : &Ch60 : &BBC60 : &L_cal;
    chan_def = &X : 10424.40 MHz : L : 32.000 MHz : &Ch61 : &BBC61 : &L_cal;
    chan_def = &X : 10296.40 MHz : L : 32.000 MHz : &Ch62 : &BBC62 : &L_cal;
    chan_def = &X : 10264.40 MHz : L : 32.000 MHz : &Ch63 : &BBC63 : &L_cal;
    chan_def = &X : 10232.40 MHz : L : 32.000 MHz : &Ch64 : &BBC64 : &L_cal;
    sample_rate = 64.0 Ms/sec;
  enddef;"""
    vex_new = vex_new.replace("$BBC;", bbc_vgos_std)
    vex_new = vex_new.replace("$IF;", if_vgos_std)
    vex_new = vex_new.replace("$TRACKS;", tracks_vgos_std)
    vex_new = vex_new.replace("$FREQ;", freq_vgos_std)

    with open(path_to_vex, "w") as f:
        f.write(vex_new)


def fill_vex_template(**kwargs):
    session = kwargs["session"]
    path_selected = kwargs["path"]
    version = kwargs["version"]
    code = kwargs["session"]["code"].lower()
    name_vex = code + ".vex"
    path_to_vex = (Path(path_selected) / name_vex).resolve()

    # generate backup of vex file
    backup_vex = Path(path_selected) / (code + ".vex.orig.VieSchedpp")
    Message.addMessage(f"    - generate backup of {path_to_vex} to {backup_vex}", dump="session")
    shutil.copy(path_to_vex, backup_vex)

    # copy .vex template
    path_to_vex.unlink()
    program_code = kwargs["program_code"]
    path_vex_template = Path("Templates") / program_code / "vex.tmpl"
    shutil.copy(path_vex_template, path_to_vex)

    with open(path_to_vex, "r") as f:
        vex_new = f.read()
    vex_new = vex_new.replace("__@EXP_CODE@__", session["code"])
    vex_new = vex_new.replace("__@NOMINAL_START@__", f"{session['date']}")
    vex_new = vex_new.replace("__@DURATION@__", f"{session['duration']:.1f}")
    vex_new = vex_new.replace("__@EXP_DESCR@__", f"{session['name']}")
    vex_new = vex_new.replace("__@DATE_START@__", f"{session['date']:%Yy%jd%Hh%Mm%Ss}")
    vex_new = vex_new.replace("__@SCHEDULE_REVISION@__", f"{version}")
    vex_new = vex_new.replace("__@DATE_STOP@__",
                              f"{session['date'] + datetime.timedelta(hours=session['duration']):%Yy%jd%Hh%Mm%Ss}")
    vex_new = vex_new.replace("__@SCHEDULER_NAME@__", "Matthias Schartner")
    vex_new = vex_new.replace("__@SCHEDULER_EMAIL@__", "mschartner@ethz.ch")
    vex_new = vex_new.replace("__@HDS@__", "v01")

    additional_blocks = ["$SCHED", "$SOURCE"]
    additional_text = []
    append = False
    with open(backup_vex, "r") as f:
        for l in f:
            if any([l.startswith(s) for s in additional_blocks]):
                append = True
            elif l.startswith("$"):
                append = False

            if append:
                l = l.replace("mode = type", "mode = v01")
                additional_text.append(l)

    vex_new = "".join([vex_new, *additional_text])

    with open(path_to_vex, "w") as f:
        f.write(vex_new)

    pass


def fill_skd_template(**kwargs):
    path_selected = kwargs["path"]
    code = kwargs["session"]["code"].lower()
    name_skd = code + ".skd"
    path_to_skd = (Path(path_selected) / name_skd).resolve()

    # generate backup of skd file
    backup_skd = Path(path_selected) / (code + ".skd.orig.VieSchedpp")
    Message.addMessage(f"    - generate backup of {path_to_skd} to {backup_skd}", dump="session")
    shutil.copy(path_to_skd, backup_skd)

    # copy .skd template
    path_to_skd.unlink()
    program_code = kwargs["program_code"]
    path_skd_template = Path("Templates") / program_code / "skd.tmpl"
    shutil.copy(path_skd_template, path_to_skd)

    with open(path_to_skd, "r") as f:
        skd_new = f.read()

    additional_blocks = ["$CATALOGS_USED", "$SOURCES", "$SKED", "$FLUX"]
    additional_text = {}
    append = False
    with open(backup_skd, "r") as f:
        for l in f:
            if any([l.startswith(s) for s in additional_blocks]):
                if append == True:
                    skd_new = skd_new.replace(key, "".join(txt))
                key = l
                txt = []
                append = True
            elif l.startswith("$") and append == True:
                append = False
                skd_new = skd_new.replace(key, "".join(txt))

            if append:
                txt.append(l)

    new_lines = skd_new.split("\n")
    with open(backup_skd, "r") as f:
        old_lines = f.read()
    old_lines = old_lines.split("\n")
    new_lines[:15] = old_lines[:15]

    skd_new = "\n".join(new_lines)

    with open(path_to_skd, "w") as f:
        f.write(skd_new)

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
    Message.addMessage(f"    - generate backup of {path_to_vex} to {backup_vex}", dump="session")
    shutil.copy(path_to_vex, backup_vex)

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

    Message.addMessage(f"    - copy {path_to_skd} to {Path(path_sked) / name_skd}", dump="session")
    shutil.copy(path_to_skd, Path(path_sked) / name_skd)

    cwd = Path.cwd()
    try:
        Message.addMessage(f"    - change dir to {path_sked}", dump="session")
        os.chdir(path_sked)
        if Path(name_vex).is_file():
            Message.addMessage(f"    - delete existing .vex file {name_vex}", dump="session")
            Path(name_vex).unlink()
        Message.addMessage(f"    - execute sked to parse .vex file {path_sked}", dump="session")
        child = pexpect.spawn(sked_executable + " " + name_skd)
        child.expect(r'\?')
        child.sendline("vwc " + name_vex)
        child.expect(r'\?')
        child.sendline("q")
        child.close()

        newVex = Path(path_sked) / name_vex
        Message.addMessage(f"    - copy new .vex file from {newVex} to {path_to_vex}", dump="session")
        shutil.copy(newVex, path_to_vex)
    except:
        Message.addMessage("[ERROR] failed to generate .vex file in \"sked\" format", dump="session")
        Message.addMessage(traceback.format_exc(), dump="session")

    finally:
        Message.addMessage(f"    - change dir to {cwd}", dump="session")
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
    p_path_script = Path(path_script)
    stations = kwargs["session"]["stations"]

    try:
        Message.addMessage(f"    - change dir to {p_path_script.parent}", dump="session")
        os.chdir(p_path_script.parent)
        if "ISHIOKA" in stations:
            p_path_script = p_path_script.parent / "vlba_vex_correct_modified_for_IS"
            path_script = str(p_path_script)

        if not p_path_script.is_file():
            Message.addMessage(
                f"[ERROR] failed to execute \"vlba_vex_correct\" script with IS - script not found {p_path_script}",
                dump="session")
            return

        Message.addMessage(f"    - execute {path_script} {path_to_vex}", dump="session")
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
        Message.addMessage(f"    - change dir to {cwd}", dump="session")
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
        broadband_string += f"{sta:8s}   512.00    8192       4096\n"

    skd_file = next(Path(path).glob("*.skd"))
    with open(skd_file, 'r') as f:
        skd_content = f.read()

    skd_content = skd_content.replace("$BROADBAND\n", broadband_string)

    with open(skd_file, 'w') as f:
        f.write(skd_content)


def VGOS_Broadband_block_512_8192_8192(**kwargs):
    path = kwargs["path"]
    session = kwargs["session"]
    stations = session["stations"]

    broadband_string = "$BROADBAND\n"
    for sta in stations:
        broadband_string += f"{sta:8s}   512.00    8192       4096\n"

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

    skd_content = skd_content.replace("* no sked observing mode used! \n", codes)
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
