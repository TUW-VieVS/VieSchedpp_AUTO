import datetime
import re

import numpy as np

from skd_parser.observation import Observation, ObservationList
from skd_parser.scan import Scan, ScanList
from skd_parser.source import Source, SourceList
from skd_parser.station import Station, StationList
from skd_parser.equip import Equip, Equip_el
from skd_parser.mask import Step, Line
from skd_parser.flux import B, M


class skdParser:
    def __init__(self, filename):
        self.filename = filename
        self.stations = StationList()
        self.scans = ScanList()
        self.sources = SourceList()
        self.times = {}
        self.session_name = None
        self.data_rate = {"x": 0, "s": 0}
        self.obs_mode_eta = 0
        self.maxscan = 0
        self.snr = {"X": 0, "S": 0}

    def parse_stations(self):

        equip2sta = dict()
        mask2sta = dict()

        with open(self.filename, 'r') as f:
            station_section = False
            for line in f.readlines():
                if line.startswith("$"):
                    station_section = line.startswith("$STATIONS")
                if station_section:
                    ant_info = re.search(
                        r'^A\s+(\S+)\s+(\S+)\s+\S+\s+\S+\s+(\S+)\s+(\S+)\s+'
                        r'(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)',
                        line)
                    pos_info = re.search(r'^P\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+\S+\s+(\S+)\s+(\S+)', line)

                    if ant_info:
                        station = self.stations.get_station_by_name(ant_info.group(2))
                        if station == -1:
                            station = Station()
                            self.stations.append(station)

                        station.name1 = ant_info.group(1)
                        station.name = ant_info.group(2)
                        equip2sta[ant_info.groups()[-2].lower()] = station.name
                        mask2sta[ant_info.groups()[-1].lower()] = station.name

                        station.c1 = float(ant_info.group(4))
                        station.c2 = float(ant_info.group(8))
                        station.azmax = float(ant_info.group(5)) * np.pi / 180.
                        station.azmin = float(ant_info.group(6)) * np.pi / 180.
                        station.vaz = float(ant_info.group(3)) * np.pi / 180. / 60.  # [rad/s]
                        station.vel = float(ant_info.group(7)) * np.pi / 180. / 60.  # [rad/s]
                        if station.name in ['YARRA12M', 'HOBART12', 'KATH12M']:
                            station.aaz = 1.3 * np.pi / 180.  # [rad/s]
                            station.ael = 1.3 * np.pi / 180.  # [rad/s]

                    if pos_info:
                        station = self.stations.get_station_by_name(pos_info.group(2))
                        if station == -1:
                            station = Station()
                            self.stations.append(station)

                        station.name2 = pos_info.group(1)
                        station.x = float(pos_info.group(3))
                        station.y = float(pos_info.group(4))
                        station.z = float(pos_info.group(5))
                        station.lon = np.pi / 180. * (360 - float(pos_info.group(6)))
                        station.lat = np.pi / 180. * float(pos_info.group(7))

                    if line.startswith("H"):
                        tmp = line.split()
                        mask = [float(x) for x in tmp[2:]]
                        if len(mask) % 2 == 0:
                            mask = Line(mask)
                        else:
                            mask = Step(mask)
                        station = self.stations.get_station_by_name(mask2sta[tmp[1].lower()])
                        station.mask = mask

                    if line.startswith("T"):
                        try:
                            tmp = line.split()
                            sefd_x = float(tmp[6])
                            sefd_s = float(tmp[8])
                            if len(tmp) == 11:
                                eq = Equip(sefd_x, sefd_s)
                            elif len(tmp) == 19:
                                band_a = tmp[9]
                                coef_a = [float(a) for a in tmp[10:13]]
                                band_b = tmp[13]
                                coef_b = [float(a) for a in tmp[14:17]]
                                if band_a.lower() == "x":
                                    coef_x = coef_a
                                    coef_s = coef_b
                                else:
                                    coef_x = coef_b
                                    coef_s = coef_a

                                eq = Equip_el(sefd_x, sefd_s, coef_x, coef_s)
                        except:
                            print(f"error parsing EQUIP .cat")
                            eq = Equip(1, 1)
                        else:
                            eq = Equip(1, 1)
                            print("failed to parse equip block (not critical)")

                        station = self.stations.get_station_by_name(equip2sta[tmp[1].lower()])
                        station.equip = eq

    def parse_sources(self):
        with open(self.filename, 'r') as f:
            source_section = False
            for line in f.readlines():
                if line.startswith("$"):
                    source_section = line.startswith("$SOURCES")
                if source_section:
                    source_info = re.search(r'^\s*(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)',
                                            line)
                    if source_info:
                        ra = 15. * np.pi / 180. * (abs(float(source_info.group(3))) +
                                                   abs(float(source_info.group(4))) / 60 +
                                                   abs(float(source_info.group(5))) / 3600)

                        ra *= -1 if np.any([float(source_info.group(k)) < 0 for k in [3, 4, 5]]) else 1

                        de = np.pi / 180. * (abs(float(source_info.group(6))) +
                                             abs(float(source_info.group(7))) / 60 +
                                             abs(float(source_info.group(8))) / 3600)

                        de *= -1 if np.any([float(source_info.group(k)) < 0 for k in [6, 7, 8]]) else 1

                        source = self.sources.get_source_by_name(source_info.group(1))
                        if source == -1:
                            source = Source(name=source_info.group(1),
                                            ra=ra,
                                            de=de)
                            self.sources.append(source)

                        if source_info.group(2) != "$":
                            source.altname = source_info.group(2)

    def parse_observations(self):
        with open(self.filename, 'r') as f:
            obs_section = False
            stations_last_obs = {}
            scan_counts = {}
            for line in f.readlines():
                if line.startswith("$"):
                    obs_section = line.startswith("$SKED")
                if obs_section:
                    SKED = re.search(r'^(\S+)\s+(\S+)\s+\S+\s+\S+\s+(\d{2})(\d{3})(\d{2})(\d{2})(\d{2})'
                                     r'\s+(\d+)\s+\S+\s+(\d+)\s+\S+\s+(\S+)', line)
                    if SKED:
                        start_time = datetime.datetime.strptime("%2s.%3s.%2s:%2s:%2s" %
                                                                (SKED.group(3),
                                                                 SKED.group(4),
                                                                 SKED.group(5),
                                                                 SKED.group(6),
                                                                 SKED.group(7)),
                                                                "%y.%j.%H:%M:%S")
                        scan_code = start_time.strftime("%j-%H%M")

                        scan = self.scans.get_scan_by_name(scan_code)
                        if scan != -1:
                            scan_counts[scan.name] = 1
                            scan.name = scan.name + "a"

                        count = scan_counts.get(scan_code, 0)
                        if count >= 1:
                            scan_name = scan_code + chr(97 + count)
                            scan_counts[scan_code] += 1
                        else:
                            scan_name = scan_code

                        scan = Scan(observations=ObservationList(),
                                    name=scan_name,
                                    start_time=start_time,
                                    source=self.sources.get_source_by_name(SKED.group(1)),
                                    cal_time=int(SKED.group(2)),
                                    obs_time_total=int(SKED.group(8)),
                                    postob_time=int(SKED.group(9)),
                                    session=self.session_name
                                    )

                        self.scans.append(scan)

                        for i in range(int(len(SKED.group(10)) / 2)):
                            station = self.stations.get_station_by_1char(SKED.group(10)[i * 2])
                            wrap = SKED.group(10)[i * 2 + 1]

                            search_str = r'\s+(\S+)' + int((len(SKED.group(10)) / 2 - i - 1)) * (r'\s+\S+') + r'\s*$'
                            get_station_duration = re.search(search_str, line)
                            duration = None
                            if get_station_duration:
                                duration = int(get_station_duration.group(1))

                            observation = Observation(station=station,
                                                      scan=scan,
                                                      duration=duration,
                                                      cable_wrap=wrap,
                                                      prev_obs=stations_last_obs.get(station, None)
                                                      )
                            if observation.prev_obs:
                                observation.prev_obs.next_obs = observation  # double link <->
                            stations_last_obs[station] = observation
                            scan.observations.append(observation)

    def parse_flux(self):
        try:
            with open(self.filename, 'r') as f:
                flux_section = False
                for line in f.readlines():
                    if line.startswith("$"):
                        flux_section = line.startswith("$FLUX")
                        continue
                    if flux_section:
                        tmp = line.split()
                        name = tmp[0]
                        band = tmp[1].lower()
                        type = tmp[2]
                        src = self.sources.get_source_by_name(name)
                        if src.flux is None:
                            if type == "M":
                                src.flux = M()
                            elif type == "B":
                                src.flux = B()
                            else:
                                Exception("ERROR parsing flux block")
                        coef = [float(a) for a in tmp[3:]]
                        src.flux.add(band, coef)
                        pass
        except Exception as e:
            print(e)

    def parse_codes(self):
        try:
            with open(self.filename, 'r') as f:
                codes_section = False
                bits = 2
                bit2effic = {1: 0.6366 * 0.97, 2: 0.625 * 0.97}
                chan_x = 0
                chan_s = 0
                count_F = 0
                for line in f.readlines():
                    if line.startswith("$"):
                        codes_section = line.startswith("$CODES")
                        continue
                    if codes_section:
                        if line.startswith("F"):
                            count_F += 1

                        if line.startswith("C") and count_F == 1:
                            tmp = line.split()
                            tracks = len(list(filter(None, tmp[-1].split(","))))
                            bits = min(tracks, bits)
                            freq = tmp[3]
                            if freq.startswith("8"):
                                chan_x += tracks
                            elif freq.startswith("2"):
                                chan_s += tracks
                            else:
                                print(f"cannot assign band to {line}")
                        if line.startswith("R"):
                            sample_rate = float(line.split()[-1])
                            self.data_rate["x"] = chan_x * sample_rate
                            self.data_rate["s"] = chan_s * sample_rate

                            eta = bit2effic[bits]
                            self.obs_mode_eta = eta
                            break
        except Exception as e:
            print(e)

    def parse(self):
        with open(self.filename, 'r') as f:
            for line in f.readlines():
                times = re.search(r"^SETUP\s+(\d+) SOURCE\s+(\d+) TAPETM\s+(\d+)", line)
                maxscan = re.search(r"MAXSCAN\s+(\d+)", line)
                first_snr = True
                snr = re.search(r"SNR\s+\S+\s+(X|S)\s+(\S+)\s+\S+\s+(X|S)\s+(\S+)", line)
                if times:
                    self.times['setup'] = int(times.group(1))
                    self.times['source'] = int(times.group(2))
                    self.times['tapetm'] = int(times.group(3))
                if maxscan:
                    self.maxscan = float(maxscan.group(1))
                if first_snr and snr:
                    band_a = snr.group(1).lower()
                    snr_a = float(snr.group(2))
                    band_b = snr.group(3).lower()
                    snr_b = float(snr.group(4))
                    self.snr[band_a] = snr_a
                    self.snr[band_b] = snr_b

                name = re.search(r"^\$EXPER (\S+)", line)
                if name:
                    self.session_name = name.group(1)

        self.parse_sources()
        self.parse_stations()
        self.parse_observations()
        self.parse_flux()
        self.parse_codes()

    def getScanList(self):
        return self.scans


if __name__ == "__main__":
    # skd = skdParser('/home/mschartner/Downloads/t2153.skd')
    skd = skdParser('/home/mschartner/Downloads/z22129.skd')
    skd.parse()
    pass
