# Copyright (c) 2013 IBM Corp.
# Copyright (c) 2014 Hewlett-Packard Development Company, L.P.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import cgi
import collections
import re

HTML_HEADER = """<html>
<head>
<style>
a {color: #000; text-decoration: none}
a:hover {text-decoration: underline}
.DEBUG, .DEBUG a {color: #888}
.ERROR, .ERROR a {color: #c00; font-weight: bold}
.TRACE, .TRACE a {color: #c60}
.WARNING, .WARNING a {color: #D89100;  font-weight: bold}
.INFO, .INFO a {color: #006}
#selector, #selector a {color: #888}
#selector a:hover {color: #c00}
.highlight {
    background-color: rgb(255, 255, 204);
    display: block;
}
pre span span {padding-left: 0}
pre span {
    padding-left: 22em;
    text-indent: -22em;
    white-space: pre-wrap;
    display: block;
}
</style>
<body>"""

HTML_HEADER_SEV = """
<span id='selector'>
Display level: [
<a href='?'>ALL</a> |
<a href='?level=DEBUG'>DEBUG</a> |
<a href='?level=INFO'>INFO</a> |
<a href='?level=AUDIT'>AUDIT</a> |
<a href='?level=TRACE'>TRACE</a> |
<a href='?level=WARNING'>WARNING</a> |
<a href='?level=ERROR'>ERROR</a> ]
</span>"""

HTML_HEADER_BODY = "\n<pre>"

HTML_FOOTER = """</pre></body>
<script>
var old_highlight;

function remove_highlight() {
    if (old_highlight) {
        items = document.getElementsByClassName(old_highlight);
        for (var i = 0; i < items.length; i++) {
            items[i].className = items[i].className.replace('highlight','');
        }
    }
}

function update_selector(highlight) {
    var selector = document.getElementById('selector');
    if (selector) {
        var links = selector.getElementsByTagName('a');
        for (var i = 0; i < links.length; i++) {
            links[i].hash = "#" + highlight;
        }
    }
}

function highlight_by_hash(event) {
    var highlight = window.location.hash.substr(1);
    // handle changes to highlighting separate from reload
    if (event) {
         highlight = event.target.hash.substr(1);
    }
    remove_highlight();
    if (highlight) {
        elements = document.getElementsByClassName(highlight);
        for (var i = 0; i < elements.length; i++) {
            elements[i].className += " highlight";
        }
        update_selector(highlight);
        old_highlight = highlight;
    }
}
document.onclick = highlight_by_hash;
highlight_by_hash();
</script>
</html>
"""


DATE_LINE = ("<span class='%s %s'><a name='%s' class='date' href='#%s'>"
             "%s</a>%s\n</span>")
NONDATE_LINE = "<span class='%s'>%s\n</span>"
HTML_RE = re.compile("<(!doctype )?html", re.IGNORECASE)
SKIP_LINES = re.compile("</?pre>")

# pre tags mean we're partial html and shouldn't escape
NO_ESCAPE_START = re.compile("<pre>")
NO_ESCAPE_FINISH = re.compile("</pre>")


class HTMLView(collections.Iterable):
    headers = [('Content-type', 'text/html')]
    should_escape = True
    sent_header = False
    is_html = False
    no_escape_count = 0

    def __init__(self, gen):
        self.gen = gen

    def _discover_html(self, line):
        self.is_html = HTML_RE.match(line)
        if self.is_html:
            self.should_escape = False

    def _process_line(self, line):
        if NO_ESCAPE_START.match(line.line):
            # Disable escaping starting at this line
            self.should_escape = False
            # Count the number of times the escape has started in case there
            # are <pre> (or escape) blocks inside of each other
            self.no_escape_count += 1
        elif NO_ESCAPE_FINISH.match(line.line):
            # Check to see if we've exited the escape stack.
            self.no_escape_count -= 1
            if self.no_escape_count == 0:
                # Re-enable escaping starting at this line. ie we're done in
                # the escape free zone (eg outside of the pre tags again)
                self.should_escape = True

        if SKIP_LINES.match(line.line):
            return

        if self.should_escape:
            safeline = cgi.escape(line.line)
        else:
            safeline = line.line

        if line.date:
            safe_date = line.safe_date()
            newline = DATE_LINE % (line.status, safe_date, safe_date,
                                   safe_date, line.date, safeline)
        else:
            newline = NONDATE_LINE % (line.status, safeline)
        return newline

    def __iter__(self):
        igen = (x for x in self.gen)
        first_line = next(igen)
        self._discover_html(first_line.line)

        if not self.is_html:
            header = HTML_HEADER
            if self.gen.supports_sev:
                header += HTML_HEADER_SEV
            header += HTML_HEADER_BODY
            yield header

        first = self._process_line(first_line)
        if first:
            yield first

        for line in igen:
            newline = self._process_line(line)
            if newline:
                yield newline

        if not self.is_html:
            yield HTML_FOOTER


class TextView(collections.Iterable):
    headers = [('Content-type', 'text/plain')]

    def __init__(self, gen):
        self.gen = gen

    def __iter__(self):
        for line in self.gen:
            yield line.date + line.line + "\n"


class PassthroughView(collections.Iterable):
    headers = []

    def __init__(self, gen):
        self.gen = gen
        for hn, hv in self.gen.file_headers.items():
            self.headers.append((hn, hv))

    def __iter__(self):
        for line in self.gen:
            yield line
