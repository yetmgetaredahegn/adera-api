from httpx import Cookies, Request, Response

cookies = Cookies()
cookies.set("adera_session", "value", domain="test")
print(list(cookies.jar))
req = Request("GET", "https://test/api")
print(cookies.jar._cookies)
cookies.set_cookie_header(req)
print(req.headers)

# Also let's see what happens if we set a cookie from a response
cookies2 = Cookies()
res = Response(200, headers=[(b"set-cookie", b"adera_session=val; Secure; HttpOnly; Path=/; SameSite=Lax")])
cookies2.extract_cookies(res)
print("Extracted:", cookies2)
req2 = Request("GET", "https://test/api")
cookies2.set_cookie_header(req2)
print("Headers2:", req2.headers)
