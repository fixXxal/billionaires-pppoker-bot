"""
Compatibility layer: Makes Django API look like the old SheetsManager
This allows bot.py to work without changes
"""

from django_api import DjangoAPI
import os

class SheetsCompat:
    """Wrapper that makes Django API compatible with old sheets code"""

    def __init__(self):
        api_url = os.getenv('DJANGO_API_URL', 'http://localhost:8000/api')
        self.api = DjangoAPI(api_url)

    # Just pass through all calls to django_api
    def __getattr__(self, name):
        return getattr(self.api, name)
