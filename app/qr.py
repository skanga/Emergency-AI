"""Small, offline terminal QR codes for the LAN connection URL."""
import os

from .vendor.qrcodegen import QrCode


def terminal_qr(text, color=False):
    qr = QrCode.encode_text(text, QrCode.Ecc.LOW)
    size = qr.get_size()
    # Four light modules on every side are the scanner's quiet zone.
    # Each terminal cell holds two vertical modules, preserving square geometry.
    rows = []
    for y in range(-4, size + 4, 2):
        row = ''.join((' ', '\u2584', '\u2580', '\u2588')[
            2 * int(qr.get_module(x, y)) + int(qr.get_module(x, y + 1))]
            for x in range(-4, size + 4))
        rows.append(('\x1b[30;47m' + row + '\x1b[0m') if color else row)
    return '\n'.join(rows)


def terminal_colors(stream):
    if not stream.isatty() or os.environ.get('TERM') == 'dumb':
        return False
    if os.name != 'nt':
        return True
    # Windows consoles need VT processing to honor explicit black-on-white colors.
    try:
        import ctypes
        import msvcrt
        handle = msvcrt.get_osfhandle(stream.fileno())
        mode = ctypes.c_ulong()
        kernel = ctypes.windll.kernel32
        if not kernel.GetConsoleMode(ctypes.c_void_p(handle), ctypes.byref(mode)):
            return False
        return bool(kernel.SetConsoleMode(ctypes.c_void_p(handle), mode.value | 4))
    except (AttributeError, OSError, ValueError):
        return False
