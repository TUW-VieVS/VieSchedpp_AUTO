import os

from Helper import read_sources


def upload_vex_in_sked_format(**kwargs):
    path = kwargs["path"]
    print("TODO: convert .skd to .vex in \"sked format\" and upload it")
    pass


def update_source_list(**kwargs):
    path = kwargs["path"]
    ds = kwargs["ds"]
    session = kwargs["session"]
    session_code = session["code"]
    code = kwargs["code"]

    target_source_list = os.path.join("Templates", code, "source.cat.target")
    calib_source_list = os.path.join("Templates", code, "source.cat.calib")

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
