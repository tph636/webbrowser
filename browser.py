import socket
import ssl
import gzip
import tkinter


WIDTH, HEIGHT = 800, 600

class Browser:
    def __init__(self):
        self.window = tkinter.Tk()
        self.canvas = tkinter.Canvas(
            self.window, 
            width=WIDTH,
            height=HEIGHT
        )
        self.canvas.pack()

    def load(self, url):
        text = url.lex(url.request())

        HSTEP, VSTEP = 13, 18
        cursor_x, cursor_y = HSTEP, VSTEP
        for c in text:
            self.canvas.create_text(cursor_x, cursor_y, text=c)
            cursor_x += HSTEP
            if cursor_x >= WIDTH - HSTEP:
                cursor_y += VSTEP
                cursor_x = HSTEP

class URL:
    sockets = {}
    cache = {}

    def __init__(self, url):
        # data: URLs
        if url.startswith("data:"):
            self.scheme = "data"
            self.data = url[len("data:") :]
            return

        # file: URLs
        if url.startswith("file://"):
            self.scheme = "file"
            path = url[len("file://") :]
            self.path = path if path.startswith("/") else "/" + path
            return

        # view-source: URLs
        if url.startswith("view-source:"):
            self.scheme = "view-source"
            self.inner = URL(url[len("view-source:") :])
            return

        # http / https URLs
        if url.startswith("http://") or url.startswith("https://"):
            self.scheme, rest = url.split("://", 1)
            if self.scheme == "http":
                self.port = 80
            elif self.scheme == "https":
                self.port = 443

            if "/" not in rest:
                rest = rest + "/"

            self.host, rest = rest.split("/", 1)
            self.path = "/" + rest

            if ":" in self.host:
                self.host, port = self.host.split(":", 1)
                self.port = int(port)

        assert self.scheme in ["http", "https", "file", "data", "view-source"]

    
    # Fetch the resource, handling caching, redirects, and decompression
    def request(self):
        if self.scheme == "data":
            body = self.data.split(",", 1)[1]
            return body

        if self.scheme == "file":
            with open(self.path, "r", encoding="utf8") as f:
                return f.read()

        key = (self.host, self.port)

        # Get content from cache if possible
        if key in URL.cache:
            return URL.cache[key] + " CACHED"

        if key not in URL.sockets:
            s = socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP)
            s.connect((self.host, self.port))

            if self.scheme == "https":
                ctx = ssl.create_default_context()
                s = ctx.wrap_socket(s, server_hostname=self.host)

            URL.sockets[key] = s
        else:
            s = URL.sockets[key]


        headers = {
            "Host": self.host,
            "Connection": "keep-alive",
            "User-Agent": "MyBrowser/",
            "Accept-Encoding": "gzip",
        }

        # Add headers to request
        request = f"GET {self.path} HTTP/1.1\r\n"
        for name, value in headers.items():
            request += f"{name}: {value}\r\n"
        request += "\r\n"

        s.send(request.encode("utf8"))

        response = s.makefile("rb")
        statusline = response.readline().decode("utf8")
        to_cache = False
        max_age = None

        # Example: "HTTP/1.1 200 OK"
        version, status, explanation = statusline.split(" ", 2)

        response_headers = {}
        while True:
            line = response.readline().decode("utf8")
            if line == "\r\n":
                break
            header, value = line.split(":", 1)
            response_headers[header.casefold()] = value.strip()

        # Cache-Control handling
        cc = response_headers.get("cache-control", "").lower()
        if cc:
            parts = [p.strip() for p in cc.split(",")]
            if "no-store" in parts:
                to_cache = False
            else:
                for p in parts:
                    if p.startswith("max-age="):
                        try:
                            max_age = int(p.split("=", 1)[1])
                            to_cache = True
                        except:
                            to_cache = False
                        break
                else:
                    to_cache = False

        # 300 range redirect
        if status in ("301", "302", "303", "307", "308"):
            return URL(response_headers.get("location", "")).request()

        if status == "200" and not cc:
            to_cache = True

        # Read body: chunked vs Content-Length
        if response_headers.get("transfer-encoding", "").lower() == "chunked":
            content = self.read_chunked(response)
        else:
            length = int(response_headers["content-length"])
            content = response.read(length)
            response.read(2)

        # Decompress gzip if needed
        if response_headers.get("content-encoding", "").lower() == "gzip":
            content = gzip.decompress(content)

        content = content.decode("utf8")

        # Cache content
        if (key not in URL.cache) and to_cache:
            URL.cache[key] = content

        return content

    def read_chunked(self, response):
        chunks = []
        while True:
            # Read chunk size line (hex)
            line = response.readline().decode("utf8")
            size_str = line.strip()

            size = int(size_str, 16)
            if size == 0:
                break

            chunk = response.read(size)
            chunks.append(chunk)

            response.read(2)

        response.read(2)
        return b"".join(chunks)

    # Show HTML
    def lex(self, body):
        text = ""
        in_tag = False
        entity = ""
        in_entity = False

        for c in body:
            if in_entity:
                if c == ";":
                    entity += c
                    if entity == "&lt;":
                        text += "<"
                    elif entity == "&gt;":
                        text += ">"
                    else:
                        print(entity, end="")
                    in_entity = False
                    entity = ""
                else:
                    entity += c
                continue

            if c == "&":
                in_entity = True
                entity = "&"
                continue

            if c == "<":
                in_tag = True
            elif c == ">":
                in_tag = False
            elif not in_tag:
                text += c

        return text
    
    def load(self):
        if self.scheme == "view-source":
            body = self.inner.request()
            print(body)
        else:
            body = self.request()
            self.show(body)


if __name__ == "__main__":
    import sys
    import os

    if len(sys.argv) > 1:
        url = URL(sys.argv[1])
    else:
        # Default file for quick testing, built dynamically
        home = os.path.expanduser("~")
        testfile = os.path.join(home, "Documents", "webbrowser", "testfile")
        url = URL("file://" + testfile)

    Browser().load(url)
    tkinter.mainloop()


