import json
import os
from http.server import HTTPServer, BaseHTTPRequestHandler

from bot import api, process_update


class WebhookHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running!")

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            upd = json.loads(body)
            process_update(upd)
        except Exception as e:
            print(f"Error: {e}")
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        pass  # silent


def set_webhook(url):
    result = api("setWebhook", url=url)
    print(f"Webhook set: {result}")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    webhook_url = os.environ.get("WEBHOOK_URL", "")
    if webhook_url:
        set_webhook(f"{webhook_url}/webhook")
    print(f"Starting webhook server on port {port}")
    server = HTTPServer(("0.0.0.0", port), WebhookHandler)
    server.serve_forever()
