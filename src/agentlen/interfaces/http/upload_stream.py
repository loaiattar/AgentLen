"""Read the file part of a `multipart/form-data` upload as it arrives.

FastAPI hands an `UploadFile` to a route only once Starlette has spooled the
whole request body to a temporary file. A size limit checked afterwards is
checked too late: a 20 GB upload is written to disk in full before it is
refused. Parsing the body here instead passes the storage the bytes as they
come off the connection, so it can stop reading the moment the limit is crossed.
"""

from __future__ import annotations

from collections import deque
from collections.abc import AsyncIterator

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from python_multipart.exceptions import MultipartParseError
from python_multipart.multipart import MultipartParser, parse_options_header

from agentlen.application.ports.file_storage import FileTooLargeError

#: What a request may carry beyond the file itself: the boundaries and the
#: part headers, filename included. Generous, since it only bounds an abuse.
MULTIPART_OVERHEAD_BYTES = 64 * 1024


def _malformed(message: str, field_name: str) -> RequestValidationError:
    # Same error FastAPI raised for a missing `UploadFile` parameter: 400.
    return RequestValidationError(
        [{"type": "value_error", "loc": ("body", field_name), "msg": message, "input": None}]
    )


def _too_large(max_bytes: int) -> FileTooLargeError:
    return FileTooLargeError(f"Fichier trop volumineux : limite {max_bytes // (1024 * 1024)} Mo.")


class _FilePart:
    """Parser callbacks keeping the first file part named `field_name`."""

    def __init__(self, field_name: str) -> None:
        self._field_name = field_name.encode()
        self._header_name = b""
        self._header_value = b""
        self._disposition = b""
        self._in_file = False
        self.filename: str | None = None
        self.data: deque[bytes] = deque()
        self.done = False

    def on_part_begin(self) -> None:
        self._disposition = b""
        self._in_file = False

    def on_header_field(self, data: bytes, start: int, end: int) -> None:
        self._header_name += data[start:end]

    def on_header_value(self, data: bytes, start: int, end: int) -> None:
        self._header_value += data[start:end]

    def on_header_end(self) -> None:
        if self._header_name.lower() == b"content-disposition":
            self._disposition = self._header_value
        self._header_name = self._header_value = b""

    def on_headers_finished(self) -> None:
        _, options = parse_options_header(self._disposition)
        if (
            self.filename is None
            and options.get(b"name") == self._field_name
            and b"filename" in options
        ):
            raw = options[b"filename"]
            try:
                self.filename = raw.decode("utf-8")
            except UnicodeDecodeError:
                self.filename = raw.decode("latin-1")
            self._in_file = True

    def on_part_data(self, data: bytes, start: int, end: int) -> None:
        # Other fields are skipped, not buffered: nothing but the file is kept.
        if self._in_file:
            self.data.append(data[start:end])

    def on_part_end(self) -> None:
        if self._in_file:
            self._in_file = False
            self.done = True


async def read_file_part(
    request: Request, *, max_bytes: int, field_name: str = "file"
) -> tuple[str, AsyncIterator[bytes]]:
    """Return the uploaded file's name and a stream of its bytes.

    Only the body up to the start of the file is read here; the bytes then
    arrive as the stream is consumed. Raises `FileTooLargeError` before reading
    anything when `Content-Length` already exceeds the limit, and while reading
    when a body without one does.
    """
    body_limit = max_bytes + MULTIPART_OVERHEAD_BYTES
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > body_limit:
        raise _too_large(max_bytes)

    content_type, params = parse_options_header(request.headers.get("content-type"))
    boundary = params.get(b"boundary")
    if content_type.lower() != b"multipart/form-data" or not boundary:
        raise _malformed("Envoi attendu en multipart/form-data.", field_name)

    part = _FilePart(field_name)
    parser = MultipartParser(
        boundary,
        {
            "on_part_begin": part.on_part_begin,
            "on_header_field": part.on_header_field,
            "on_header_value": part.on_header_value,
            "on_header_end": part.on_header_end,
            "on_headers_finished": part.on_headers_finished,
            "on_part_data": part.on_part_data,
            "on_part_end": part.on_part_end,
        },
    )
    body = request.stream()
    received = 0

    async def feed() -> bool:
        """Parse the next chunk of the body; False once the body is exhausted."""
        nonlocal received
        try:
            chunk = await anext(body)
        except StopAsyncIteration:
            return False
        received += len(chunk)
        # Without Content-Length, fields around the file could still be
        # arbitrarily large: the body as a whole is bounded too.
        if received > body_limit:
            raise _too_large(max_bytes)
        try:
            parser.write(chunk)
        except MultipartParseError:
            raise _malformed("Corps multipart invalide.", field_name) from None
        return True

    while part.filename is None:
        if not await feed():
            raise _malformed(f"Champ '{field_name}' manquant.", field_name)

    async def file_bytes() -> AsyncIterator[bytes]:
        while True:
            while part.data:
                yield part.data.popleft()
            if part.done:
                return
            if not await feed():
                raise _malformed("Corps multipart tronqué avant la fin du fichier.", field_name)

    return part.filename, file_bytes()
