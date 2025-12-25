import socket
import ssl
import gzip
import tkinter

WIDTH, HEIGHT = 1900, 1300
SCROLL_STEP = 100
HSTEP, VSTEP = 18, 25


def lex(body):
    text = ""
    in_tag = False
    in_entity = False
    entity = ""

    for c in body:
        # Tag handling
        if in_tag:
            if c == ">":
                in_tag = False
            continue

        # Entity handling
        if in_entity:
            if c == ";":
                entity += c
                if entity == "&lt;":
                    text += "<"
                elif entity == "&gt;":
                    text += ">"
                in_entity = False
                entity = ""
            else:
                entity += c
            continue

        if c == "<":
            in_tag = True
            continue

        if c == "&":
            in_entity = True
            entity = "&"
            continue

        text += c

    return text


class Browser:
    def __init__(self):
        self.window = tkinter.Tk()

        self.canvas = tkinter.Canvas(
            self.window,
            width=WIDTH,
            height=HEIGHT
        )
        self.canvas.pack(side=tkinter.LEFT, fill=tkinter.BOTH, expand=1)

        self.scrollbar = tkinter.Scrollbar(
            self.window,
            orient="vertical",
            command=self.scrollbar_move,
            width=40,
        )
        self.scrollbar.pack(side=tkinter.RIGHT, fill=tkinter.Y)

        self.canvas.config(yscrollcommand=self.scrollbar.set)

        self.scroll = 0
        self.display_list = []
        self.text = ""
        self.width = WIDTH
        self.height = HEIGHT
        self.document_height = 0

        self.window.bind("<Down>", self.scrolldown)
        self.window.bind("<Up>", self.scrollup)
        self.window.bind("<MouseWheel>", self.mousewheel)
        self.window.bind("<Button-4>", self.mousewheel)
        self.window.bind("<Button-5>", self.mousewheel)
        self.window.bind("<Configure>", self.resize)

    def scrollbar_move(self, *args):
        if args[0] == "moveto":
            fraction = float(args[1])
            self.scroll = fraction * max(0, self.document_height - self.height)
        elif args[0] == "scroll":
            amount = int(args[1])
            self.scroll += amount * SCROLL_STEP

        self.scroll = max(0, min(self.scroll, max(0, self.document_height - self.height)))
        self.draw()

    def scrolldown(self, e=None):
        max_scroll = max(0, self.document_height - self.height)
        self.scroll = min(self.scroll + SCROLL_STEP, max_scroll)
        self.draw()

    def scrollup(self, e=None):
        self.scroll = max(self.scroll - SCROLL_STEP, 0)
        self.draw()

    def mousewheel(self, e):
        # Only process mousewheel if scrollbar is visible
        if self.scrollbar.winfo_ismapped():
            if hasattr(e, "delta") and e.delta:
                if e.delta < 0:
                    self.scrolldown()
                else:
                    self.scrollup()
                return

            if e.num == 5:
                self.scrolldown()
            elif e.num == 4:
                self.scrollup()

    def resize(self, e):
        # Use actual canvas size, not window size
        self.width = self.canvas.winfo_width()
        self.height = self.canvas.winfo_height()

        if self.text:
            self.display_list = self.layout(self.text)
            self.draw()

    def layout(self, text):
        display_list = []
        cursor_x, cursor_y = HSTEP, VSTEP

        max_width = self.width - HSTEP

        for c in text:
            if c == "\n":
                cursor_x = HSTEP
                cursor_y += VSTEP
                continue

            display_list.append((cursor_x, cursor_y, c))
            cursor_x += HSTEP

            if cursor_x >= max_width:
                cursor_x = HSTEP
                cursor_y += VSTEP

        self.document_height = cursor_y
        
        # Show/hide scrollbar based on document size
        if self.document_height <= self.height:
            self.scrollbar.pack_forget()  # Hide scrollbar
        else:
            self.scrollbar.pack(side=tkinter.RIGHT, fill=tkinter.Y)  # Show scrollbar
            
        return display_list

    def draw(self):
        self.canvas.delete("all")

        # Text
        for x, y, c in self.display_list:
            if y > self.scroll + self.height:
                continue
            if y + VSTEP < self.scroll:
                continue
            self.canvas.create_text(x, y - self.scroll, text=c, anchor="nw")

        # Scrollbar
        if self.document_height > self.height:
            thumb_size = self.height / self.document_height
            thumb_position = self.scroll / self.document_height
            first = thumb_position
            last = first + thumb_size
            
            # Ensure values are within 0-1 range
            first = max(0, min(1, first))
            last = max(0, min(1, last))
            
            self.scrollbar.set(first, last)

    def load(self, url):
        body = url.request()
        self.text = lex(body)
        self.display_list = self.layout(self.text)
        self.draw()

