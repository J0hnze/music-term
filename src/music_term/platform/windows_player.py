"""Native Windows mpv playback over asynchronous named-pipe IPC."""
import asyncio
import uuid
from .mpv_player import Player as MpvPlayer, dependencies


class Player(MpvPlayer):
    def prepare_endpoint(self) -> str:
        self.pipe_name = '\\\\.\\pipe\\music-term-' + uuid.uuid4().hex
        return self.pipe_name

    def audio_options(self) -> list[str]:
        return ['--ao=wasapi']

    async def connect(self) -> None:
        loop = asyncio.get_running_loop()
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        transport, _ = await loop.create_pipe_connection(lambda: protocol, self.pipe_name)
        self.reader = reader
        self.writer = asyncio.StreamWriter(transport, protocol, reader, loop)
