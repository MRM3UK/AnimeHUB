#!/usr/bin/env python3
"""
StreamX Backend Sniffer - uses Playwright headless browser to intercept real signed stream URLs
Run: python3 sniffer.py
Then the frontend calls: http://localhost:7777/sniff?platform=stripchat&user=kate-paul
"""
import asyncio, json, sys, re
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_OK = True
except:
    PLAYWRIGHT_OK = False

M3U8_PATTERNS = re.compile(
    r'https?://[a-zA-Z0-9.\-_]+/'
    r'(?:[a-zA-Z0-9.\-_/]+/)?'
    r'(?:[a-zA-Z0-9.\-_]+\.m3u8|playlist\.m3u8|index\.m3u8|master\.m3u8)'
    r'(?:\?[^\s"\'<>]*)?'
)

def score_url(url):
    if 'master' in url: return 100
    if '1080' in url: return 90
    if '720' in url: return 80
    if '480' in url: return 70
    if '360' in url: return 60
    if '240' in url: return 50
    if 'index' in url or 'playlist' in url: return 75
    return 65

async def sniff_platform(platform, user, timeout=25):
    found = []
    seen = set()

    urls_to_try = {
        'stripchat': [f'https://stripchat.com/{user}'],
        'chaturbate': [f'https://chaturbate.com/{user}/'],
        'jerkmate': [f'https://jerkmate.com/{user}'],
    }

    page_urls = urls_to_try.get(platform, [f'https://stripchat.com/{user}'])

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=['--no-sandbox','--disable-setuid-sandbox',
                  '--disable-web-security','--disable-features=IsolateOrigins',
                  '--disable-site-isolation-trials']
        )
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.144 Mobile Safari/537.36',
            viewport={'width':1280,'height':720},
            ignore_https_errors=True,
        )

        page = await context.new_page()

        def capture(url):
            if not url: return
            url = url.replace('\\u0026','&')
            is_m3u8 = ('.m3u8' in url or 
                       ('playlist' in url.lower() and 'hls' in url.lower()) or
                       ('/hls/live/' in url))
            if is_m3u8 and url not in seen:
                seen.add(url)
                found.append({'url': url, 'score': score_url(url)})
                print(f"[INTERCEPT] {url[:120]}", flush=True)

        async def on_request(req):
            capture(req.url)

        async def on_response(resp):
            url = resp.url
            capture(url)
            # Also scan response body of JS/JSON for embedded m3u8 URLs
            if resp.ok and resp.headers.get('content-type','') in ['application/json','text/javascript','application/javascript']:
                try:
                    body = await resp.text()
                    for m in M3U8_PATTERNS.finditer(body):
                        capture(m.group(0))
                except:
                    pass

        page.on('request', on_request)
        page.on('response', on_response)

        for url in page_urls:
            try:
                print(f"[NAV] {url}", flush=True)
                await page.goto(url, timeout=timeout*1000, wait_until='domcontentloaded')
                # Wait for dynamic content to load
                await page.wait_for_timeout(10000)
                
                # Also check performance entries
                try:
                    entries = await page.evaluate("""
                        () => performance.getEntriesByType('resource')
                            .map(e => e.name)
                            .filter(n => n.includes('.m3u8') || n.includes('/hls/live/'))
                    """)
                    for e in entries: capture(e)
                except: pass

                # Check for any XHR/fetch that happened
                try:
                    network_urls = await page.evaluate("""
                        () => {
                            const all = [];
                            // Try to find stream config in window objects
                            const check = (obj, depth=0) => {
                                if (depth > 4 || !obj) return;
                                if (typeof obj === 'string' && obj.includes('.m3u8')) all.push(obj);
                                if (typeof obj === 'object') {
                                    try { Object.values(obj).forEach(v => check(v, depth+1)); } catch {}
                                }
                            };
                            try { check(window.__NUXT__); } catch {}
                            try { check(window.__INITIAL_STATE__); } catch {}
                            try { check(window.App); } catch {}
                            try { check(window.chaturbate); } catch {}
                            try { check(window.CB); } catch {}
                            return all;
                        }
                    """)
                    for u in network_urls: capture(u)
                except: pass

            except Exception as e:
                print(f"[ERR] {e}", flush=True)

        await browser.close()

    found.sort(key=lambda x: x['score'], reverse=True)
    return found


class SnifferHandler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass  # Suppress default logs

    def send_cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_cors()
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)

        if parsed.path == '/health':
            self.send_response(200)
            self.send_cors()
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'ok': True, 'playwright': PLAYWRIGHT_OK}).encode())
            return

        if parsed.path == '/sniff':
            platform = qs.get('platform', ['stripchat'])[0]
            user = qs.get('user', [''])[0]
            if not user:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b'{"error":"no user"}')
                return

            print(f"\n[SNIFF] {platform}/{user}", flush=True)
            try:
                results = asyncio.run(sniff_platform(platform, user))
            except Exception as e:
                results = []
                print(f"[ERR] {e}", flush=True)

            self.send_response(200)
            self.send_cors()
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            resp = {'platform': platform, 'user': user, 'urls': results, 'count': len(results)}
            self.wfile.write(json.dumps(resp).encode())
            return

        self.send_response(404)
        self.end_headers()


if __name__ == '__main__':
    port = 7777
    print(f"StreamX Sniffer Backend running on http://localhost:{port}", flush=True)
    print(f"Playwright: {'OK' if PLAYWRIGHT_OK else 'NOT AVAILABLE'}", flush=True)
    print(f"Usage: GET /sniff?platform=stripchat&user=kate-paul", flush=True)
    server = HTTPServer(('0.0.0.0', port), SnifferHandler)
    server.serve_forever()
