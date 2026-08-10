"""Image Search RSS Feed Registry.

RSS feed URLs for image-search category providers. Mirrors the structure of
``news_search_feed.py`` / ``web_search_feed.py`` but focuses on image-hosting
sources that publish Media RSS (MRSS) or RSS-with-enclosure feeds.

Verified sources:
- Flickr public photos feed (``photos_public.gne``) supports per-tag and
  per-user feeds and returns full Media RSS with thumbnails + image URLs.
- NASA Image of the Day publishes a standard RSS feed with media enclosures.

Flickr tag feeds are generated dynamically per category via
``flickr_tag_feed(tag)`` so every category maps to a live Flickr photo stream.
"""

from typing import Any, Dict, List

__all__ = [
    "IMAGE_SEARCH_FEEDS",
    "FLICKR_TAG_FEED",
    "flickr_tag_feed",
    "flickr_user_feed",
    "youtube_thumbnail_feed",
]


def flickr_tag_feed(tag: str) -> str:
    """Flickr public-photos RSS feed for a single tag."""
    return f"https://www.flickr.com/services/feeds/photos_public.gne?tags={tag}&format=rss_200"


def flickr_user_feed(user_id: str) -> str:
    """Flickr public-photos RSS feed for a user NSID."""
    return f"https://www.flickr.com/services/feeds/photos_public.gne?id={user_id}&format=rss_200"


def youtube_thumbnail_feed(channel_id: str) -> str:
    """YouTube channel video feed (used by image search for thumbnails)."""
    return f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"


# Sentinel marker so providers know to expand a Flickr tag feed from the
# category name at fetch time.
FLICKR_TAG_FEED = "__flickr_tag__"

# Curated Flickr user/group feeds that consistently surface high-quality,
# freely-licensed imagery (NASA, institutional Commons accounts).
_FLICKR_FEATURED_USERS = [
    {"url": flickr_user_feed("24662369@N07"), "notes": "NASA Goddard photo stream."},
    {"url": flickr_user_feed("35067687@N04"), "notes": "Library of Congress photo stream."},
    {"url": flickr_user_feed("12403504@N02"), "notes": "Smithsonian Institution photo stream."},
]


IMAGE_SEARCH_FEEDS: Dict[str, List[Dict[str, Any]]] = {
    "nature": [
        {"url": flickr_tag_feed("nature"), "notes": "Flickr public photos tagged 'nature'."},
        {"url": flickr_tag_feed("landscape"), "notes": "Flickr public photos tagged 'landscape'."},
        {"url": flickr_tag_feed("wildlife"), "notes": "Flickr public photos tagged 'wildlife'."},
    ],
    "space": [
        {"url": "https://www.nasa.gov/feed/", "notes": "NASA Image of the Day."},
        {"url": flickr_tag_feed("space"), "notes": "Flickr public photos tagged 'space'."},
        {"url": flickr_tag_feed("astronomy"), "notes": "Flickr public photos tagged 'astronomy'."},
        {"url": flickr_user_feed("24662369@N07"), "notes": "NASA Goddard photo stream."},
    ],
    "architecture": [
        {"url": flickr_tag_feed("architecture"), "notes": "Flickr public photos tagged 'architecture'."},
        {"url": flickr_tag_feed("building"), "notes": "Flickr public photos tagged 'building'."},
        {"url": flickr_tag_feed("urban"), "notes": "Flickr public photos tagged 'urban'."},
    ],
    "travel": [
        {"url": flickr_tag_feed("travel"), "notes": "Flickr public photos tagged 'travel'."},
        {"url": flickr_tag_feed("city"), "notes": "Flickr public photos tagged 'city'."},
        {"url": flickr_tag_feed("street"), "notes": "Flickr public photos tagged 'street photography'."},
    ],
    "food": [
        {"url": flickr_tag_feed("food"), "notes": "Flickr public photos tagged 'food'."},
        {"url": flickr_tag_feed("cuisine"), "notes": "Flickr public photos tagged 'cuisine'."},
    ],
    "people": [
        {"url": flickr_tag_feed("portrait"), "notes": "Flickr public photos tagged 'portrait'."},
        {"url": flickr_tag_feed("people"), "notes": "Flickr public photos tagged 'people'."},
    ],
    "animals": [
        {"url": flickr_tag_feed("animals"), "notes": "Flickr public photos tagged 'animals'."},
        {"url": flickr_tag_feed("pets"), "notes": "Flickr public photos tagged 'pets'."},
        {"url": flickr_tag_feed("cats"), "notes": "Flickr public photos tagged 'cats'."},
        {"url": flickr_tag_feed("dogs"), "notes": "Flickr public photos tagged 'dogs'."},
    ],
    "cars": [
        {"url": flickr_tag_feed("cars"), "notes": "Flickr public photos tagged 'cars'."},
        {"url": flickr_tag_feed("automobile"), "notes": "Flickr public photos tagged 'automobile'."},
        {"url": flickr_tag_feed("motorcycle"), "notes": "Flickr public photos tagged 'motorcycle'."},
    ],
    "art": [
        {"url": flickr_tag_feed("art"), "notes": "Flickr public photos tagged 'art'."},
        {"url": flickr_tag_feed("painting"), "notes": "Flickr public photos tagged 'painting'."},
        {"url": flickr_tag_feed("illustration"), "notes": "Flickr public photos tagged 'illustration'."},
    ],
    "technology": [
        {"url": flickr_tag_feed("technology"), "notes": "Flickr public photos tagged 'technology'."},
        {"url": flickr_tag_feed("computer"), "notes": "Flickr public photos tagged 'computer'."},
        {"url": flickr_tag_feed("gadgets"), "notes": "Flickr public photos tagged 'gadgets'."},
    ],
    "sports": [
        {"url": flickr_tag_feed("sports"), "notes": "Flickr public photos tagged 'sports'."},
        {"url": flickr_tag_feed("football"), "notes": "Flickr public photos tagged 'football'."},
        {"url": flickr_tag_feed("basketball"), "notes": "Flickr public photos tagged 'basketball'."},
    ],
    "music": [
        {"url": flickr_tag_feed("music"), "notes": "Flickr public photos tagged 'music'."},
        {"url": flickr_tag_feed("concert"), "notes": "Flickr public photos tagged 'concert'."},
    ],
    "fashion": [
        {"url": flickr_tag_feed("fashion"), "notes": "Flickr public photos tagged 'fashion'."},
        {"url": flickr_tag_feed("style"), "notes": "Flickr public photos tagged 'style'."},
    ],
    "flowers": [
        {"url": flickr_tag_feed("flowers"), "notes": "Flickr public photos tagged 'flowers'."},
        {"url": flickr_tag_feed("garden"), "notes": "Flickr public photos tagged 'garden'."},
    ],
    "wallpaper": [
        {"url": flickr_tag_feed("wallpaper"), "notes": "Flickr public photos tagged 'wallpaper'."},
        {"url": flickr_tag_feed("abstract"), "notes": "Flickr public photos tagged 'abstract'."},
    ],
    "science": [
        {"url": "https://www.nasa.gov/feed/", "notes": "NASA Image of the Day."},
        {"url": flickr_tag_feed("science"), "notes": "Flickr public photos tagged 'science'."},
        {"url": flickr_tag_feed("microscope"), "notes": "Flickr public photos tagged 'microscope'."},
    ],
    "news": [
        {"url": "https://www.nasa.gov/feed/", "notes": "NASA Image of the Day."},
        *_FLICKR_FEATURED_USERS,
    ],
    "featured": [*_FLICKR_FEATURED_USERS],
}
