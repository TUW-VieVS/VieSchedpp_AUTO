class Source:
    def __init__(self, name, ra, de, altname=""):
        self.name = name
        self.ra = ra
        self.de = de
        self.altname = altname
        self.flux = None


class SourceList:
    def __init__(self, *args):
        self.sources = list(args)

    def get_source_by_name(self, name):
        for source in self.sources:
            if source.name.lower() == name.lower() or source.altname.lower() == name.lower():
                return source
        return -1

    def append(self, item):
        self.sources.append(item)
