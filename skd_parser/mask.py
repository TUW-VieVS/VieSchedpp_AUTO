from math import pi

DEG2RAD = pi / 180
RAD2DEG = 180 / pi


class Step():
    def __init__(self, coef):
        az = coef[0::2]
        el = coef[1::2]
        i = 0
        mask_az = []
        mask = []
        for a in range(361):
            if a > az[i + 1]:
                i += 1
            mask.append(el[i] * DEG2RAD)
            mask_az.append(a * DEG2RAD)
        self.mask = mask
        self.mask_az = mask_az
        pass

    def visible(self, az, el):
        idx = round(az * RAD2DEG)
        el_mask = self.mask[idx]
        return el >= el_mask


class Line():
    def __init__(self, coef):
        az = coef[0::2]
        el = coef[1::2]
        i = 0
        mask_az = []
        mask = []
        for a in range(361):
            if a > az[i + 1]:
                i += 1
            delta = (a - az[i]) / (az[i + 1] - az[i])
            e = el[i] + delta * (el[i + 1] - el[i])
            mask.append(e * DEG2RAD)
            mask_az.append(a * DEG2RAD)
        self.mask = mask
        self.mask_az = mask_az
        pass

    def visible(self, az, el):
        idx = round(az * RAD2DEG)
        el_mask = self.mask[idx]
        return el >= el_mask
