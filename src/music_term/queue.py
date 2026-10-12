from dataclasses import dataclass, field
import random
@dataclass(frozen=True)
class Track:
    title: str
    artist: str
    source: str
    album_id: str | None = None
    is_album: bool = False
    artwork: str | None = None
    album_title: str | None = None

@dataclass
class Queue:
    tracks: list[Track] = field(default_factory=list)
    index: int = -1

    shuffle: bool = False
    repeat: str = "off"
    _order: list[int] = field(default_factory=list, repr=False)

    def _sync_order(self) -> None:
        if len(self._order) != len(self.tracks):
            self._order = list(range(len(self.tracks)))
            if self.shuffle:
                random.shuffle(self._order)
                if self.index >= 0 and self.index in self._order:
                    self._order.remove(self.index)
                    self._order.insert(0, self.index)

    def set_shuffle(self, enabled: bool) -> None:
        self.shuffle = enabled
        self._order = []
        self._sync_order()

    def cycle_repeat(self) -> None:
        modes = ("off", "one", "all")
        self.repeat = modes[(modes.index(self.repeat) + 1) % 3]

    def add(self, track: Track) -> None:
        self.tracks.append(track)
        # Rebuild only the unplayed tail so adding songs doesn't reset progress.
        if self._order and len(self._order) == len(self.tracks) - 1:
            position = self._order.index(self.index) + 1 if self.index in self._order else 0
            insert = random.randrange(position, len(self._order) + 1) if self.shuffle else len(self._order)
            self._order.insert(insert, len(self.tracks) - 1)

    def remove(self, index: int) -> Track | None:
        if not 0 <= index < len(self.tracks):
            return None
        self._sync_order()
        removed = self.tracks.pop(index)
        self._order = [item - 1 if item > index else item for item in self._order if item != index]
        if self.index > index:
            self.index -= 1
        elif self.index == index:
            self.index = min(index, len(self.tracks) - 1)
        return removed

    def clear(self) -> None:
        self.tracks.clear()
        self.index = -1
        self._order.clear()

    def select(self, index: int) -> Track | None:
        if 0 <= index < len(self.tracks):
            self.index = index
            return self.tracks[index]
        return None

    def next(self, automatic: bool = False) -> Track | None:
        if not self.tracks:
            return None
        if automatic and self.repeat == "one" and self.index >= 0:
            return self.select(self.index)
        self._sync_order()
        position = self._order.index(self.index) + 1 if self.index in self._order else 0
        if position >= len(self._order):
            if self.repeat != "all":
                return None
            if self.shuffle and len(self._order) > 1:
                last = self.index
                random.shuffle(self._order)
                if self._order[0] == last:
                    self._order[0], self._order[1] = self._order[1], self._order[0]
            position = 0
        return self.select(self._order[position])

    def previous(self) -> Track | None:
        if not self.tracks:
            return None
        self._sync_order()
        position = self._order.index(self.index) if self.index in self._order else 0
        if position == 0 and self.repeat == "all":
            position = len(self._order)
        return self.select(self._order[max(0, position - 1)])
