import os
import tempfile
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def atomic_text(path: Path, *, encoding: str = "utf-8", newline: str | None = None):
    """Replace a text file only after a complete, flushed write in the same directory."""
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding=encoding,
            newline=newline,
            dir=path.parent,
            prefix="." + path.name + ".",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            yield stream
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
