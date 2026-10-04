"""Export the app's vector-drawn train symbol as a multi-resolution Windows icon."""
from pathlib import Path
import struct

from PyQt6.QtCore import QBuffer, QIODevice
from PyQt6.QtWidgets import QApplication

from ktx_app import app_icon


def main():
    app = QApplication([])
    sizes = (16, 24, 32, 48, 64, 128, 256)
    entries, images = [], []
    offset = 6 + 16 * len(sizes)
    for size in sizes:
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        # Native ICO bitmap payloads also work with Windows shell icon extractors
        # that do not handle PNG payloads consistently at small resolutions.
        if not app_icon(size).pixmap(size, size).save(buffer, "ICO"):
            raise RuntimeError("Could not render application icon")
        single_icon = bytes(buffer.data())
        entry = struct.unpack("<BBBBHHII", single_icon[6:22])
        data = single_icon[entry[7]:entry[7] + entry[6]]
        entries.append(struct.pack("<BBBBHHII", size % 256, size % 256,
                                   0, 0, 1, 32, len(data), offset))
        images.append(data)
        offset += len(data)
    target = Path(__file__).resolve().parent / "build" / "KTXSeatWatch.ico"
    target.parent.mkdir(exist_ok=True)
    target.write_bytes(struct.pack("<HHH", 0, 1, len(sizes))
                       + b"".join(entries) + b"".join(images))


if __name__ == "__main__":
    main()
