import jinja2
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4

_js_escapes = {
        '\\': '\\u005C',
        '\'': '\\u0027',
        '"': '\\u0022',
        '>': '\\u003E',
        '<': '\\u003C',
        '&': '\\u0026',
        '=': '\\u003D',
        '-': '\\u002D',
        ';': '\\u003B',
        u'\u2028': '\\u2028',
        u'\u2029': '\\u2029'
}
# Escape every ASCII character with a value less than 32.
_js_escapes.update(('%c' % z, '\\u%04X' % z) for z in range(32))

def jinja2_escapejs_filter(value):
        retval = [_js_escapes.get(letter, letter) for letter in value]
        return jinja2.utils.markupsafe.Markup("".join(retval))


def get_recording_duration_in_seconds(file_path):
    if file_path.lower().endswith('.mp3'):
        audio = MP3(file_path)
        return audio.info.length  # Duration in seconds
    elif file_path.lower().endswith('.m4a'):
        audio = MP4(file_path)
        return audio.info.length  # Duration in seconds
    else:
        raise ValueError("Unsupported file type. Only MP3 and M4A files are supported.")

def format_duration(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    if hours > 0:
        return f"{hours}h {minutes}m"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    else:
        return f"{secs}s"

def ellide(text, max_length):
    if len(text) > max_length:
        return text[:max_length] + "..."
    else:
        return text
