#-*- coding: utf-8 -*-

import re
from io import StringIO

simple_html = "<p> Hello,{{ user  }} ̣</p>"

bare_bones = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title> {{ pt }} </title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0, shrink-to-fit=no">
    <!--[if lt IE9]><script src="js/html5shiv-printshiv.js" media="all"></script><![endif]-->
</head>
<body>
    <!-- This is a VERY bare bones version of a HTML5 template! -->
    {% for user in users %}
        <div>Hello,  {{ user }} </div>
    {% endfor %}
</body>
</html>
"""

class Template_Compiler():
    def __init__(self):
        self.indent_level = 0
        self.lines = []
        self.states = ['reading', 'if', 'elif', 'else', 'for']
        self.curr_state = self.prev_state = 'reading'

    def indent(self): 
        self.indent_level += 4

    def dedent(self): 
        self.indent_level -= 4

    def spaces(self):
        return " " * self.indent_level

    def __call__(self, tpl_str):
        self.lines.append(f"""{self.spaces()}def render_tpl(**kw):\n""")
        self.indent()
        self.lines.append(f"""{self.spaces()}resp = []\n""")

        tpl_stringio = StringIO(tpl_str) 
        tpl_lines = tpl_stringio.readlines()

        for line in tpl_lines:
            stripline = line.strip()
            if stripline.startswith('{%'):
                pass
            else:
                stripline = re.sub(r'{{\s*', '{', stripline) 
                stripline = re.sub(r'\s*}}', '}', stripline) 
                appendstr = "'" + stripline + "'" 
                self.lines.append(f"""{self.spaces()}resp.append({appendstr})\n""")

        
        self.lines.append(f"""{self.spaces()}return chr(10).join(resp).format(**kw)""")

        funcstr = ''.join(self.lines)
        glbls = {}
        exec(funcstr, glbls)
        func = glbls['render_tpl']
        return func

def _compile_template(tpl_str):
    return Template_Compiler()(tpl_str)

simple_compiler = _compile_template(simple_html)

