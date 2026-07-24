import urllib.request
from http.cookiejar import CookieJar
import requests

s = requests.Session()
s.cookies.set("adera_session", "val", domain="example.com")
print("requests req:", requests.Request('GET', 'https://example.com/').prepare().headers)
