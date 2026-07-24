import urllib.request
from http.cookiejar import CookieJar
import requests

s = requests.Session()
s.cookies.set("adera_session", "val", domain="test")
print("requests test:", s.cookies.get_dict())
print("requests req:", requests.Request('GET', 'https://test/').prepare().headers)

s = requests.Session()
s.cookies.set("adera_session", "val", domain="localhost")
print("requests localhost req:", requests.Request('GET', 'https://localhost/').prepare().headers)
