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

    EVENT_NONE = 0
    EVENT_FINISHED = 3      # frame 0x3D: track finished (TF card)
    EVENT_ERROR = 4         # frame 0x40: module error, parameter = error code

    # Error codes (parameter of frame 0x40) meaning "file/index not found".
    ERR_NOT_FOUND = (0x05, 0x06)

    def __init__(self, uart):
        self.uart = uart
        self.ready = False
        self.sd_ok = True        # updated from frames 0x3F / 0x3A / 0x3B
        self.check_sd = True
        self.online_seen = False
        self.log = None          # optional callback(frame_bytes)
        self._rx = bytearray()

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
        self.uart.write(self._frame(command, parameter, ack))
        sleep_ms(20)

    # ---- receiving -------------------------------------------------------

    def _note(self, f):
        # Track card state from the module's own notifications.
        cmd = f[3]
        param = (f[5] << 8) | f[6]
        if cmd == 0x3F:                      # initialisation complete
            self.online_seen = True
            if self.check_sd:
                self.sd_ok = bool(param & 0x02)
        elif cmd == 0x3A and (param & 0xFF) == 2:   # TF card inserted
            if self.check_sd:
                self.sd_ok = True
        elif cmd == 0x3B and (param & 0xFF) == 2:   # TF card removed
            if self.check_sd:
                self.sd_ok = False

    def _pump(self):
        """Read the UART, return the list of complete 10-byte frames."""
        try:
            if self.uart.any():
                data = self.uart.read()
                if data:
                    self._rx.extend(data)
                    if len(self._rx) > 64:
                        del self._rx[:-64]
        except Exception:
            pass
        frames = []
        while len(self._rx) >= 10:
            if self._rx[0] == self.START and self._rx[9] == self.END:
                f = bytes(self._rx[:10])
                del self._rx[:10]
                self._note(f)
                if self.log:
                    try:
                        self.log(f)
                    except Exception:
                        pass
                frames.append(f)
            else:
                del self._rx[0]
        return frames

    def flush_rx(self):
        self._pump()
        self._rx = bytearray()

    def _query(self, command, parameter=0, timeout_ms=300):
        """Return the answer value, or -1 if the module did not answer."""
        self.flush_rx()
        self.send(command, parameter, 0)
        start = ticks_ms()
        while ticks_diff(ticks_ms(), start) < timeout_ms:
            for f in self._pump():
                if f[3] == command:
                    return (f[5] << 8) | f[6]
                if f[3] == 0x40:
                    return -1
            sleep_ms(5)
        return -1

    def files_in_folder(self, folder):
        """Files in folder: >=0 answer (0 = empty/missing), -1 = no answer."""
        return self._query(self.CMD_FOLDER_FILES, int(folder))

    def folder_count(self):
        return self._query(self.CMD_FOLDER_COUNT)

    def probe(self):
        """True if the module answers a query (a card is readable)."""
        if self._query(self.CMD_FOLDER_COUNT) >= 0:
            return True
        return self._query(self.CMD_FOLDER_FILES, 1) >= 0

    def poll_events(self):
        """Return a list of (event, parameter) for finished/error frames."""
        events = []
        for f in self._pump():
            if f[3] == 0x3D:
                events.append((self.EVENT_FINISHED, f[6]))
            elif f[3] == 0x40:
                events.append((self.EVENT_ERROR, f[6]))
        return events

    # ---- commands --------------------------------------------------------

    def begin(self, source=2, init_timeout_ms=3000, check_sd=True):
        self.check_sd = check_sd
        self.online_seen = False
        self.sd_ok = True
        # The module announces itself (frame 0x3F) when its card is ready.
        # The frame may have been sent before our UART existed, so a timeout
        # is not an error: fall back to probing the module with a query.
        start = ticks_ms()
        while ticks_diff(ticks_ms(), start) < init_timeout_ms:
            self._pump()
            if self.online_seen:
                break
            sleep_ms(20)
        sleep_ms(200)
        self.send(self.CMD_SOURCE, source, 0)
        sleep_ms(200)
        self._pump()
        if not check_sd:
            self.sd_ok = True
        elif not self.online_seen:
            self.sd_ok = self.probe()
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
