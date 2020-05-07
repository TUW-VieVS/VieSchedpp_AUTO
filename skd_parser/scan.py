import datetime
import operator


class Scan:
    def __init__(self, observations, name, start_time, source, cal_time, obs_time_total, postob_time, session):
        self.observations = observations
        self.name = name
        self.start_time = start_time
        self.source = source
        self.cal_time = cal_time
        self.obs_time_total = obs_time_total
        self.postob_time = postob_time
        self.session = session

    def __repr__(self):
        return self.name


class ScanList:
    def __init__(self, *scans):
        self.scans = list(scans)

    def append(self, item):
        self.scans.append(item)

    def remove(self, item):
        self.scans.remove(item)

    def get_scan_by_name(self, name):
        for scan in self.scans:
            if scan.name.lower() == name.lower():
                return scan
        return -1

    def total_seconds(self):
        scans_sorted = sorted(self.scans, key=operator.attrgetter('start_time'))
        return (scans_sorted[-1].start_time - scans_sorted[0].start_time +
                datetime.timedelta(seconds=scans_sorted[-1].obs_time_total)).total_seconds()

    def __iter__(self):
        scans_sorted = sorted(self.scans, key=operator.attrgetter('start_time'))
        for scan in scans_sorted:
            yield scan

    def update(self, other):
        for scan in other:
            if self.get_scan_by_name(scan.name) == -1:
                self.append(scan)
