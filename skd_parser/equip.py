from math import sin


class Equip:

    def __init__(self, sefd_x, sefd_s):
        self.sefd_x = sefd_x
        self.sefd_s = sefd_s
        pass

    def sefd(self, band, el):
        if band.lower() == "x":
            return self.sefd_x
        if band.lower() == "s":
            return self.sefd_s
        pass


class Equip_el(Equip):

    def __init__(self, sefd_x, sefd_s, coef_x, coef_s):
        super().__init__(sefd_x, sefd_s)
        self.coef_x = coef_x
        self.coef_s = coef_s
        pass

    def sefd(self, band, el):
        if band.lower() == "x":
            tmp = sin(el) ** self.coef_x[0]
            fac = self.coef_x[1] + self.coef_x[2] / tmp
            if fac < 1:
                fac = 1
            return self.sefd_x * fac
        if band.lower() == "s":
            tmp = sin(el) ** self.coef_s[0]
            fac = self.coef_s[1] + self.coef_s[2] / tmp
            if fac < 1:
                fac = 1
            return self.sefd_s * fac
        pass
