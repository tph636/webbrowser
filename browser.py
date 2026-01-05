import socket
import ssl
import gzip
import tkinter
import tkinter.font

WIDTH, HEIGHT = 1900, 1300
SCROLL_STEP = 100
HSTEP, VSTEP = 13, 18
FONTS = {}

def lex(body):
    out = []
    buffer = ""
    in_tag = False
    in_entity = False
    entity = ""  # Need a separate buffer for entities
    
    i = 0
    while i < len(body):
        c = body[i]
        
        if in_entity:
            entity += c
            if c == ";":
                # Check if it's a known entity
                if entity == "&lt;":
                    buffer += "<"
                elif entity == "&gt;":
                    buffer += ">"
                elif entity == "&amp;":
                    buffer += "&"
                elif entity == "&quot;":
                    buffer += '"'
                elif entity == "&apos;":
                    buffer += "'"
                else:
                    # Not a valid entity, add as plain text
                    buffer += entity
                in_entity = False
                entity = ""
            i += 1
            continue
            
        if c == "&":
            # Check if it's actually an entity by looking ahead
            # Common entities: &lt; &gt; &amp; &quot; &apos;
            remaining = len(body) - i - 1
            if remaining >= 3:
                # Check for common 3-char entities: &lt; &gt;
                if body[i:i+4] == "&lt;" or body[i:i+4] == "&gt;":
                    in_entity = True
                    entity = "&"
                    i += 1
                    continue
            if remaining >= 4:
                # Check for 4-char entity: &amp;
                if body[i:i+5] == "&amp;":
                    in_entity = True
                    entity = "&"
                    i += 1
                    continue
            if remaining >= 5:
                # Check for 5-char entities: &quot; &apos;
                if body[i:i+6] == "&quot;" or body[i:i+6] == "&apos;":
                    in_entity = True
                    entity = "&"
                    i += 1
                    continue
            
            # If not an entity, just add & to buffer
            buffer += c
            i += 1
            continue
            
        if c == "<":
            in_tag = True
            if buffer: out.append(Text(buffer))
            buffer = ""
            i += 1
            continue
            
        if c == ">":
            in_tag = False
            out.append(Tag(buffer))
            buffer = ""
            i += 1
            continue
            
        buffer += c
        i += 1
        
    if buffer:
        if in_tag:
            out.append(Tag(buffer))
        else:
            out.append(Text(buffer))
    
    return out

import tkinter

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

        self.canvas.config(yscrollcommand=self.scrollbar.set)

        self.scroll = 0
        self.display_list = []
        self.tokens = []
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
            self.scroll = fraction * self.document_height
        elif args[0] == "scroll":
            amount = int(args[1])
            self.scroll += amount * SCROLL_STEP

        # Clamp based on document height minus visible height
        max_scroll = max(0, self.document_height - self.height)
        self.scroll = max(0, min(self.scroll, max_scroll))
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

    def position_scrollbar(self):
        if self.document_height > self.height:
            # Place scrollbar on the right side with fixed width
            self.scrollbar.place(
                x=self.width - 40,
                y=0,
                width=40,
                height=self.height
            )
        else:
            self.scrollbar.place_forget()  # Hide if not needed

    def resize(self, e):
        self.width = self.canvas.winfo_width()
        self.height = self.canvas.winfo_height()

        if self.tokens:
            # Re-layout with current width
            layout = Layout(self.tokens, self.width)
            self.display_list = layout.display_list
            self.document_height = layout.document_height
            self.draw()
        
        # Position scrollbar after resize
        self.position_scrollbar()

    def draw(self):
        self.canvas.delete("all")

        # Text
        for x, y, word, font in self.display_list:
            if y > self.scroll + self.height:
                continue
            if y + font.metrics("linespace") * 1.25 < self.scroll:
                continue
            self.canvas.create_text(x, y - self.scroll, text=word, anchor="nw", font=font)

        # Update scrollbar position and thumb
        if self.document_height > self.height:
            thumb_size = self.height / self.document_height
            thumb_position = self.scroll / self.document_height
            first = thumb_position
            last = first + thumb_size
            
            # Ensure values are within 0-1 range
            first = max(0, min(1, first))
            last = max(0, min(1, last))
            
            self.scrollbar.set(first, last)
            
            # Reposition scrollbar in case canvas size changed
            self.position_scrollbar()

    def load(self, url):
        body = url.request()
        self.tokens = lex(body)
        self.display_list = Layout(self.tokens, self.width).display_list
        self.draw()

class Text:
    def __init__(self, text):
        self.text = text

class Tag:
    def __init__(self, tag):
        self.tag = tag

def get_font(size, weight, style):
    key = (size, weight, style)
    if key not in FONTS:
        font = tkinter.font.Font(size=size, weight=weight,
            slant=style)
        label = tkinter.Label(font=font)
        FONTS[key] = (font, label)
    return FONTS[key][0]

class Layout:
    
    def __init__(self, tokens, width):
        self.display_list = []
        self.tokens = tokens
        self.width = width
        self.size = 12
        self.line = []

        self.cursor_x = HSTEP
        self.cursor_y = VSTEP
        self.weight = "normal"
        self.style = "roman"


        for tok in tokens:
            self.token(tok)

        self.document_height = self.cursor_y
        
        self.flush()

    def token(self, tok):
        if isinstance(tok, Text):
            for word in tok.text.split():
                self.word(word)
        elif tok.tag == "i":
            self.style = "italic"
        elif tok.tag == "/i":
            self.style = "roman"
        elif tok.tag == "b":
            self.weight = "bold"
        elif tok.tag == "/b":
            self.weight = "normal"
        elif tok.tag == "small":
            self.size -= 2
        elif tok.tag == "/small":
            self.size += 2
        elif tok.tag == "big":
            self.size += 4
        elif tok.tag == "/big":
            self.size -= 4
        elif tok.tag == "br":
            self.flush()
        elif tok.tag == "/p":
            self.flush()
            self.cursor_y += VSTEP

        self.document_height = self.cursor_y
                
        return self.display_list
    
    def word(self, word):
        font = get_font(self.size, self.weight, self.style)
        w = font.measure(word)
        if self.cursor_x + w > self.width - HSTEP - 40: 
            self.flush()

        # Store the current x position (where word starts)
        word_x = self.cursor_x
        self.cursor_x += w + font.measure(" ")
        
        # Store word with its starting position
        self.line.append((word_x, word, font))

    def flush(self):
        if not self.line: return
        metrics = [font.metrics() for x, word, font in self.line]
        max_ascent = max([metric["ascent"] for metric in metrics])
        baseline = self.cursor_y + 1.25 * max_ascent

        for x, word, font in self.line:
            y = baseline - font.metrics("ascent")
            self.display_list.append((x, y, word, font))

        max_descent = max([metric["descent"] for metric in metrics])
        self.cursor_y = baseline + 1.25 * max_descent

        self.cursor_x = HSTEP
        self.line = []


    
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
