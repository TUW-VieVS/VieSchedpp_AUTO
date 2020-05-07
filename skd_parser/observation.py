import datetime

import numpy as np

from skd_parser.jdutil import datetime_to_jd, jd_to_mjd
from skd_parser.station import direction_from_wraps
from skd_parser.zazel_s import zazel_s


class Observation:
    def __init__(self, station, scan, duration, cable_wrap=None, prev_obs=None, next_obs=None):
        self.station = station
        self.scan = scan
        self.duration = duration
        self.cable_wrap = cable_wrap
        self._az_start = None
        self._el_start = None
        self._az_end = None
        self._el_end = None
        self.prev_obs = prev_obs
        self.next_obs = None
        self.log_entry = None

    def calc_azel_start(self, time=None):
        if time is None:
            time = self.scan.start_time
        start_mjd = jd_to_mjd(datetime_to_jd(time))
        self._az_start, self._el_start = zazel_s(start_mjd,
                                                 self.station.lon, self.station.lat,
                                                 self.scan.source.ra, self.scan.source.de)

    def calc_azel_end(self, time=None):
        if time is None:
            time = self.scan.start_time + datetime.timedelta(seconds=self.duration)
        start_mjd = jd_to_mjd(datetime_to_jd(time))
        self._az_end, self._el_end = zazel_s(start_mjd,
                                             self.station.lon, self.station.lat,
                                             self.scan.source.ra, self.scan.source.de)

    def get_az_start(self):
        if self._az_start is None:
            self.calc_azel_start()
        return self._az_start

    def get_el_start(self):
        if self._el_start is None:
            self.calc_azel_start()
        return self._el_start

    def set_az_start(self, value):
        self._az_start = value

    def set_el_start(self, value):
        self._el_start = value

    el_start = property(get_el_start, set_el_start, None, "Elevation of telescope for this observation")
    az_start = property(get_az_start, set_az_start, None, "Azimuth of telescope for this observation")

    def get_az_end(self):
        if self._az_end is None:
            self.calc_azel_end()
        return self._az_end

    def get_el_end(self):
        if self._el_end is None:
            self.calc_azel_end()
        return self._el_end

    def set_az_end(self, value):
        self._az_end = value

    def set_el_end(self, value):
        self._el_end = value

    el_end = property(get_el_end, set_el_end, None, "Elevation of telescope for this observation")
    az_end = property(get_az_end, set_az_end, None, "Azimuth of telescope for this observation")

    def get_slew_time(self, ignore_accel=True):
        return max(self.calc_slew_time(ignore_accel=ignore_accel))

    def get_slew_limit(self, ignore_accel=True):
        [el, az] = self.calc_slew_time(ignore_accel=ignore_accel)
        return "el" if el > az else "az"

    def calc_slew_time(self, ignore_accel):
        if self.next_obs is None:
            return [0, 0]
        curr_az = self.az_end
        curr_el = self.el_end
        curr_cw = self.cable_wrap

        next_az = self.next_obs.az_start
        next_el = self.next_obs.el_start
        next_cw = self.next_obs.cable_wrap

        curr_uaz = self.station.unwrap_azimuth(curr_az, curr_cw)
        next_uaz = self.station.unwrap_azimuth(next_az, next_cw)

        direction = direction_from_wraps(curr_cw, next_cw)
        if direction == -1:  # turn left
            delta_az = np.mod(curr_uaz - next_uaz, 2 * np.pi)
        elif direction == 1:  # turn right
            delta_az = np.mod(next_uaz - curr_uaz, 2 * np.pi)
        else:  # shortest
            delta_az = min(np.mod(curr_uaz - next_uaz, 2 * np.pi), np.mod(next_uaz - curr_uaz, 2 * np.pi))

        delta_el = abs(next_el - curr_el)

        if self.station.aaz is None or self.station.ael is None or ignore_accel:
            time_az = delta_az / self.station.vaz + self.station.c1
            time_el = delta_el / self.station.vel + self.station.c2
        else:
            t1 = self.station.vaz / self.station.aaz
            s1 = 2 * self.station.aaz * t1 ** 2 / 2  # 2* for accel and decel
            if delta_az < s1:
                time_az = 2 * np.sqrt(delta_az / self.station.aaz) + self.station.c1
            else:
                time_az = 2 * t1 + (delta_az - s1) / self.station.vaz + self.station.c1

            t2 = self.station.vel / self.station.ael
            s2 = 2 * self.station.ael * t2 ** 2 / 2  # 2* for accel and decel
            if delta_el < s2:
                time_el = 2 * np.sqrt(delta_el / self.station.ael) + self.station.c2
            else:
                time_el = 2 * t2 + (delta_el - s2) / self.station.vel + self.station.c2

        return [time_el, time_az]

    def calc_slew_time_eldep(self, ignore_accel):
        if not self.next_obs:
            return [0.0, 0.0]
        [time_el, time_az] = self.calc_slew_time(ignore_accel=ignore_accel)  # azimuth as earlier
        curr_el = self.el_end
        next_el = self.next_obs.el_start
        delta_el = abs(next_el - curr_el)
        mid_el = (curr_el + next_el) / 2.

        k = self.station.el_k
        d = self.station.el_d

        time_el += k * mid_el + d

        return [time_el, time_az]

    def calc_slew_time_pw(self, ignore_accel):
        if not self.next_obs:
            return [0.0, 0.0]
        [time_el, time_az] = self.calc_slew_time(ignore_accel=ignore_accel)  # azimuth as earlier
        curr_el = self.el_end
        next_el = self.next_obs.el_start

        el_start = min(curr_el, next_el)
        el_end = max(curr_el, next_el)

        if not self.station.pw:
            return time_el, time_az
        delta_els = []
        for i in range(len(self.station.pw)):
            class_start = self.station.pw.keys()[i]
            try:
                class_end = self.station.pw.keys()[i + 1]
            except IndexError:
                class_end = np.pi / 2
            if class_end < el_start or class_start > el_end:
                delta_el_in_class = 0
            else:
                delta_el_in_class = abs(min(el_end, class_end) - max(el_start, class_start))
            delta_els.append(delta_el_in_class)
        delta_els = np.array(delta_els)
        vels = np.array(self.station.pw.values())
        time_el = np.sum(delta_els / vels) + self.station.c2
        return time_el, time_az

    def __repr__(self):
        return self.scan.name + ": " + self.station.name + " --> " + self.scan.source.name


class ObservationList:
    def __init__(self, *args):
        self.obs = list(args)

    def append(self, item):
        self.obs.append(item)

    def get_observation_by_station(self, station):
        for ob in self.obs:
            if ob.station == station:
                return ob
        return -1

    def get_observation_by_station_name(self, station_name):
        for ob in self.obs:
            if ob.station.name.lower() == station_name.lower():
                return ob
        return -1

    def __iter__(self):
        for obs in self.obs:
            yield obs
