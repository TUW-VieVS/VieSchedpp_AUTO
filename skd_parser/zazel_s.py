import numpy as np


def zazel_s(mjd, lon, lat, ra, de):
    """
    ZAZEL_S adapted from VieVS' zazel_s.m
    lwiniwar, with permission from mschartner
    GEO/TU Wien 2017
    :param mjd: 
    :param lon: 
    :param lat: 
    :param ra: 
    :param de: 
    :return: 
    """
    tu = mjd - 51544.5
    frac = mjd - np.floor(mjd) + 0.5
    fac = 0.00273781191135448
    era = 2 * np.pi * (frac + 0.7790572732640 + fac * tu)
    era = np.mod(era, 2 * np.pi)

    # source vector CRF
    sid = np.sin(de)
    cod = np.cos(de)
    sir = np.sin(ra)
    cor = np.cos(ra)

    rq = np.array([cod * cor, cod * sir, sid]).T

    # rotation matrix for rotation around z-axis
    caEra = np.cos(-era)
    siEra = np.sin(-era)

    t2c = np.array([[caEra, -siEra, 0], [siEra, caEra, 0], [0, 0, 1]])

    # source in TRS (c2t = t2c')
    rq = np.dot(t2c, rq)

    # source in local system
    coLat = np.cos(np.pi / 2 - lat)
    siLat = np.sin(np.pi / 2 - lat)
    coLon = np.cos(lon)
    siLon = np.sin(lon)

    g2l = np.dot(np.array([[coLat, 0, -siLat], [0, -1, 0], [siLat, 0, coLat]]),
                 np.array([[coLon, siLon, 0], [-siLon, coLon, 0], [0, 0, 1]]))
    lq = np.dot(g2l, rq)

    zd = np.arccos(lq[2])
    el = np.pi / 2 - zd
    saz = np.arctan2(lq[1], lq[0])
    saz += (np.pi * 2) if saz < 0 else 0
    az = saz + np.pi
    az = np.mod(az, np.pi * 2)
    return (az, el)


if __name__ == '__main__':
    testcases = [{
        'mjd': 2457849.254861111,
        'lon': 244.65 * np.pi / 180,  # YARRA 12M
        'lat': -29.05 * np.pi / 180,
        'ra': 08.583148 * np.pi / (15 * 180),  # 0858-279
        'de': -27.56329 * np.pi / 180,
        'el': 0.369993259427594,
        'az': 4.352358447134368,
    },
        {
            'mjd': 2457849.2569444445,
            'lon': 244.65 * np.pi / 180,  # YARRA 12M
            'lat': -29.05 * np.pi / 180,
            'ra': 08.583148 * np.pi / (15 * 180),  # 0858-279
            'de': -27.56329 * np.pi / 180,
            'el': 0.359264178110300,
            'az': 4.347537745378729,
        },
        {
            'mjd': 2457849.2569444445,
            'lon': 244.65 * np.pi / 180,  # YARRA 12M
            'lat': -29.05 * np.pi / 180,
            'ra': 07.231782 * np.pi / (15 * 180),  # 0723-008
            'de': -00.48550 * np.pi / 180,
            'el': 0.146419985157314,
            'az': 4.784569197717226,
        },
        {
            'mjd': 57000.00,
            'lon': (16 + 180) * np.pi / 180,  # WIEN
            'lat': 48 * np.pi / 180,
            'ra': 07.231782 * np.pi / (15 * 180),  # SKY
            'de': -27.56329 * np.pi / 180,
            'el': -0.318318951389518,
            'az': 1.941359456707980,
        }]
    for case in testcases:
        # pprint.pprint(case)
        az, el = zazel_s(case['mjd'], case['lon'], case['lat'], case['ra'], case['de'])
        print(el - case['el']) / np.pi * 180., (az - case['az']) / np.pi * 180.
