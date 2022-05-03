import argparse
import re
import shutil


def skd2skd_template(path_source, path_template):
    """
    This function can be used to copy some blocks of a .skd schedule to a .skd template. This is useful if you have a
    working .skd file (the template - e.g. an old successful session) and want to add the new schedule into this
    template. In particular, it will exchange parts of the $EXPER and $PARA block, as well as the full $SOURCES,
    $FLUX and $SKED blocks. The original schedule file will be overwritten by this function, but a backup is generated
    in the same folder named "{path_source}.skd.old"

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
    # Within the sources block, there might be other $ signs.
    # Therefore, use "^\s*\$|\Z" as the end
    sked = re.compile(f'\$SKED[\S\s]*?(?=^\s*\$|\Z)', re.MULTILINE)
    source = re.compile(f'\$SOURCES[\S\s]*?(?=^\s*\$|\Z)', re.MULTILINE)
    flux = re.compile(f'\$FLUX[\S\s]*?(?=^\s*\$|\Z)', re.MULTILINE)

    # read template
    with open(path_template) as f:
        template = f.read()

    # make a backup of the original schedule
    shutil.copy(path_source, path_source + ".old")

    # read the schedule
    with open(path_source) as f:
        skd = f.read()
    skd_sked = sked.search(skd).group()
    skd_source = source.search(skd).group()
    skd_flux = flux.search(skd).group()

    # exchange $SOURCES, $SKED and $FLUX block of template with the blocks from the schedule
    template = re.sub(sked, skd_sked, template)
    template = re.sub(source, skd_source, template)
    template = re.sub(flux, skd_flux, template)

    # next change some entries of the $EXPER and $PARAM block
    exper = re.compile(f'\$EXPER\s+(.*)')
    description = re.compile(f'DESCRIPTION\s+(.*)\n')
    software = re.compile(f'SCHEDULING_SOFTWARE\s+(.*?)\s')
    version = re.compile(f'SOFTWARE_VERSION\s+(.*?)\s')
    created = re.compile(f'SCHEDULE_CREATE_DATE\s+(.*?)\s')
    scheduler = re.compile(f'SCHEDULER\s+(.*?)\s')
    correlator = re.compile(f'CORRELATOR\s+(.*?)\s')
    start = re.compile(f'START\s+(.*?)\s')
    end = re.compile(f'END\s+(.*?)\s')

    template = re.sub(exper, exper.search(skd).group(), template)
    template = re.sub(description, description.search(skd).group()[:-1] + "_skd_converted\n", template)
    template = re.sub(software, software.search(skd).group(), template)
    template = re.sub(version, version.search(skd).group(), template)
    template = re.sub(created, created.search(skd).group(), template)
    template = re.sub(scheduler, scheduler.search(skd).group(), template)
    template = re.sub(correlator, correlator.search(skd).group(), template)
    template = re.sub(start, start.search(skd).group(), template)
    template = re.sub(end, end.search(skd).group(), template)

    with open(path_source, "w") as f:
        f.write(template)

    pass


if __name__ == "__main__":
    doc = "Replaces some elements in the $EXPER and $PARA block, as well as the full $SOURCES, $FLUX and $SKED " \
          "blocks in the template with the values from the source. The original skd file will get renamed to " \
          "session.skd.old. The merged schedule is stored in the source location."

    parser = argparse.ArgumentParser(description=doc)
    parser.add_argument("-s", "--source", help="path to input skd file")
    parser.add_argument("-t", "--template", help="path to template skd file")

    args = parser.parse_args()
    skd2skd_template(args.source, args.template)
