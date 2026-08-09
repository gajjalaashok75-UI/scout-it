"""Command modules for scout-it CLI."""

from .image import image_search
from .url import fetch_url, fatchurl
from .video import video_search, video_extract
from .web import multi_search
from .wikipedia import wikipedia_search

__all__ = [
    "image_search",
    "fetch_url",
    "fatchurl",
    "video_search",
    "video_extract",
    "multi_search",
    "wikipedia_search",
]
