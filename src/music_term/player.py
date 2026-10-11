"""Asynchronous, request-correlated mpv JSON IPC on a private Unix socket."""
import asyncio
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any

def dependencies() -> list[str]:
    return [name for name in ("mpv", "ffmpeg") if shutil.which(name) is None]

class Player:
    def __init__(self) -> None:
        self.process: asyncio.subprocess.Process | None = None
        self.directory: str | None = None
        self.socket: Path | None = None
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None
        self.pending: dict[int, asyncio.Future] = {}
        self.counter = 0
        self.task: asyncio.Task | None = None
        self.events: asyncio.Queue = asyncio.Queue()

    async def start(self) -> None:
        if not shutil.which("mpv"):
            raise RuntimeError("mpv is missing. Install: sudo apt install mpv ffmpeg")
        self.directory = tempfile.mkdtemp(prefix="music-term-")
        os.chmod(self.directory, 0o700)
        self.socket = Path(self.directory) / "ipc.sock"
        self.process = await asyncio.create_subprocess_exec(
            "mpv", "--no-config", "--idle=yes", "--no-video", "--ytdl=no",
            "--volume=70", "--volume-max=100", f"--input-ipc-server={self.socket}",
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        for _ in range(100):
            if self.process.returncode is not None:
                raise RuntimeError("mpv exited during startup. Check your mpv installation.")
            try:
                self.reader, self.writer = await asyncio.open_unix_connection(str(self.socket))
                self.socket.chmod(0o600)
                self.task = asyncio.create_task(self._read())
                return
            except (FileNotFoundError, ConnectionRefusedError):
                await asyncio.sleep(0.05)
        raise RuntimeError("mpv IPC startup timed out.")

    async def _read(self) -> None:
        try:
            while line := await self.reader.readline():
                message = json.loads(line)
                future = self.pending.get(message.get("request_id"))
                if future and not future.done():
                    future.set_result(message)
                elif "event" in message:
                    await self.events.put(message)
        finally:
            for future in self.pending.values():
                if not future.done():
                    future.set_exception(RuntimeError("mpv disconnected; restart music-term."))

    async def command(self, *args: Any) -> Any:
        if not self.writer:
            raise RuntimeError("mpv is unavailable. Install mpv and restart music-term.")
        self.counter += 1
        request = self.counter
        future = asyncio.get_running_loop().create_future()
        self.pending[request] = future
        try:
            self.writer.write((json.dumps({"command": list(args), "request_id": request}) + "\n").encode())
            await self.writer.drain()
            result = await asyncio.wait_for(future, 5)
            if result.get("error") != "success":
                raise RuntimeError("mpv rejected the command. Check audio output or FFmpeg filter support.")
            return result.get("data")
        except (TimeoutError, ConnectionError, OSError):
            raise RuntimeError("mpv IPC timed out or disconnected. Restart music-term and check mpv/audio output.") from None
        finally:
            self.pending.pop(request, None)

    async def load(self, source: str, headers: dict[str, str]) -> None:
        await self.command("set_property", "http-header-fields", [f"{k}: {v}" for k, v in headers.items()])
        await self.command("loadfile", source, "replace")
        await self.command("set_property", "pause", False)

    async def close(self) -> None:
        if self.writer:
            self.writer.close()
            try:
                await self.writer.wait_closed()
            except (ConnectionError, BrokenPipeError):
                pass
            self.writer = None
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
        if self.process and self.process.returncode is None:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), 3)
            except asyncio.TimeoutError:
                self.process.kill()
                await self.process.wait()
        if self.directory:
            shutil.rmtree(self.directory, ignore_errors=True)
            self.directory = None
