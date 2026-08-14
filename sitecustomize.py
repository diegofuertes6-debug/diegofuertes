"""Compatibilidad mínima para Buildozer con Python 3.14."""

import urllib.request

if not hasattr(urllib.request, "FancyURLopener"):
    class FancyURLopener(urllib.request.URLopener):
        pass

    urllib.request.FancyURLopener = FancyURLopener
