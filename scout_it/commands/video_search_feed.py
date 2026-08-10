"""Video Search RSS Feed Registry.

RSS feed URLs for video-search category providers. Every public YouTube
channel exposes a free Atom feed at
``https://www.youtube.com/feeds/videos.xml?channel_id=<ID>`` returning the
channel's recent uploads with Media RSS thumbnails, titles, descriptions, and
publish dates. This registry curates high-quality channels by category so the
unified video-search pipeline can discover videos via RSS alongside DuckDuckGo.

All channel IDs below have been verified to return a live feed (HTTP 200).
"""

from typing import Any, Dict, List

__all__ = ["VIDEO_SEARCH_FEEDS", "youtube_channel_feed"]


def youtube_channel_feed(channel_id: str) -> str:
    """YouTube channel uploads Atom feed."""
    return f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"


VIDEO_SEARCH_FEEDS: Dict[str, List[Dict[str, Any]]] = {
    "technology": [
        {"url": youtube_channel_feed("UC_x5XG1OV2P6uZZ5FSM9Ttw"), "notes": "Google for Developers."},
        {"url": youtube_channel_feed("UCddiUEpeqJcYeBxX1IVBKvQ"), "notes": "The Verge."},
        {"url": youtube_channel_feed("UCBJycsmduvYEL83R_U4JriQ"), "notes": "Marques Brownlee (MKBHD)."},
        {"url": youtube_channel_feed("UCXuqSBlHAE6Xw-yeJA0Tunw"), "notes": "Linus Tech Tips."},
    ],
    "science": [
        {"url": youtube_channel_feed("UCHnyfMqiRRG1u-2MsSQLbXA"), "notes": "Veritasium."},
        {"url": youtube_channel_feed("UC8VkNBOwvsTlFjoSnNSMmxw"), "notes": "SmarterEveryDay."},
        {"url": youtube_channel_feed("UCsXVk37bltHxD1rDPwtNM8Q"), "notes": "Kurzgesagt - In a Nutshell."},
        {"url": youtube_channel_feed("UCUdettijNYvLAm4AixZv4RA"), "notes": "SciShow."},
    ],
    "education": [
        {"url": youtube_channel_feed("UC4R8DWoMoI7CAwX8_LjQHig"), "notes": "TED-Ed."},
        {"url": youtube_channel_feed("UCBcRF18a7Qf58cCRy5xuWwQ"), "notes": "Vsauce."},
        {"url": youtube_channel_feed("UC2ri4rEb8abnNwXvTjg5ARw"), "notes": "Khan Academy."},
    ],
    "news": [
        {"url": youtube_channel_feed("UCLA_DiR1FfKNvjuUpBHmylQ"), "notes": "NASA."},
        {"url": youtube_channel_feed("UC16niRr50-MSBwiO3YDb3RA"), "notes": "BBC News."},
        {"url": youtube_channel_feed("UChqUTb7kYRX8-EiaN3XFrSQ"), "notes": "Reuters."},
        {"url": youtube_channel_feed("UCBi2mrWuNuyYy4gbM6fU18Q"), "notes": "ABC News."},
    ],
    "space": [
        {"url": youtube_channel_feed("UCLA_DiR1FfKNvjuUpBHmylQ"), "notes": "NASA."},
        {"url": youtube_channel_feed("UCryGec9PdUCLjpJW2mgCuLw"), "notes": "NASA Spaceflight."},
        {"url": youtube_channel_feed("UC6uKrU_WqJ1R2HMTY3LIx5Q"), "notes": "Everyday Astronaut."},
    ],
    "ai": [
        {"url": youtube_channel_feed("UCbfYPyITQ-7l4upoX8nvctg"), "notes": "Two Minute Papers."},
        {"url": youtube_channel_feed("UCSHZKyawb77ixDdsGog4iWA"), "notes": "Lex Fridman."},
        {"url": youtube_channel_feed("UCZHmQk67mSJgfCCTn7xBfew"), "notes": "Yannic Kilcher."},
    ],
    "engineering": [
        {"url": youtube_channel_feed("UCR1IuLEqb6UEA_zQ81kwXfg"), "notes": "Real Engineering."},
        {"url": youtube_channel_feed("UCY1kMZp36IQSyNx_9h4mpCg"), "notes": "Mark Rober."},
        {"url": youtube_channel_feed("UCAK3X_yAuxrQo_6q_mzPK8w"), "notes": "Practical Engineering."},
    ],
    "history": [
        {"url": youtube_channel_feed("UCv_vLHiWVBh_FR9vbeuiY-A"), "notes": "Historia Civilis."},
        {"url": youtube_channel_feed("UCMmaBzfCCwZ2KqaBJjkj0fw"), "notes": "Kings and Generals."},
        {"url": youtube_channel_feed("UCCODtTcd5M1JavPCOr_Uydg"), "notes": "Extra History."},
    ],
    "music": [
        {"url": youtube_channel_feed("UC5nc_ZtjKW1htCVZVRxlQAQ"), "notes": "Mr. Suicidesheep (electronic)."},
    ],
    "gaming": [
        {"url": youtube_channel_feed("UCKy1dAqELo0zrOtPkf0eTMw"), "notes": "IGN."},
        {"url": youtube_channel_feed("UCbu2SsF-Or3Rsn3NxqODImw"), "notes": "GameSpot."},
    ],
    "sports": [
        {"url": youtube_channel_feed("UCWJ2lWNubArHWmf3FIHbfcQ"), "notes": "NBA."},
        {"url": youtube_channel_feed("UCiio0ydw439X13KyZgMIcHw"), "notes": "ESPN."},
    ],
    "cooking": [
        {"url": youtube_channel_feed("UCbpMy0Fg74eXXkvxJrtEn3w"), "notes": "Bon Appetit."},
        {"url": youtube_channel_feed("UC8Y-jrV8oR3s2Ix4viDkZtA"), "notes": "Food Network."},
        {"url": youtube_channel_feed("UChBEbMKI1eCcejTtmI32UEw"), "notes": "Joshua Weissman."},
    ],
    "documentary": [
        {"url": youtube_channel_feed("UCijcd0GR0fkxCAZwkiuWqtQ"), "notes": "Free Documentary."},
        {"url": youtube_channel_feed("UCW39zufHfsuGgpLviKh297Q"), "notes": "DW Documentary."},
    ],
    "ted": [
        {"url": youtube_channel_feed("UCAuUUnT6oDeKwE6v1NGQxug"), "notes": "TED."},
        {"url": youtube_channel_feed("UC4R8DWoMoI7CAwX8_LjQHig"), "notes": "TED-Ed."},
    ],
}
