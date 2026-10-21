class VC99Reading:
    def __init__(self):
        self.valid = False
        self.overload = False
        self.negative = False

        self.value = 0.0
        self.has_value = False
        self.counts = 0  # surowe zliczenia (0-6000)

        self.prefix = ""
        self.unit = ""

        # Tryby pomiaru (bajt 7)
        self.dc = False
        self.ac = False
        self.auto_mode = False
        self.rel = False
        self.hold = False
        self.bpn = False  # bargraph widoczny

        # Bajt 8
        self.z1 = False  # w VC99 czesto "dioda"
        self.z2 = False
        self.max_flag = False
        self.min_flag = False
        self.apo = False
        self.bat_low = False
        self.nano = False

        # Bajt 9
        self.micro = False
        self.milli = False
        self.kilo = False
        self.mega = False
        self.beep = False       # ciaglosc
        self.diode = False
        self.percent = False

        # Bajt 10
        self.volt = False
        self.ampere = False
        self.ohm = False
        self.hfe = False
        self.hertz = False
        self.farad = False
        self.celsius = False
        self.fahrenheit = False

        # Bajt 11 - bargraf
        self.bargraph = 0

        self.raw_hex = ""


class VC99Parser:
    OVERLOAD = b"?0:?"

    @staticmethod
    def is_valid_frame(frame_bytes):
        if len(frame_bytes) != 14:
            return False
        if frame_bytes[12] != 0x0D or frame_bytes[13] != 0x0A:
            return False
        if frame_bytes[0] not in (0x2B, 0x2D):
            return False
        return True

    @staticmethod
    def parse(frame_bytes):
        r = VC99Reading()
        r.raw_hex = ' '.join(f'{b:02X}' for b in frame_bytes)

        if not VC99Parser.is_valid_frame(frame_bytes):
            r.valid = False
            return r

        b = frame_bytes

        r.negative = (b[0] == 0x2D)

        # Bajty 1-4: cyfry lub stan O.L "?0:?"
        if b[1:5] == VC99Parser.OVERLOAD:
            r.overload = True
            r.has_value = False
        elif all(0x30 <= c <= 0x39 for c in b[1:5]):
            digits = bytes(b[1:5]).decode("ascii")
            intval = int(digits)
            r.counts = intval

            # Bajt 6: pozycja przecinka ('0','1','2','4')
            dec_exp = {0x30: 0, 0x31: -3, 0x32: -2, 0x34: -1}.get(b[6], 0)

            r.value = float(intval) * (10.0 ** dec_exp)
            if r.negative:
                r.value = -r.value
            r.has_value = True
        else:
            r.overload = False
            r.has_value = False

        # Bajt 7: flagi trybu
        r.bpn = (b[7] & 0x01) != 0
        r.hold = (b[7] & 0x02) != 0
        r.rel = (b[7] & 0x04) != 0
        r.ac = (b[7] & 0x08) != 0
        r.dc = (b[7] & 0x10) != 0
        r.auto_mode = (b[7] & 0x20) != 0

        # Bajt 8
        r.z1 = (b[8] & 0x80) != 0
        r.z2 = (b[8] & 0x40) != 0
        r.max_flag = (b[8] & 0x20) != 0
        r.min_flag = (b[8] & 0x10) != 0
        r.apo = (b[8] & 0x08) != 0
        r.bat_low = (b[8] & 0x04) != 0
        r.nano = (b[8] & 0x02) != 0

        # Bajt 9
        r.micro = (b[9] & 0x80) != 0
        r.milli = (b[9] & 0x40) != 0
        r.kilo = (b[9] & 0x20) != 0
        r.mega = (b[9] & 0x10) != 0
        r.beep = (b[9] & 0x08) != 0
        r.diode = (b[9] & 0x04) != 0
        r.percent = (b[9] & 0x02) != 0

        # Bajt 10
        r.volt = (b[10] & 0x80) != 0
        r.ampere = (b[10] & 0x40) != 0
        r.ohm = (b[10] & 0x20) != 0
        r.hfe = (b[10] & 0x10) != 0
        r.hertz = (b[10] & 0x08) != 0
        r.farad = (b[10] & 0x04) != 0
        r.celsius = (b[10] & 0x02) != 0
        r.fahrenheit = (b[10] & 0x01) != 0

        # Prefiks
        if r.nano:
            r.prefix = "n"
        elif r.micro:
            r.prefix = "\u00b5"
        elif r.milli:
            r.prefix = "m"
        elif r.kilo:
            r.prefix = "k"
        elif r.mega:
            r.prefix = "M"

        # Jednostka
        if r.volt:
            r.unit = "V"
        elif r.ampere:
            r.unit = "A"
        elif r.ohm:
            r.unit = "\u03a9"
        elif r.hfe:
            r.unit = "hFE"
        elif r.hertz:
            r.unit = "Hz"
        elif r.farad:
            r.unit = "F"
        elif r.celsius:
            r.unit = "\u00b0C"
        elif r.fahrenheit:
            r.unit = "\u00b0F"
        elif r.percent:
            r.unit = "%"

        # Bargraf (bajt 11) - tylko gdy widoczny
        if r.bpn:
            sign = -1 if (b[11] & 0x80) else 1
            r.bargraph = (b[11] & 0x7F) * sign

        r.valid = True
        return r
