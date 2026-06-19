"""Instagram-side data collection and analysis."""

from instabot.instagram import analysis
from instabot.instagram.client import InstagramClient
from instabot.instagram.collectors import Collector

__all__ = ["Collector", "InstagramClient", "analysis"]
