"""Web Search RSS Feed Registry.

This module contains RSS feed URLs for web-search category providers.
Similar to tech_crunch_rss.py but focused on technical blogs, engineering,
research, and open source content rather than news.
"""

from typing import Any, Dict, List

__all__ = ['WEB_SEARCH_FEEDS']

WEB_SEARCH_FEEDS: Dict[str, List[Dict[str, Any]]] = {

    "ai": [
        {"url": "https://openai.com/news/rss.xml", "verified": False, "notes": "OpenAI announcements and releases."},
        {"url": "https://huggingface.co/blog/feed.xml", "verified": False, "notes": "Hugging Face blog and model updates."},
        {"url": "https://deepmind.google/blog/rss.xml", "verified": False, "notes": "Google DeepMind research updates."},
        {"url": "https://blog.google/innovation-and-ai/technology/ai/rss/", "verified": False, "notes": "Google AI announcements."},
        {"url": "https://blogs.nvidia.com/feed/", "verified": False, "notes": "NVIDIA AI and GPU developments."},
        {"url": "https://ollama.com/blog/rss.xml", "verified": False, "notes": "Ollama releases and updates."},
        {"url": "https://weaviate.io/blog/rss.xml", "verified": False, "notes": "Weaviate vector search blog."},
    ],

    "engineering": [
        {"url": "https://netflixtechblog.com/feed", "verified": False, "notes": "Netflix engineering blog."},
        {"url": "https://blog.cloudflare.com/rss/", "verified": False, "notes": "Cloudflare engineering and security."},
        {"url": "https://slack.engineering/feed/", "verified": False, "notes": "Slack engineering stories."},
        {"url": "https://stripe.com/blog/feed.rss", "verified": False, "notes": "Stripe engineering updates."},
        {"url": "https://engineering.fb.com/feed/", "verified": False, "notes": "Meta engineering blog."},
        {"url": "https://medium.com/feed/airbnb-engineering", "verified": False, "notes": "Airbnb engineering."},
        {"url": "https://dropbox.tech/feed", "verified": False, "notes": "Dropbox engineering."},
        {"url": "https://engineering.atspotify.com/feed", "verified": False, "notes": "Spotify engineering."},
        {"url": "https://discord.com/blog/rss.xml", "verified": False, "notes": "Discord engineering and product updates."},
    ],

    "cloud": [
        {"url": "https://aws.amazon.com/blogs/aws/feed/", "verified": False, "notes": "AWS official news blog."},
        {"url": "https://azure.microsoft.com/en-us/blog/feed/", "verified": False, "notes": "Azure platform updates."},
        {"url": "https://www.redhat.com/en/blog/rss.xml", "verified": False, "notes": "Red Hat engineering and cloud."},
        {"url": "https://www.hashicorp.com/blog/feed.xml", "verified": False, "notes": "HashiCorp tooling updates."},
        {"url": "https://www.linode.com/blog/feed/", "verified": False, "notes": "Linode cloud updates."},
    ],

    "software_engineering": [
        {"url": "https://feed.infoq.com/", "verified": False, "notes": "Software engineering articles."},
        {"url": "https://stackoverflow.blog/feed/", "verified": False, "notes": "Stack Overflow blog."},
        {"url": "https://martinfowler.com/feed.atom", "verified": False, "notes": "Software architecture insights."},
        {"url": "https://dev.to/feed", "verified": False, "notes": "DEV community posts."},
        {"url": "https://thenewstack.io/feed/", "verified": False, "notes": "Cloud-native engineering."},
        {"url": "https://www.infoq.com/feed/", "verified": False, "notes": "Software engineering news."},
    ],

    "open_source": [
        {"url": "https://opensource.com/feed", "verified": False, "notes": "Open source community."},
        {"url": "https://www.linux.com/feed/", "verified": False, "notes": "Linux ecosystem."},
        {"url": "https://lwn.net/headlines/rss", "verified": False, "notes": "Linux kernel updates."},
        {"url": "https://planet.python.org/rss20.xml", "verified": False, "notes": "Python ecosystem."},
        {"url": "https://planet.mozilla.org/rss20.xml", "verified": False, "notes": "Mozilla development."},
        {"url": "https://planet.gnome.org/rss20.xml", "verified": False, "notes": "GNOME community."},
    ],

    "data_science": [
        {"url": "https://towardsdatascience.com/feed", "verified": False, "notes": "Data science articles."},
        {"url": "https://www.kdnuggets.com/feed", "verified": False, "notes": "Analytics and AI content."},
        {"url": "https://www.datanami.com/feed/", "verified": False, "notes": "Big data industry."},
        {"url": "https://aws.amazon.com/blogs/big-data/feed/", "verified": False, "notes": "AWS big data."},
    ],

    "research": [
        {"url": "https://rss.arxiv.org/rss/cs", "verified": False, "notes": "Computer science papers."},
        {"url": "https://rss.arxiv.org/rss/ai", "verified": False, "notes": "Artificial intelligence papers."},
        {"url": "https://www.nature.com/subjects/computer-science.rss", "verified": False, "notes": "Computer science research."},
        {"url": "https://www.sciencedaily.com/rss/computers_math.xml", "verified": False, "notes": "Research summaries."},
        {"url": "https://paperswithcode.com/rss/latest", "verified": False, "notes": "Latest ML papers."},
    ],

    "devops": [
        {"url": "https://www.devops.com/feed/", "verified": False, "notes": "DevOps ecosystem."},
        {"url": "https://containerjournal.com/feed/", "verified": False, "notes": "Containers and Kubernetes."},
        {"url": "https://kubernetes.io/feed.xml", "verified": False, "notes": "Kubernetes updates."},
        {"url": "https://helm.sh/blog/index.xml", "verified": False, "notes": "Helm project updates."},
    ],

    "databases": [
        {"url": "https://www.datanami.com/feed/", "verified": False, "notes": "Big data and databases."},
        {"url": "https://planet.postgresql.org/rss20.xml", "verified": False, "notes": "PostgreSQL community."},
        {"url": "https://www.mongodb.com/blog/rss", "verified": False, "notes": "MongoDB updates."},
        {"url": "https://www.percona.com/blog/feed/", "verified": False, "notes": "MySQL and PostgreSQL insights."},
    ],

    "frontend": [
        {"url": "https://react.dev/rss.xml", "verified": False, "notes": "React updates."},
        {"url": "https://blog.angular.dev/feed", "verified": False, "notes": "Angular blog."},
        {"url": "https://svelte.dev/blog/rss.xml", "verified": False, "notes": "Svelte framework updates."},
        {"url": "https://nextjs.org/feed.xml", "verified": False, "notes": "Next.js releases."},
        {"url": "https://astro.build/rss.xml", "verified": False, "notes": "Astro framework updates."},
    ],

    "backend": [
        {"url": "https://nodejs.org/en/feed/blog.xml", "verified": False, "notes": "Node.js updates."},
        {"url": "https://go.dev/blog/feed.atom", "verified": False, "notes": "Go language updates."},
        {"url": "https://blog.rust-lang.org/feed.xml", "verified": False, "notes": "Rust language updates."},
    ],

    "security_research": [
        {"url": "https://www.schneier.com/feed/atom/", "verified": False, "notes": "Security research."},
        {"url": "https://unit42.paloaltonetworks.com/feed/", "verified": False, "notes": "Threat intelligence."},
        {"url": "https://www.crowdstrike.com/blog/feed/", "verified": False, "notes": "Security analysis."},
        {"url": "https://www.sentinelone.com/blog/feed/", "verified": False, "notes": "Threat research."},
    ],

    "community": [
        {"url": "https://news.ycombinator.com/rss", "verified": False, "notes": "Hacker News front page."},
        {"url": "https://lobste.rs/rss", "verified": False, "notes": "Programming community discussions."},
        {"url": "https://www.producthunt.com/feed", "verified": False, "notes": "Product launches and discovery."},
    ]
}