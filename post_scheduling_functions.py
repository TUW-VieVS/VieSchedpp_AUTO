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


def VGOS_std_vex_template(**kwargs):
    session = kwargs["session"]
    path_selected = kwargs["path"]
    code = session["code"].lower()
    name_vex = code + ".vex"
    path_to_vex = (Path(path_selected) / name_vex).resolve()

    # generate backup of vex file
    backup_vex = Path(path_selected) / (code + ".vex.orig.VieSchedpp")
    Message.addMessage(f"    - generate backup of {path_to_vex} to {backup_vex}", dump="session")
    shutil.copy(path_to_vex, backup_vex)

    # copy .vex template
    path_to_vex.unlink()
    path_vex_template = Path("CATALOGS_VieSchedpp/std_VGOS_vex_template.txt")
    template = {}
    with open(path_vex_template) as f:
        values = []
        for l in f:
            l_strip = l.strip()
            if l_strip.startswith("$"):
                if values:
                    value = "".join(values)
                    template[key] = value
                key = l_strip.split()[0]
                values = [l]
            else:
                values.append(l)
        if values:
            value = "".join(values)
            template[key] = value

    def adjust_mode_line(l, tlcs):
        l_strip = l.strip()
        if l_strip.startswith("ref"):
            pre = l_strip.split(":")[0].strip()
            stas = [tmp.strip().upper() for tmp in re.split(r'[:;]', l_strip)[1:]]
            pre = f"        {pre:<37s}"
            post = ""
            out = False
            for tlc in tlcs:
                if tlc.upper() in stas:
                    out = True
                    post += ": " + tlc[0].upper() + tlc[1].lower() + " "
                else:
                    post += "     "
            if out:
                return pre + post + ";\n"
            else:
                return ""
        else:
            return l + "\n"

    with open(backup_vex, "r") as vex_in, open(path_to_vex, "w") as vex_out:
        read = True
        for l in vex_in:
            if read == False and l.startswith("$"):
                read = True
            if "$MODE" in l:
                mode = template["$MODE;"]
                mode_lines = mode.split("\n")[:-1]
                for mode_l in mode_lines:
                    mode_l = adjust_mode_line(mode_l, session["stations_tlc"])
                    vex_out.write(mode_l)
                read = False
            if "$BBC" in l:
                read = False
                vex_out.write(template["$BBC;"])
            if "$IF" in l:
                read = False
                vex_out.write(template["$IF;"])
            if "$FREQ" in l:
                read = False
                vex_out.write(template["$FREQ;"])
            if "$TRACKS" in l:
                read = False
                vex_out.write(template["$TRACKS;"])
            if read:
                l = re.sub(r'mode\s*=\s*type', 'mode = VGOS_std', l)
                vex_out.write(l)
        pass
    pass

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