class URL:
    sockets = {}
    cache = {}

    def __init__(self, url):
        # data:
        if url.startswith("data:"):
            self.scheme = "data"
            self.data = url[len("data:"):]
            return

        # file://
        if url.startswith("file://"):
            self.scheme = "file"
            self.path = url[len("file://"):]
            return

        # view-source:
        if url.startswith("view-source:"):
            self.scheme = "view-source"
            self.inner = URL(url[len("view-source:"):])
            return

        # Everything else. Try to parse as http/https
        try:
            self.scheme, rest = url.split("://", 1)
            self.port = 443 if self.scheme == "https" else 80

            if self.scheme not in ("http", "https"):
                raise ValueError("Unknown scheme")

            if "/" not in rest:
                rest += "/"

            self.host, rest = rest.split("/", 1)
            self.path = "/" + rest

            if ":" in self.host:
                self.host, port = self.host.split(":", 1)
                self.port = int(port)

        except:
            self.scheme = "about"
            self.path = "blank"
            self.data = ""
            self.host = None
            self.port = None


    def request(self):
        try:
            if self.scheme == "about":
                return self.data

            if self.scheme == "data":
                return self.data.split(",", 1)[1]

            if self.scheme == "file":
                with open(self.path, "r", encoding="utf8") as f:
                    return f.read()

            if self.scheme == "view-source":
                return self.inner.request()

            key = (self.host, self.port)

            if key in URL.cache:
                return URL.cache[key]

            if key not in URL.sockets:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect((self.host, self.port))
                if self.scheme == "https":
                    ctx = ssl.create_default_context()
                    s = ctx.wrap_socket(s, server_hostname=self.host)
                URL.sockets[key] = s
            else:
                s = URL.sockets[key]

            request = (
                f"GET {self.path} HTTP/1.1\r\n"
                f"Host: {self.host}\r\n"
                f"Connection: keep-alive\r\n"
                f"Accept-Encoding: gzip\r\n"
                f"\r\n"
            )

            s.send(request.encode("utf8"))
            response = s.makefile("rb")

            statusline = response.readline().decode("utf8")
            _, status, _ = statusline.split(" ", 2)

            headers = {}
            while True:
                line = response.readline().decode("utf8")
                if line == "\r\n":
                    break
                h, v = line.split(":", 1)
                headers[h.lower()] = v.strip()

            if status.startswith("3"):
                return URL(headers["location"]).request()

            if headers.get("transfer-encoding") == "chunked":
                body = self.read_chunked(response)
            else:
                length = int(headers["content-length"])
                body = response.read(length)

            if headers.get("content-encoding") == "gzip":
                body = gzip.decompress(body)

            body = body.decode("utf8")
            URL.cache[key] = body
            return body
        
        except:
            self.scheme = "about"
            self.path = "blank"
            self.data = ""
            self.host = None
            self.port = None
            return ""

    def read_chunked(self, response):
        chunks = []
        while True:
            size = int(response.readline().strip(), 16)
            if size == 0:
                break
            chunks.append(response.read(size))
            response.read(2)
        response.read(2)
        return b"".join(chunks)


if __name__ == "__main__":
    import sys
    import os

    if len(sys.argv) > 1:
        url = URL(sys.argv[1])
    else:
        home = os.path.expanduser("~")
        testfile = os.path.join(home, "Documents", "webbrowser", "testfile")
        url = URL("file://" + testfile)

    browser = Browser()
    browser.load(url)
    tkinter.mainloop()
