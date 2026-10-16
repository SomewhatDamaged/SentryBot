
class Moderated:
    _muted: bool = False
    _kicked: bool = False
    _banned: bool = False
    _deleted: bool = False
    _source: str = ""
    source_data: dict = {}
    _muted_err: bool = False

    @property
    def source(self):
        return self._source
    @source.setter
    def source(self, data: tuple[dict, str]):
        self._source = data[1]
        if isinstance(data[0], dict):
            self.source_data = data[0]

    @property
    def muted_err(self):
        return self._muted_err
    @muted_err.setter
    def muted_err(self, _ = None):
        self._muted_err = True

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