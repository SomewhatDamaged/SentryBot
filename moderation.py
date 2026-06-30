class Moderated:
    _muted: bool = False
    _kicked: bool = False
    _banned: bool = False
    _deleted: bool = False

    @property
    def muted(self):
        return self._muted
    @muted.setter
    def muted(self, _ = None):
        self._muted = True

    @property
    def kicked(self):
        return self._kicked
    @kicked.setter
    def kicked(self, _ = None):
        self._kicked = True

    @property
    def banned(self):
        return self._banned
    @banned.setter
    def banned(self, _ = None):
        self._banned = True

    @property
    def deleted(self):
        return self._deleted
    @deleted.setter
    def deleted(self, _ = None):
        self._deleted = True

    @property
    def moderated(self):
        return self._muted or self._kicked or self._banned or self._deleted