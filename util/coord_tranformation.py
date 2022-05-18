import numpy as np


def azel2rade(mjd, lat, lon, az, el):
    saz2 = az - np.pi
    zd2 = np.pi / 2 - el

    lqxy = np.array([np.cos(saz2), np.sin(saz2)])
    lqz = np.cos(zd2)
    scale = np.sqrt(1 - lqz ** 2 / (np.sum(lqxy ** 2)))
    lq2 = np.array([[lqxy[0] * scale, lqxy[1] * scale, lqz]]).T

    coLat = np.cos(np.pi / 2 - lat)
    siLat = np.sin(np.pi / 2 - lat)
    coLon = np.cos(lon)
    siLon = np.sin(lon)
    l2g = (np.array([[coLat, 0, -siLat], [0, -1, 0], [siLat, 0, coLat]]) @ np.array(
        [[coLon, siLon, 0], [-siLon, coLon, 0], [0, 0, 1]])).T
    rq2 = l2g @ lq2

    tu2 = mjd - 51544.5
    frac2 = mjd - np.floor(mjd) + 0.5
    fac2 = 0.00273781191135448
    era2 = 2 * np.pi * (frac2 + 0.7790572732640 + fac2 * tu2)
    era2 = np.mod(era2, 2 * np.pi)

    # rotation matrix for rotation around z-axis
    caEra2 = np.cos(-era2)
    siEra2 = np.sin(-era2)

    c2t = np.array([[caEra2, -siEra2, 0], [siEra2, caEra2, 0], [0, 0, 1]]).T

    q2 = c2t @ rq2

    ra2 = np.arctan2(q2[1][0], q2[0][0])
    de2 = np.pi / 2 - np.arccos(q2[2][0] / np.sqrt(np.sum(q2 ** 2)))
    return ra2, de2


def rade2azel(mjd, lat, lon, ra, de):
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

    q = np.array([cod * cor, cod * sir, sid]).T

    # rotation matrix for rotation around z-axis
    caEra = np.cos(-era)
    siEra = np.sin(-era)

    t2c = np.array([[caEra, -siEra, 0], [siEra, caEra, 0], [0, 0, 1]])

    # source in TRS (c2t = t2c')
    rq = np.dot(t2c, q)

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
