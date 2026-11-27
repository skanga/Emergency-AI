# Kiwix proxy compatibility validation

The user selected one hostname and one port, prioritizing emergency usability and Kiwix functionality over archive-script isolation. Scripts remain enabled without a sandbox or script-blocking CSP. Opened ZIM content still shares the app origin, API access and browser storage. This is an explicit limitation, not a resolved isolation vulnerability.

## Automated coverage

`python3 -m unittest discover -s tests -p test_kiwix_proxy.py` covers bounded streaming, range requests and response headers, HEAD without reading a body, malformed response lengths, script/style MIME preservation, upstream 404/416/503 responses, conditional 304 responses, same-origin canonical redirects, cross-origin redirect rejection, and errors before/after response headers. Existing HTTP boundary tests now include `/viewer_settings.js`.

The bounded-stream fixture rejects any upstream read larger than 64 KiB or without a positive byte limit. The redirect test uses an actual temporary HTTP upstream. Media range behavior is also covered with a synthetic video response.

## Live browser and HTTP checks

Chromium was driven with Playwright against temporary loopback proxies backed by the already-running Kiwix server on port 8092. The installed app and Kiwix process were not restarted or modified.

Verified:

- The Kiwix landing page loaded its JavaScript catalog of ten installed libraries.
- Catalog search for `Water` returned one library and opened its viewer.
- The Water Treatment Library, Food for Preppers and A Library of Knots loaded their JavaScript-generated document lists through the viewer.
- The water archive's search for `Giardia` filtered the list to the matching document.
- Water-library images loaded; the viewer and archive scripts/styles loaded after canonical redirect handling was corrected.
- Full-text search for `burn` in the medical Wikipedia archive returned HTTP 200 and the same 7,564-byte HTML response length directly and through the proxy, including a Burn result.
- A real water-library PDF range request returned HTTP 206, `application/pdf`, `Content-Range: bytes 0-1023/117197`, and 1,024 bytes beginning `%PDF-`, both directly and through the proxy.

Browser checks exposed two pre-existing compatibility defects repaired in this change: the missing `/viewer_settings.js` route and server-side redirect following that left the browser on the wrong base URL for relative archive assets. A missing top-level `/favicon.ico` still returns 404; it does not prevent viewer or article operation.

## Limits

This is representative compatibility evidence, not exhaustive testing of every ZIM or browser. No live video playback/codec test was completed: the inspected archive pages offered PDFs. Video range transport is covered by the automated fixture. Native Windows/macOS and phone/LAN browser testing were not performed. `nosniff` requires archives to supply correct script/style MIME types. Streaming keeps memory bounded but permits large, long-running transfers subject to socket inactivity timeouts and the existing concurrent-request limit.
