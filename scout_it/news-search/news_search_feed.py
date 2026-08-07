"""News Search RSS Feed Registry

This module contains all RSS feed URLs for news-search categories.
Just add more URLs to any category and they will automatically be detected and used.

Categories:
- all: General technology news
- ai: Artificial intelligence and machine learning
- startups: Startup ecosystem and funding
- security: Cybersecurity and privacy
- cloud: Cloud computing and infrastructure
- And more...
"""

from typing import Any, Dict, List

TECHCRUNCH_FEEDS: Dict[str, List[Dict[str, Any]]] = {
    "all": [
        {"url": "https://techcrunch.com/feed/", "verified": False, "notes": "TechCrunch main technology news feed."},
        {"url": "https://www.theverge.com/rss/index.xml", "verified": False, "notes": "The Verge technology and innovation news."},
        {"url": "https://feeds.arstechnica.com/arstechnica/index", "verified": False, "notes": "Ars Technica technology journalism."},
        {"url": "https://www.wired.com/feed/rss", "verified": False, "notes": "WIRED technology and science news."},
        {"url": "https://www.zdnet.com/news/rss.xml", "verified": False, "notes": "ZDNet enterprise and technology news."},
        {"url": "https://venturebeat.com/feed/", "verified": False, "notes": "Technology and startup news."},
        {"url": "https://www.technologyreview.com/feed/", "verified": False, "notes": "MIT Technology Review news."},
        {"url": "https://www.engadget.com/rss.xml", "verified": False, "notes": "Consumer technology and gadget news."},
        {"url": "https://www.cnet.com/rss/news/", "verified": False, "notes": "Technology news and reviews."},
        {"url": "https://www.techmeme.com/feed.xml", "verified": False, "notes": "Aggregated top technology stories."},
        {"url": "https://thenextweb.com/feed/", "verified": False, "notes": "Technology and startup news."},
    ],
    "startups": [
        {"url": "https://techcrunch.com/category/startups/feed/", "verified": False, "notes": "Startup ecosystem news."},
        {"url": "https://venturebeat.com/feed/", "verified": False, "notes": "Startup and venture news."},
        {"url": "https://www.geekwire.com/feed/", "verified": False, "notes": "Startup and innovation reporting."},
        {"url": "https://thenextweb.com/feed/", "verified": False, "notes": "Startup industry coverage."},
        {"url": "https://news.crunchbase.com/feed/", "verified": False, "notes": "Funding and startup news."},
    ],
    "venture": [
        {"url": "https://techcrunch.com/category/venture/feed/", "verified": True, "notes": "TechCrunch venture category feed."},
        {"url": "https://techcrunch.com/tag/venture/feed/", "verified": True, "notes": "TechCrunch venture tag feed."},
        {"url": "https://venturebeat.com/feed/", "verified": True, "notes": "VentureBeat covers startups and venture."},
    ],
    "ai": [
        {"url": "https://techcrunch.com/category/artificial-intelligence/feed/", "verified": True, "notes": "TechCrunch AI category feed."},
        {"url": "https://techcrunch.com/tag/artificial-intelligence/feed/", "verified": True, "notes": "TechCrunch AI tag feed."},
        {"url": "https://www.technologyreview.com/topic/artificial-intelligence/feed/", "verified": True, "notes": "MIT Technology Review AI topic feed."},
        {"url": "https://tldr.tech/api/rss/ai", "verified": True, "notes": "TLDR AI feed."},
        {"url": "https://importai.substack.com/feed", "verified": True, "notes": "Import AI newsletter feed."},
        {"url": "https://simonwillison.net/atom/everything/", "verified": True, "notes": "Simon Willison Atom feed; often covers AI/tools."},
        {"url": "https://marktechpost.com/feed/", "verified": False, "notes": "MarkTechPost feed; verify in your environment."},
        {"url": "https://www.artificialintelligence-news.com/feed/", "verified": False, "notes": "AI news feed pattern; verify in your environment."},
    ],
    "space": [
        {"url": "https://techcrunch.com/category/space/feed/", "verified": False, "notes": "Space technology news."},
        {"url": "https://spacenews.com/feed/", "verified": False, "notes": "Space industry reporting."},
        {"url": "https://www.space.com/feeds/all", "verified": False, "notes": "Space exploration news."},
    ],
    "apps": [
        {"url": "https://techcrunch.com/category/apps/feed/", "verified": True, "notes": "TechCrunch apps category feed."},
        {"url": "https://www.androidauthority.com/feed/", "verified": True, "notes": "Android Authority main feed."},
        {"url": "https://www.theverge.com/apps/rss/index.xml", "verified": True, "notes": "The Verge apps feed."},
    ],
    "business": [
        {"url": "https://techcrunch.com/category/business/feed/", "verified": True, "notes": "TechCrunch business category feed."},
        {"url": "https://www.ft.com/technology?format=rss", "verified": False, "notes": "Financial Times technology RSS pattern; verify in your environment."},
        {"url": "https://feeds.a.dj.com/rss/RSSWSJD.xml", "verified": False, "notes": "WSJ tech feed pattern; verify in your environment."},
        {"url": "https://www.reuters.com/technology/", "verified": False, "notes": "Reuters technology section."},
        {"url": "https://www.bloomberg.com/technology", "verified": False, "notes": "Bloomberg technology section; RSS availability may vary."},
    ],
    "security": [
        {"url": "https://techcrunch.com/category/security/feed/", "verified": True, "notes": "TechCrunch security category feed."},
        {"url": "https://www.bleepingcomputer.com/feed/", "verified": True, "notes": "BleepingComputer main feed."},
        {"url": "https://krebsonsecurity.com/feed/", "verified": True, "notes": "Krebs on Security feed."},
        {"url": "https://www.schneier.com/feed/atom/", "verified": True, "notes": "Bruce Schneier Atom feed."},
        {"url": "https://www.darkreading.com/rss.xml", "verified": False, "notes": "Dark Reading feed pattern; verify in your environment."},
        {"url": "https://thehackernews.com/feeds/posts/default", "verified": False, "notes": "The Hacker News Atom feed pattern; verify in your environment."},
    ],
    "enterprise": [
        {"url": "https://techcrunch.com/category/enterprise/feed/", "verified": True, "notes": "TechCrunch enterprise category feed."},
        {"url": "https://www.cio.com/feed/", "verified": False, "notes": "CIO feed pattern; verify in your environment."},
        {"url": "https://www.computerworld.com/index.rss", "verified": False, "notes": "Computerworld feed pattern; verify in your environment."},
        {"url": "https://www.networkworld.com/feed/", "verified": False, "notes": "Network World feed pattern; verify in your environment."},
        {"url": "https://www.zdnet.com/topic/enterprise/rss.xml", "verified": False, "notes": "ZDNET enterprise topic feed pattern; verify in your environment."},
    ],
    "fintech": [
        {"url": "https://techcrunch.com/category/fintech/feed/", "verified": True, "notes": "TechCrunch fintech category feed."},
    ],
    "transportation": [
        {"url": "https://techcrunch.com/category/transportation/feed/", "verified": True, "notes": "TechCrunch transportation category feed."},
    ],
    "robotics": [
        {"url": "https://techcrunch.com/category/robotics/feed/", "verified": False, "notes": "Robotics industry news."},
        {"url": "https://www.roboticsbusinessreview.com/feed/", "verified": False, "notes": "Robotics business coverage."},
    ],
    "hardware": [
        {"url": "https://techcrunch.com/category/hardware/feed/", "verified": True, "notes": "TechCrunch hardware category feed."},
        {"url": "https://www.tomshardware.com/feeds.xml", "verified": False, "notes": "Tom's Hardware feed pattern; verify in your environment."},
        {"url": "https://www.anandtech.com/rss/", "verified": True, "notes": "AnandTech RSS feed."},
        {"url": "https://www.servethehome.com/feed/", "verified": True, "notes": "ServeTheHome feed."},
    ],
    "mobile": [
        {"url": "https://techcrunch.com/category/mobile/feed/", "verified": True, "notes": "TechCrunch mobile category feed."},
        {"url": "https://9to5mac.com/feed/", "verified": True, "notes": "9to5Mac main feed."},
        {"url": "https://9to5google.com/feed/", "verified": True, "notes": "9to5Google main feed."},
        {"url": "https://www.androidpolice.com/feed/", "verified": True, "notes": "Android Police main feed."},
    ],
    "gaming": [
        {"url": "https://techcrunch.com/category/gaming/feed/", "verified": True, "notes": "TechCrunch gaming category feed."},
        {"url": "https://www.theverge.com/gaming/rss/index.xml", "verified": True, "notes": "The Verge gaming feed."},
        {"url": "https://kotaku.com/rss", "verified": True, "notes": "Kotaku RSS feed."},
        {"url": "https://www.pcgamer.com/rss/", "verified": True, "notes": "PC Gamer RSS feed pattern."},
    ],
    "cloud": [
        {"url": "https://techcrunch.com/category/cloud/feed/", "verified": True, "notes": "TechCrunch cloud category feed."},
        {"url": "https://www.cshub.com/rss/categories/cloud", "verified": False, "notes": "Cloud security feed; useful for cloud/security overlap."},
    ],
    "cryptocurrency": [
        {"url": "https://techcrunch.com/category/cryptocurrency/feed/", "verified": True, "notes": "TechCrunch crypto category feed."},
        {"url": "https://techcrunch.com/tag/cryptocurrency/feed/", "verified": True, "notes": "TechCrunch crypto tag feed."},
        {"url": "https://www.coindesk.com/arc/outboundfeeds/rss/", "verified": False, "notes": "CoinDesk RSS pattern; verify in your environment."},
        {"url": "https://cointelegraph.com/rss", "verified": True, "notes": "Cointelegraph RSS feed."},
    ],
    "climate": [
        {"url": "https://techcrunch.com/category/climate/feed/", "verified": True, "notes": "TechCrunch climate category feed."},
    ],
    "social": [
        {"url": "https://techcrunch.com/category/social/feed/", "verified": True, "notes": "TechCrunch social category feed."},
        {"url": "https://www.socialmediatoday.com/feeds/news", "verified": False, "notes": "Social Media Today feed pattern; verify in your environment."},
        {"url": "https://mashable.com/feed/", "verified": False, "notes": "Mashable feed pattern; verify in your environment."},
    ],
    "commerce": [
        {"url": "https://techcrunch.com/category/commerce/feed/", "verified": True, "notes": "TechCrunch commerce category feed."},
    ],
    "open_source": [
        {"url": "https://opensource.com/feed", "verified": False, "notes": "Open source industry news."},
        {"url": "https://www.linux.com/feed/", "verified": False, "notes": "Linux and open-source news."},
        {"url": "https://lwn.net/headlines/rss", "verified": False, "notes": "Linux and kernel news."},
    ],
}
