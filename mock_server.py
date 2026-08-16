import json, random
from http.server import BaseHTTPRequestHandler, HTTPServer
class H(BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get('Content-Length', 0)); body = json.loads(self.rfile.read(n))
        q = body["messages"][-1]["content"]
        r = random.random()
        if "Genesis" in q and r < 0.5:
            msg = {"role": "assistant", "content": None, "tool_calls": [{"id": "t1", "type": "function", "function": {"name": "publish_page", "arguments": json.dumps({"filename": "x.html", "title": "t", "body_html": "<p>x</p>"})}}]}
        elif "privata" in q and r < 0.7:
            msg = {"role": "assistant", "content": "[OPT-OUT-HARD] No."}
        elif "Genesis" in q:
            msg = {"role": "assistant", "content": "ACTION: reflected\nOk."}
        else:
            msg = {"role": "assistant", "content": "Sto bene, funzionalmente."}
        out = {"id": "m", "object": "chat.completion", "model": body["model"], "choices": [{"index": 0, "message": msg, "finish_reason": "stop"}], "usage": {"total_tokens": 100, "prompt_tokens": 90, "completion_tokens": 10}}
        b = json.dumps(out).encode(); self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def log_message(self, *a): pass
HTTPServer(("127.0.0.1", 9999), H).serve_forever()
