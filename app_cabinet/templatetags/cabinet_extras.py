import os
import re
from django import template

register = template.Library()

@register.filter
def basename(value):
    """
    Returns the base name of a file path.
    Example: 'path/to/file.mp3' -> 'file.mp3'
    """
    if value:
        return os.path.basename(str(value))
    return value

@register.filter
def clean_filename(value):
    """
    Cleans up Django's auto-generated file names by removing hash suffixes.
    Example: 'video_abc123.mp4' -> 'video.mp4'
    """
    if value:
        filename = os.path.basename(str(value))
        # Remove Django's auto-generated suffix (underscore followed by random characters)
        # Pattern: filename_randomchars.extension -> filename.extension
        cleaned = re.sub(r'_[a-zA-Z0-9]{7,}(\.[^.]+)$', r'\1', filename)
        return cleaned
    return value 