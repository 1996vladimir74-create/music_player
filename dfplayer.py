from time import sleep_ms, ticks_ms, ticks_diff


class DFPlayer:
    START = 0x7E
    VERSION = 0xFF
    LENGTH = 0x06
    END = 0xEF

    CMD_PLAY_FOLDER = 0x0F
    CMD_VOLUME = 0x06
    CMD_PAUSE = 0x0E
    CMD_RESUME = 0x0D
    CMD_STOP = 0x16
    CMD_SOURCE = 0x09
    CMD_FOLDER_COUNT = 0x4F
    CMD_FOLDER_FILES = 0x4E

    EVENT_FINISHED = 3

    def __init__(self, tx_uart, rx_uart):
        self.tx = tx_uart
        self.rx = rx_uart
        self.ready = False

    @staticmethod
    def _checksum(frame_without_checksum):
        total = sum(frame_without_checksum[1:]) & 0xFFFF
        return (-total) & 0xFFFF

    def _frame(self, command, parameter=0, ack=0):
        frame = bytearray([
            self.START, self.VERSION, self.LENGTH, command, ack,
            (parameter >> 8) & 0xFF, parameter & 0xFF, 0, 0, self.END
        ])
        checksum = self._checksum(frame[:7])
        frame[7] = (checksum >> 8) & 0xFF
        frame[8] = checksum & 0xFF
        return frame

    def send(self, command, parameter=0, ack=0):
        self.tx.write(self._frame(command, parameter, ack))
        sleep_ms(20)

    def begin(self):
        # DFPlayer Mini normally needs about 1.5-3 s to initialise its SD card.
        sleep_ms(1800)
        self.send(self.CMD_SOURCE, 2, 0)  # 2 = TF/microSD
        sleep_ms(200)
        self.ready = True

    def volume(self, level):
        self.send(self.CMD_VOLUME, max(0, min(30, int(level))))

    def play_folder(self, folder, track):
        folder = max(1, min(99, int(folder)))
        track = max(1, min(255, int(track)))
        parameter = (folder << 8) | track
        self.send(self.CMD_PLAY_FOLDER, parameter)

    def pause(self):
        self.send(self.CMD_PAUSE)

    def resume(self):
        self.send(self.CMD_RESUME)

    def stop(self):
        self.send(self.CMD_STOP)

    def _read_frame(self, timeout_ms=120):
        start = ticks_ms()
        while ticks_diff(ticks_ms(), start) < timeout_ms:
            if self.rx.any():
                data = self.rx.read()
                if not data:
                    continue
                for i in range(0, max(0, len(data) - 9)):
                    if data[i] == 0x7E and data[i + 9] == 0xEF:
                        return data[i:i + 10]
            sleep_ms(2)
        return None

    def _query(self, command, parameter=0):
        try:
            while self.rx.any():
                self.rx.read()
        except Exception:
            pass
        self.send(command, parameter, 1)
        frame = self._read_frame(250)
        if not frame or len(frame) != 10:
            return 0
        if frame[3] != command and frame[3] != 0x41:
            return 0
        return (frame[5] << 8) | frame[6]

    def files_in_folder(self, folder):
        return self._query(self.CMD_FOLDER_FILES, int(folder))

    def folder_count(self):
        return self._query(self.CMD_FOLDER_COUNT)

    def poll_event(self):
        try:
            if not self.rx.any():
                return 0
            data = self.rx.read()
            if not data:
                return 0
            for i in range(0, max(0, len(data) - 9)):
                if data[i] == 0x7E and data[i + 9] == 0xEF:
                    command = data[i + 3]
                    if command == 0x3D:
                        return self.EVENT_FINISHED
                    return command
        except Exception:
            return 0
        return 0

    def flush_rx(self):
        try:
            while self.rx.any():
                self.rx.read()
        except Exception:
            pass
