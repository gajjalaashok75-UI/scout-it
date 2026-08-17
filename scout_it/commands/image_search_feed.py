"""Image Search RSS Feed Registry.

RSS feed URLs for image-search category providers. Mirrors the structure of
``news_search_feed.py`` / ``web_search_feed.py`` but focuses on image-hosting
sources that publish Media RSS (MRSS) or RSS-with-enclosure feeds.

Verified sources:
- Flickr public photos feed (``photos_public.gne``) supports per-tag and
  per-user feeds and returns full Media RSS with thumbnails + image URLs.
- NASA Image of the Day publishes a standard RSS feed with media enclosures.
- DeviantArt backend RSS (``backend.deviantart.com/rss.xml``) supports a
  ``q=<tag>`` query parameter that returns Media RSS with image thumbnails for
  any tag/category/topic on deviantart.com. The tag set is large (gallery,
  animegirls, swords, dnd, elves, photography, fantasy, cosplay, comics, etc.)
  and covers the full range of DeviantArt's browse topics.

Flickr tag feeds are generated dynamically per category via
``flickr_tag_feed(tag)`` so every category maps to a live Flickr photo stream.
DeviantArt tag feeds are generated dynamically via ``deviantart_feed(tag)``.
``deviantart_query_feeds(query)`` selects the best DeviantArt tag feeds for an
arbitrary search query using the keyword map below.
"""

from typing import Any, Dict, List
from urllib.parse import quote_plus

