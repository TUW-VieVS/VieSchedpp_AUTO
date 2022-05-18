from math import sqrt, sin, cos, exp, pi

FLCON1 = (pi * pi) / (4.0 * 0.6931471)
FLCON2 = pi / (3600.0 * 180.0 * 1000.0)
DEG2RAD = pi / 180


class M():
    def __init__(self):
        self.x = []
        self.s = []
        pass

    def add(self, band, coef):
        m = {'flux': coef[0],
             'majorAxis': coef[1] * FLCON2,
             'axialRatio': coef[2],
             'positionAngle': coef[3] * DEG2RAD,
             }

        if band.lower() == "x":
            self.x.append(m)
        else:
            self.s.append(m)

    def flux(self, band, uv):
        obs = 0

        if band.lower() == "x":
            model = self.x
            wavelength = 0.03490528971653583
        else:
            model = self.s
            wavelength = 0.13085659450021825

        u_w = uv[0] / wavelength
        v_w = uv[1] / wavelength

        for m in model:
            pa = m['positionAngle']
            ucospa = u_w * cos(pa)
            usinpa = u_w * sin(pa)
            vcospa = v_w * cos(pa)
            vsinpa = v_w * sin(pa)

            ar = m['axialRatio']
            f = m['flux']
            ma = m['majorAxis']

            arg1 = (vcospa + usinpa) * (vcospa + usinpa)
            arg2 = (ar * (ucospa - vsinpa)) * (ar * (ucospa - vsinpa))
            arg = -FLCON1 * (arg1 + arg2) * ma * ma
            f1 = f * exp(arg)
            obs += f1
        return obs


class B():
    def __init__(self):
        self.bl_length_x = []
        self.bl_length_s = []
        self.flux_x = []
        self.flux_s = []
        pass

    def add(self, band, coef):

        bl_length = coef[0::2]
        flux = coef[1::2]
        if band.lower() == "x":
            self.bl_length_x = bl_length
            self.flux_x = flux
        else:
            self.bl_length_s = bl_length
            self.flux_s = flux

    def flux(self, band, uv):
        length = sqrt(uv[0] * uv[0] + uv[1] * uv[1]) / 1000

        if band == "x":
            bl_length = self.bl_length_x
            flux = self.flux_x
        else:
            bl_length = self.bl_length_s
            flux = self.flux_s

        for i in range(1, len(bl_length)):
            if bl_length[i] > length:
                return flux[i - 1]
