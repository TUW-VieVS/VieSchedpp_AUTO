import operator
from collections import OrderedDict

import numpy as np

wraps = {
    'W': -1,
    '-': 0,
    'C': 1
}


def direction_from_wraps(wrap1, wrap2):
    w1 = wraps[wrap1]
    w2 = wraps[wrap2]
    if w1 < w2:
        return +1
    if w1 == w2:
        return 0
    if w1 > w2:
        return -1


class Station:
    def __init__(self, name=None, name2=None, name1=None,
                 x=None, y=None, z=None,
                 c1=None, c2=None,
                 lat=None, lon=None,
                 vaz=None, vel=None,
                 azmin=None, azmax=None,
                 aaz=None, ael=None):
        self.name = name
        self.name2 = name2
        self.name1 = name1
        self.x = x
        self.y = y
        self.z = z
        self.c1 = c1
        self.c2 = c2
        self.azmin = azmin
        self.azmax = azmax
        self.lat = lat
        self.lon = lon
        self.vaz = vaz
        self.vel = vel
        self.aaz = aaz
        self.ael = ael

        self.el_k = 0
        self.el_d = 0
        self.pw = OrderedDict()

    def __repr__(self):
        return self.name

    def unwrap_azimuth(self, wrapped_azi, cable_wrap):
        normalmin = self.azmin
        normalmax = self.azmax
        while normalmin > 0:
            normalmin -= 2 * np.pi
            normalmax -= 2 * np.pi
        reducedazi = wrapped_azi - normalmin
        if cable_wrap == '-':
            return reducedazi
        elif cable_wrap == 'C':
            return reducedazi + 2 * np.pi
        elif cable_wrap == 'W':
            return reducedazi


class StationList:
    def __init__(self, *args):
        self.stations = list(args)

    def get_station_by_name(self, name):
        for station in self.stations:
            if station.name.lower() == name.lower():
                return station
        return -1

    def get_station_by_1char(self, char):
        for station in self.stations:
            if station.name1.lower() == char.lower():
                return station
        return -1

    def get_station_by_2char(self, char):
        for station in self.stations:
            if station.name2.lower() == char.lower():
                return station
        return -1

    def __contains__(self, item):
        return item in self.stations

    def append(self, item):
        self.stations.append(item)

    def __iter__(self):
        stations_sorted = sorted(self.stations, key=operator.attrgetter('name'))
        for stations in stations_sorted:
            yield stations

    def __getitem__(self, item):
        stations_sorted = sorted(self.stations, key=operator.attrgetter('name'))
        return stations_sorted[item]

    def __len__(self):
        return len(self.stations)

    def indexof(self, station):
        stations_sorted = sorted(self.stations, key=operator.attrgetter('name'))
        for i, stations in enumerate(stations_sorted):
            if station == stations:
                return i

    def update(self, other):
        for station in other:
            if self.get_station_by_name(station.name) == -1:
                self.append(station)
