from datetime import datetime

from PIL import Image, ImageGrab


def read_clipboard_image():
    data = ImageGrab.grabclipboard()
    if isinstance(data, Image.Image):
        return data
    return None


def new_clipboard_filename():
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    return f"tmp_{timestamp}.png"
