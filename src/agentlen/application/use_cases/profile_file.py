from __future__ import annotations

from dataclasses import dataclass, replace

from agentlen.application.ports.file_reader import FileProfiler
from agentlen.domain.model.profile import FileProfile


@dataclass(frozen=True)
class ProfileFileCommand:
    file_id: int
    path: str
    sample_size: int = 500


class ProfileFile:
    """Profiles a source file before it is sent to the mapping agent.

    Thin wrapper around the `FileProfiler` port: it only stamps the real
    `file_id` onto the profile, since the port itself is source-agnostic.
    """

    def __init__(self, profiler: FileProfiler) -> None:
        self._profiler = profiler

    async def execute(self, command: ProfileFileCommand) -> FileProfile:
        profile = await self._profiler.profile(command.path, sample_size=command.sample_size)
        return replace(profile, file_id=command.file_id)
