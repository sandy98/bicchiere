#-*- coding: utf-8 -*-

import re
from io import StringIO

re
StringIO

class CodeBuilder:
    """Build source code conveniently."""

    def __init__(self, indent=0):
        self.code = []
        self.indent_level = indent

    def add_line(self, line):
        """Add a line of source to the code.
        Indentation and newline will be added for you, don't provide them.
        """
        self.code.extend([" " * self.indent_level, line, "\n"])

    INDENT_STEP = 4      # PEP8 says so!

    def indent(self):
        """Increase the current indent for following lines."""
        self.indent_level += self.INDENT_STEP

    def dedent(self):
        """Decrease the current indent for following lines."""
        self.indent_level -= self.INDENT_STEP

    def add_section(self):
        """Add a section, a sub-CodeBuilder."""
        section = CodeBuilder(self.indent_level)
        self.code.append(section)
        return section

    def __str__(self):
        return "".join(str(c) for c in self.code)

    def get_globals(self):
        """Execute the code, and return a dict of globals it defines."""
        # A check that the caller really finished all the blocks they started.
        assert self.indent_level == 0
        # Get the Python source as a single string.
        python_source = str(self)
        # Execute the source, defining globals, and return them.
        global_namespace = {}
        exec(python_source, global_namespace)
        return global_namespace

class TemplateSyntaxError(BaseException):
    pass

class TemplateLight:
    def __init__(self, text, *contexts):
        """Construct a Templite with the given `text`.
        `contexts` are dictionaries of values to use for future renderings.
        These are good for filters and global values.
        """
        self.context = {}
        for context in contexts:
            self.context.update(context)
        self.all_vars = set()
        self.loop_vars = set()

        code = CodeBuilder()
        code.add_line("def render_function(context, do_dots):")
        code.indent()
        vars_code = code.add_section()
        code.add_line("result = []")
        code.add_line("append_result = result.append")
        code.add_line("extend_result = result.extend")
        code.add_line("to_str = str")

        buffered = []

        def flush_output():
            """Force `buffered` to the code builder."""
            if len(buffered) == 1:
                code.add_line("append_result(%s)" % buffered[0])
            elif len(buffered) > 1:
                code.add_line("extend_result([%s])" % ", ".join(buffered))
            del buffered[:]

        ops_stack = []

        tokens = re.split(r"(?s)({{.*?}}|{%.*?%}|{#.*?#})", text)

        for token in tokens:
            if token.startswith('{#'):
                # Comment: ignore it and move on.
                continue
            elif token.startswith('{{'):
                # An expression to evaluate.
                expr = self._expr_code(token[2:-2].strip())
                buffered.append("to_str({0})".format(expr))
            elif token.startswith('{%'):
                # Action tag: split into words and parse further.
                flush_output()
                words = token[2:-2].strip().split()
                if words[0] == 'if':
                    # An if statement: evaluate the expression to determine if.
                    if len(words) != 2:
                        self._syntax_error("Don't understand if", token)
                    ops_stack.append('if')
                    code.add_line("if {0}:".format(self._expr_code(words[1])))
                    code.indent()
                elif words[0] == 'for':
                    # A loop: iterate over expression result.
                    if len(words) != 4 or words[2] != 'in':
                        self._syntax_error("Don't understand for", token)
                    ops_stack.append('for')
                    self._variable(words[1], self.loop_vars)
                    code.add_line(
                        "for c_{0} in {1}:".format(
                            words[1],
                            self._expr_code(words[3])
                        )
                    )
                    code.indent()
                elif words[0].startswith('end'):
                    # Endsomething.  Pop the ops stack.
                    if len(words) != 1:
                        self._syntax_error("Don't understand end", token)
                    end_what = words[0][3:]
                    if not ops_stack:
                        self._syntax_error("Too many ends", token)
                    start_what = ops_stack.pop()
                    if start_what != end_what:
                        self._syntax_error("Mismatched end tag", end_what)
                    code.dedent()
                else:
                    self._syntax_error("Don't understand tag", words[0])
            else:
                # Literal content.  If it isn't empty, output it.
                if token:
                    buffered.append(repr(token))

        if ops_stack:
            self._syntax_error("Unmatched action tag", ops_stack[-1])

        flush_output()

        for var_name in self.all_vars - self.loop_vars:
            vars_code.add_line("c_%s = context[%r]" % (var_name, var_name))

        code.add_line("return ''.join(result)")
        code.dedent()

        self._render_function = code.get_globals()['render_function']



    def _variable(self, name, vars_set):
        """Track that `name` is used as a variable.
        Adds the name to `vars_set`, a set of variable names.
        Raises an syntax error if `name` is not a valid name.
        """
        if not re.match(r"[_a-zA-Z][_a-zA-Z0-9]*$", name):
            self._syntax_error("Not a valid name", name)
        vars_set.add(name)

    def _expr_code(self, expr):
        """Generate a Python expression for `expr`."""
        if "|" in expr:
            pipes = expr.split("|")
            code = self._expr_code(pipes[0])
            for func in pipes[1:]:
                self._variable(func, self.all_vars)
                code = "c_%s(%s)" % (func, code)
        elif "." in expr:
            dots = expr.split(".")
            code = self._expr_code(dots[0])
            args = ", ".join(repr(d) for d in dots[1:])
            code = "do_dots(%s, %s)" % (code, args)
        else:
            self._variable(expr, self.all_vars)
            code = "c_%s" % expr
        return code

    def _syntax_error(self, msg, thing):
        """Raise a syntax error using `msg`, and showing `thing`."""
        raise TemplateSyntaxError("%s: %r" % (msg, thing))

    def _do_dots(self, value, *dots):
        """Evaluate dotted expressions at runtime."""
        for dot in dots:
            try:
                value = getattr(value, dot)
            except AttributeError:
                value = value[dot]
            if callable(value):
                value = value()
        return value

    def render(self, **context):
        """Render this template by applying it to `context`.
        `context` is a dictionary of values to use in this rendering.
        """
        # Make the complete context we'll use.
        render_context = dict(self.context)
        if context:
            render_context.update(context)
        return self._render_function(render_context, self._do_dots)

#{0}

testl = TemplateLight("<p> Hello, {{ user  }}!! ̣</p")

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
        <div>Hello,  {{ user }}! </div>
    {% endfor %}
</body>
</html>
"""

test2 = TemplateLight(bare_bones)

html = test2.render(pt = 'MASSIVE PAGE TITLE', users = ['Sol', 'Cele', 'Jorge'])

if __name__ == '__main__':
    print(html)
