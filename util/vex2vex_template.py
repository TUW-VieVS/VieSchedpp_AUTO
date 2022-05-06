import argparse
import re
import shutil


def vex2vex_template(path_source, path_template):
    """
    This function can be used to copy some blocks of a .vex schedule to a .vex template. This is useful if you have a
    working .vex file (the template - e.g. an old successful session) and want to add the new schedule into this
    template. In particular, it will exchange parts of the $EXPER and $PARA block, as well as the full $SOURCES,
    $FLUX and $SKED blocks. The original schedule file will be overwritten by this function, but a backup is generated
    in the same folder named "{path_source}.vex.orig"

    Parameters
    ----------
    path_source path to input schedule
    path_template path to schedule template

    Returns
    -------
    None
    """

    # some regex to find the blocks
    # things to consider: This can be the last block (no more $).
    # Additionally, there can be trailing whitespaces before the $ sign.
    # Therefore, use "^\s*\$|\Z" as the end
    sked = re.compile(f'\$SCHED[\S\s]*?(?=^\s*\$|\Z)', re.MULTILINE)
    source = re.compile(f'\$SOURCE[\S\s]*?(?=^\s*\$|\Z)', re.MULTILINE)

    # read template
    with open(path_template) as f:
        template = f.read()

    # make a backup of the original schedule
    shutil.copy(path_source, path_source + ".orig")

    # read the schedule
    with open(path_source) as f:
        vex = f.read()
    vex_sked = sked.search(vex).group()
    vex_source = source.search(vex).group()

    # exchange $SOURCES and $SKED block of template with the blocks from the schedule
    template = re.sub(sked, vex_sked, template)
    template = re.sub(source, vex_source, template)

    def exchange(template, vex, pattern):
        regex = re.compile(pattern)
        try:
            template = re.sub(regex, regex.search(vex).group(), template)
        except AttributeError as e:
            print(f'The following pattern is not defined in the original .vex file: {pattern}')
        except Exception as e:
            print(f'Error exchanging the following pattern: {pattern} -> {e}')
        return template

    # get template session name
    re_session = re.compile(f'ref\s+\$EXPER\s*=\s*(.*);')
    template_session = re.search(re_session, template).group(1)
    vex_session = re.search(re_session, vex).group(1)
    template = template.replace(template_session, vex_session)

    # next change some entries of the $GLOBAL and $EXPER block
    template = exchange(template, vex, f'ref\s+\$EXPER\s*=\s*(.*);')
    template = exchange(template, vex, f'exper_name\s*=\s*(.*);')
    template = exchange(template, vex, f'exper_description\s*=\s*(.*);')
    template = exchange(template, vex, f'exper_nominal_start\s*=\s*(.*);')
    template = exchange(template, vex, f'exper_nominal_stop\s*=\s*(.*);')
    template = exchange(template, vex, f'contact_name\s*=\s*(.*);')
    template = exchange(template, vex, f'scheduler_name\s*=\s*(.*);')
    template = exchange(template, vex, f'scheduler_email\s*=\s*(.*);')
    template = exchange(template, vex, f'target_correlator\s*=\s*(.*);')
    template = exchange(template, vex, f'software\s*=\s*(.*);')
    template = exchange(template, vex, f'software_version\s*=\s*(.*);')
    template = exchange(template, vex, f'software_gui_version\s*=\s*(.*);')

    # Finally make sure that the mode name in the template matches the mode name in the original vex file
    mode = re.search(f'\$MODE[\s\S]*?def\s(.*);', template).group(1)
    sched_mode = re.compile(f'(mode\s*=\s*)(.*);')
    template = re.sub(sched_mode, f'\g<1>{mode};', template)

    with open(path_source, "w") as f:
        f.write(template)

    pass


if __name__ == "__main__":
    doc = "Replaces some elements in the $GLOBAL and $EXPER block, as well as the full $SOURCES and $SCHED " \
          "blocks in the template with the values from the source. The original vex file will get renamed to " \
          "session.vex.orig. The merged schedule is stored in the source location."

    parser = argparse.ArgumentParser(description=doc)
    parser.add_argument("-s", "--source", help="path to input vex file")
    parser.add_argument("-t", "--template", help="path to template vex file")

    args = parser.parse_args()
    from pathlib import Path

    if Path(args.source + ".orig").is_file():
        shutil.copy(args.source + ".orig", args.source)

    vex2vex_template(args.source, args.template)