__all__ = [
    "IMAGE_SEARCH_FEEDS",
    "FLICKR_TAG_FEED",
    "flickr_tag_feed",
    "flickr_user_feed",
    "youtube_thumbnail_feed",
    "deviantart_feed",
    "deviantart_query_feeds",
    "DEVIANTART_KEYWORD_MAP",
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


def deviantart_feed(tag: str) -> str:
    """DeviantArt backend RSS feed for a tag/category/topic.

    The ``q`` parameter accepts any DeviantArt tag, category, or topic name
    (e.g. ``gallery``, ``animegirls``, ``fategrandorder``, ``swords``, ``dnd``,
    ``elves``). Returns Media RSS with image thumbnails.
    """
    return f"https://backend.deviantart.com/rss.xml?q={quote_plus(tag)}&type=deviation"


# ---------------------------------------------------------------------------
# DeviantArt keyword -> tag map
#
# Keys are lowercased keywords/phrases that may appear in a search query. Values
# are the DeviantArt tags whose feeds should be fetched when the keyword is
# present. This lets ``deviantart_query_feeds(query)`` pick the right feeds
# automatically based on the user's search terms.
#
# The tag set below mirrors DeviantArt's browse topics/categories and the user-
# supplied list (gallery, animegirls, fategrandorder, swords, dnd, elves, etc.).
# ---------------------------------------------------------------------------
DEVIANTART_KEYWORD_MAP: Dict[str, List[str]] = {
    # broad / general
    "gallery": ["gallery"],
    "art": ["digitalart", "traditional", "painting"],
    "digital art": ["digitalart"],
    "digital": ["digitalart"],
    "digitalart": ["digitalart"],
    "painting": ["painting", "traditional"],
    "drawing": ["drawing", "traditional"],
    "drawings": ["drawing", "traditional"],
    "illustration": ["illustration"],
    "concept art": ["conceptart", "characterdesign"],
    "concept": ["conceptart"],
    "character design": ["characterdesign"],
    "original character": ["originalcharacter", "characterdesign"],
    "oc": ["originalcharacter"],
    "portrait": ["portraits"],
    "portraits": ["portraits"],
    "abstract": ["abstract", "abstractart"],
    "neon": ["neon"],
    "graphic design": ["graphicdesign"],
    "procreate": ["procreate"],
    "ipad art": ["ipadart"],
    "ipad": ["ipadart"],
    "firealpaca": ["firealpaca"],
    "3d art": ["3d"],
    "3d": ["3d"],
    "science fiction": ["scifi"],
    "scifi": ["scifi"],
    "sci-fi": ["scifi"],
    "superheroes": ["superheroes"],
    "superhero": ["superheroes"],
    "comics": ["comics"],
    "comic": ["comics"],
    "game art": ["gameart"],
    "video game": ["videogamefanart", "gameart"],
    "videogame": ["videogamefanart", "gameart"],

    # fantasy / anime / manga
    "fantasy": ["fantasy", "magicrealms"],
    "fantasy art": ["fantasy"],
    "magic": ["magicrealms", "magicalgirls"],
    "magic realms": ["magicrealms"],
    "magical girl": ["magicalgirls"],
    "magical girls": ["magicalgirls"],
    "anime": ["anime", "animemanga"],
    "anime and manga": ["animemanga"],
    "manga": ["manga", "animemanga"],
    "animegirls": ["animegirls", "anime"],
    "anime girls": ["animegirls", "anime"],
    "cute": ["cute", "kawaii"],
    "kawaii": ["kawaii"],
    "cute and kawaii": ["cute", "kawaii"],
    "disney": ["disney"],
    "netflix": ["netflix"],
    "witches": ["witches"],
    "witch": ["witches"],
    "creatures": ["creatures"],
    "creature": ["creatures"],
    "space": ["space", "skyscapes"],
    "skyscapes": ["skyscapes"],
    "skyscape": ["skyscapes"],

    # specific franchises / themes (user-supplied)
    "fategrandorder": ["fategrandorder"],
    "fate grand order": ["fategrandorder"],
    "fgo": ["fategrandorder"],
    "dnd": ["dnd", "rpg"],
    "dungeons and dragons": ["dnd", "rpg"],
    "dungeons": ["dnd", "rpg"],
    "dragons": ["dnd", "fantasy"],
    "dragon": ["dnd", "fantasy"],
    "elves": ["elves"],
    "elf": ["elves"],
    "elves (elf)": ["elves"],
    "swords": ["swords"],
    "sword": ["swords"],
    "fighters": ["fighters"],
    "fighter": ["fighters"],
    "assassins": ["assassins"],
    "assassin": ["assassins"],
    "rpg": ["rpg", "dnd"],
    "character concept": ["characterconcept", "conceptart"],
    "fantasy characters": ["fantasycharacters", "fantasy"],
    "reference sheet": ["referencesheet"],
    "warrior cats": ["warriorcats"],
    "warrior": ["warriorcats", "fighters"],
    "scp": ["scpfoundation"],
    "scp foundation": ["scpfoundation"],

    # adoptables / fursona / closed species
    "adoptables": ["adoptables"],
    "adoptable": ["adoptables"],
    "adoptable auctions": ["adoptableauctions"],
    "open adoptables": ["adoptables"],
    "closed species": ["closedspecies"],
    "fursona": ["fursona"],

    # photography
    "photography": ["photography"],
    "photo": ["photography"],
    "nature photography": ["naturephotography", "photography"],
    "nature": ["naturephotography", "photography"],
    "cosplay": ["cosplay"],
    "fan art": ["fanart"],
    "fanart": ["fanart"],
    "fan": ["fanart"],
}


def deviantart_query_feeds(query: str) -> List[str]:
    """Select DeviantArt RSS feed URLs that match keywords in *query*.

    Scans the query for known DeviantArt keywords/phrases and returns the
    corresponding tag feed URLs (deduplicated, order-preserved). Falls back to
    a single ``q=<query>`` feed when no keyword matches, so any query still
    gets a DeviantArt discovery stream.

    Examples:
        >>> deviantart_query_feeds("anime girls sword")
        ['https://backend.deviantart.com/rss.xml?q=animegirls&type=deviation',
         'https://backend.deviantart.com/rss.xml?q=anime&type=deviation',
         'https://backend.deviantart.com/rss.xml?q=swords&type=deviation']
    """
    if not query or not query.strip():
        return []
    lowered = " " + query.lower().strip() + " "
    tags: List[str] = []
    seen: set = set()
    # Match longer phrases first so "digital art" wins over "art".
    for keyword in sorted(DEVIANTART_KEYWORD_MAP, key=len, reverse=True):
        needle = " " + keyword + " "
        if needle in lowered:
            for tag in DEVIANTART_KEYWORD_MAP[keyword]:
                if tag not in seen:
                    seen.add(tag)
                    tags.append(tag)
    if not tags:
        # No keyword match — use the raw query as the DeviantArt tag so the
        # user still gets a DeviantArt discovery stream for any query.
        tags = [query.strip().lower().replace(" ", "")]
    return [deviantart_feed(t) for t in tags]


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
        {"url": deviantart_feed("digitalart"), "notes": "DeviantArt digital art deviations."},
        {"url": deviantart_feed("traditional"), "notes": "DeviantArt traditional art deviations."},
    ],
    "digital_art": [
        {"url": deviantart_feed("digitalart"), "notes": "DeviantArt digital art deviations."},
        {"url": deviantart_feed("painting"), "notes": "DeviantArt painting deviations."},
        {"url": deviantart_feed("procreate"), "notes": "DeviantArt Procreate artwork."},
        {"url": deviantart_feed("ipadart"), "notes": "DeviantArt iPad art."},
        {"url": flickr_tag_feed("digitalart"), "notes": "Flickr public photos tagged 'digitalart'."},
    ],
    "fantasy_art": [
        {"url": deviantart_feed("fantasy"), "notes": "DeviantArt fantasy deviations."},
        {"url": deviantart_feed("magicrealms"), "notes": "DeviantArt magic realms deviations."},
        {"url": deviantart_feed("elves"), "notes": "DeviantArt elves/elf deviations."},
        {"url": deviantart_feed("dnd"), "notes": "DeviantArt Dungeons & Dragons deviations."},
        {"url": deviantart_feed("swords"), "notes": "DeviantArt swords deviations."},
        {"url": deviantart_feed("dragons"), "notes": "DeviantArt dragons deviations."},
        {"url": flickr_tag_feed("fantasy"), "notes": "Flickr public photos tagged 'fantasy'."},
    ],
    "anime_art": [
        {"url": deviantart_feed("anime"), "notes": "DeviantArt anime deviations."},
        {"url": deviantart_feed("animegirls"), "notes": "DeviantArt anime girls deviations."},
        {"url": deviantart_feed("animemanga"), "notes": "DeviantArt anime & manga deviations."},
        {"url": deviantart_feed("manga"), "notes": "DeviantArt manga deviations."},
        {"url": deviantart_feed("magicalgirls"), "notes": "DeviantArt magical girls deviations."},
        {"url": deviantart_feed("fategrandorder"), "notes": "DeviantArt Fate/Grand Order fan art."},
        {"url": flickr_tag_feed("anime"), "notes": "Flickr public photos tagged 'anime'."},
    ],
    "concept_art": [
        {"url": deviantart_feed("conceptart"), "notes": "DeviantArt concept art deviations."},
        {"url": deviantart_feed("characterdesign"), "notes": "DeviantArt character design deviations."},
        {"url": deviantart_feed("characterconcept"), "notes": "DeviantArt character concept deviations."},
        {"url": deviantart_feed("originalcharacter"), "notes": "DeviantArt original characters."},
        {"url": deviantart_feed("referencesheet"), "notes": "DeviantArt reference sheets."},
        {"url": flickr_tag_feed("conceptart"), "notes": "Flickr public photos tagged 'conceptart'."},
    ],
    "fan_art": [
        {"url": deviantart_feed("fanart"), "notes": "DeviantArt fan art deviations."},
        {"url": deviantart_feed("videogamefanart"), "notes": "DeviantArt video game fan art."},
        {"url": deviantart_feed("gameart"), "notes": "DeviantArt game art."},
        {"url": deviantart_feed("cosplay"), "notes": "DeviantArt cosplay deviations."},
        {"url": deviantart_feed("comics"), "notes": "DeviantArt comics deviations."},
        {"url": deviantart_feed("superheroes"), "notes": "DeviantArt superheroes deviations."},
        {"url": flickr_tag_feed("fanart"), "notes": "Flickr public photos tagged 'fanart'."},
    ],
    "photography": [
        {"url": flickr_tag_feed("photography"), "notes": "Flickr public photos tagged 'photography'."},
        {"url": flickr_tag_feed("portrait"), "notes": "Flickr public photos tagged 'portrait'."},
        {"url": deviantart_feed("photography"), "notes": "DeviantArt photography deviations."},
        {"url": deviantart_feed("naturephotography"), "notes": "DeviantArt nature photography."},
        {"url": deviantart_feed("portraits"), "notes": "DeviantArt portrait photography."},
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
