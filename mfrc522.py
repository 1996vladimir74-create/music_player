from time import sleep_ms, ticks_ms, ticks_diff


class MFRC522:
    PCD_IDLE = 0x00
    PCD_CALC_CRC = 0x03
    PCD_TRANSCEIVE = 0x0C
    PCD_SOFT_RESET = 0x0F

    PICC_REQA = 0x26
    PICC_WUPA = 0x52
    PICC_ANTICOLL_CL1 = 0x93
    PICC_ANTICOLL_CL2 = 0x95
    PICC_HALT = 0x50

    STATUS_OK = 0
    STATUS_TIMEOUT = 1
    STATUS_ERROR = 2

    CommandReg = 0x01
    ComIEnReg = 0x02
    ComIrqReg = 0x04
    DivIrqReg = 0x05
    ErrorReg = 0x06
    FIFODataReg = 0x09
    FIFOLevelReg = 0x0A
    ControlReg = 0x0C
    BitFramingReg = 0x0D
    CollReg = 0x0E
    ModeReg = 0x11
    TxControlReg = 0x14
    TxASKReg = 0x15
    RFCfgReg = 0x26
    TModeReg = 0x2A
    TPrescalerReg = 0x2B
    TReloadHReg = 0x2C
    TReloadLReg = 0x2D
    CRCResultHReg = 0x21
    CRCResultLReg = 0x22

    def __init__(self, spi, cs, rst=None):
        self.spi = spi
        self.cs = cs
        self.rst = rst
        self.cs.value(1)
        if rst is not None:
            rst.value(1)
        self.init()

    def _write(self, reg, value):
        self.cs.value(0)
        self.spi.write(bytes([((reg << 1) & 0x7E), value & 0xFF]))
        self.cs.value(1)

    def _read(self, reg):
        self.cs.value(0)
        self.spi.write(bytes([((reg << 1) & 0x7E) | 0x80]))
        value = self.spi.read(1, 0)[0]
        self.cs.value(1)
        return value

    def _set_bitmask(self, reg, mask):
        self._write(reg, self._read(reg) | mask)

    def _clear_bitmask(self, reg, mask):
        self._write(reg, self._read(reg) & (~mask))

    def reset(self):
        if self.rst is not None:
            self.rst.value(0)
            sleep_ms(2)
            self.rst.value(1)
            sleep_ms(50)
        self._write(self.CommandReg, self.PCD_SOFT_RESET)
        sleep_ms(50)

    def init(self):
        self.reset()
        self._write(self.TModeReg, 0x8D)
        self._write(self.TPrescalerReg, 0x3E)
        self._write(self.TReloadLReg, 30)
        self._write(self.TReloadHReg, 0)
        self._write(self.TxASKReg, 0x40)
        self._write(self.ModeReg, 0x3D)
        self._write(self.RFCfgReg, 0x70)
        self.antenna_on()

    def antenna_on(self):
        if (self._read(self.TxControlReg) & 0x03) != 0x03:
            self._set_bitmask(self.TxControlReg, 0x03)

    def _transceive(self, send_data, valid_bits=0, timeout_ms=30):
        self._write(self.CommandReg, self.PCD_IDLE)
        self._write(self.ComIEnReg, 0xF7)
        self._write(self.ComIrqReg, 0x7F)
        self._write(self.FIFOLevelReg, 0x80)
        for b in send_data:
            self._write(self.FIFODataReg, b)
        self._write(self.BitFramingReg, valid_bits & 0x07)
        self._write(self.CommandReg, self.PCD_TRANSCEIVE)
        self._set_bitmask(self.BitFramingReg, 0x80)

        start = ticks_ms()
        while ticks_diff(ticks_ms(), start) < timeout_ms:
            irq = self._read(self.ComIrqReg)
            if irq & 0x01:
                self._clear_bitmask(self.BitFramingReg, 0x80)
                return self.STATUS_TIMEOUT, b""
            if irq & 0x30:
                break

        self._clear_bitmask(self.BitFramingReg, 0x80)
        if ticks_diff(ticks_ms(), start) >= timeout_ms:
            return self.STATUS_TIMEOUT, b""

        error = self._read(self.ErrorReg)
        if error & 0x13:
            return self.STATUS_ERROR, b""

        length = self._read(self.FIFOLevelReg)
        if length == 0:
            return self.STATUS_ERROR, b""
        if length > 18:
            length = 18
        data = bytearray(length)
        for i in range(length):
            data[i] = self._read(self.FIFODataReg)
        return self.STATUS_OK, bytes(data)

    def request(self, mode=PICC_REQA):
        self._write(self.BitFramingReg, 0x07)
        return self._transceive([mode], valid_bits=7)

    def _calculate_crc(self, data):
        self._write(self.CommandReg, self.PCD_IDLE)
        self._write(self.DivIrqReg, 0x04)
        self._write(self.FIFOLevelReg, 0x80)
        for b in data:
            self._write(self.FIFODataReg, b)
        self._write(self.CommandReg, self.PCD_CALC_CRC)
        start = ticks_ms()
        while ticks_diff(ticks_ms(), start) < 50:
            if self._read(self.DivIrqReg) & 0x04:
                return bytes([self._read(self.CRCResultLReg), self._read(self.CRCResultHReg)])
        return b"\x00\x00"

    def _halt(self):
        frame = bytes([self.PICC_HALT, 0x00])
        crc = self._calculate_crc(frame)
        self._transceive(frame + crc, timeout_ms=10)

    def anticoll_level(self, command):
        self._write(self.CollReg, 0x80)
        self._write(self.BitFramingReg, 0x00)
        status, data = self._transceive([command, 0x20])
        if status != self.STATUS_OK or len(data) < 5:
            return status, b"", 0

        block = data[:5]
        if (block[0] ^ block[1] ^ block[2] ^ block[3]) != block[4]:
            return self.STATUS_ERROR, b"", 0

        select_frame = bytearray([command, 0x70]) + block
        crc = self._calculate_crc(select_frame)
        status, sak = self._transceive(select_frame + crc)
        if status != self.STATUS_OK or len(sak) < 1:
            return self.STATUS_ERROR, b"", 0
        return self.STATUS_OK, block[:4], sak[0]

    def read_uid(self):
        status, _ = self.request(self.PICC_REQA)
        if status != self.STATUS_OK:
            status, _ = self.request(self.PICC_WUPA)
            if status != self.STATUS_OK:
                return None

        status, part1, _ = self.anticoll_level(self.PICC_ANTICOLL_CL1)
        if status != self.STATUS_OK:
            return None

        if part1[0] == 0x88:
            status, part2, _ = self.anticoll_level(self.PICC_ANTICOLL_CL2)
            if status != self.STATUS_OK:
                return None
            uid = bytes(part1[1:4] + part2)
        else:
            uid = bytes(part1)

        self._halt()
        return uid
