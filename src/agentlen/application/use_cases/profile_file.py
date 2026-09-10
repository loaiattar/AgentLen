from __future__ import annotations

from dataclasses import dataclass, replace

from agentlen.application.ports.file_reader import FileProfiler
from agentlen.domain.model.profile import FileProfile


@dataclass(frozen=True)
class ProfileFileCommand:
    file_id: int
    path: str
    sample_size: int = 500
    # Pass the format recorded at upload time (`file_upload.format`) whenever
    # it's known: storage is content-addressed, so `path` itself has no
    # extension for the profiler to infer a format from.
    format: str | None = None


class ProfileFile:
    """Profiles a source file before it is sent to the mapping agent.

    Thin wrapper around the `FileProfiler` port: it only stamps the real
    `file_id` onto the profile, since the port itself is source-agnostic.
    """

    def __init__(self, profiler: FileProfiler) -> None:
        self._profiler = profiler

    async def execute(self, command: ProfileFileCommand) -> FileProfile:
        profile = await self._profiler.profile(
            command.path, sample_size=command.sample_size, format=command.format
        )
        return replace(profile, file_id=command.file_id)
