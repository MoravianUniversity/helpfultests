import re
import io
import sys
import os.path
import itertools
import contextlib
import builtins
import types
import difflib
import unittest

from ._utils import _indent_lines, _indent_lines_maybe, _repr

__all__ = ['add_test_case_special_asserts']


def __bold(string, charcode='\u2060'):
    """
    Bolds a string using unicode. Only letters and digits are supported. All
    other characters are passed through unchanged except that all characters
    (ones changed or not) are prefixed with the zero-width word joiner unicode
    symbol \\u2060.
    """
    output = ''
    for ch in string:
        output += charcode
        x = ord(ch)
        if 48 <= x <= 57: # numbers
            output += chr(x+120812-48)
        elif 65 <= x <= 90: # uppercase
            output += chr(x+120276-65)
        elif 97 <= x <= 122: # lowercase
            output += chr(x+120302-97)
        else:
            output += ch
    return output

def __bold_substr(string, start, end):
    """
    Applies bolding with __bold() to a substring, returning the complete string.
    """
    return string[:start] + __bold(string[start:end]) + string[end:]

def __strikethrough(text, charcode='\u0334'):
    """
    Uses unicode combining characters to strikethrough an entire string. By
    default this uses the ~ symbol instead of - to reduce confusion when placed
    over a space. To use -, the second argument should be '\u0336'.
    """
    return ''.join(charcode + ch for ch in text)

def __underline(text, charcode='\u0333'):
    """
    Uses unicode combining characters to underline an entire string. By default
    this uses a double underscore instead of _ to reduce confusion when placed
    over a space. To use _, the second argument should be '\u0332'.
    """
    return ''.join(charcode + ch for ch in text)

def __call_to_str(func, args=(), kwargs={}): # pylint: disable=dangerous-default-value
    sep = ', ' if args and kwargs else ''
    args = ', '.join(repr(arg) for arg in args)
    kwargs = ', '.join(key + '=' + repr(value) for key, value in kwargs.items())
    return f"{func.__module__}.{func.__qualname__}({args}{sep}{kwargs})"

def _helpful_failure(self, msg):
    """
    Returns a `TestCase` failure exception with the given message. Also the extra attribute
    `helpful_msg` is set the message as well, resulting in it being literally printed out when
    using helpful tests.
    """
    ex = self.failureException(msg)
    ex.helpful_msg = msg
    return ex

def _raise_helpful_failure(self, msg):
    raise _helpful_failure(self, msg)

class redirect_stdin(contextlib._RedirectStream): # pylint: disable=protected-access, invalid-name
    """Equivalent to the contextlib.redirect_stdout() but for stdin."""
    _stream = 'stdin'

def _read_file(self, filename):
    dirname = os.path.dirname(sys.modules[self.__module__].__file__)
    with open(os.path.join(dirname, filename), 'r') as file:
        return file.read()

def __check_input(self, func, inpt, args=(), kwargs={}): # pylint: disable=dangerous-default-value
    msg = f"""The function call was: {__call_to_str(func, args, kwargs)}
The 'user' typed:\n{_indent_lines(inpt, 4)}\n"""

    # Prepare the simulated standard input and output
    # The input read() and readline() functions are wrapped so input also shows in the output
    out = io.StringIO()
    in_ = io.StringIO(inpt)
    inpt_ranges = [] # ranges in the output that are actually from the input
    def _read(*args, **kwargs):
        data = io.StringIO.read(in_, *args, **kwargs)
        inpt_ranges.append((len(out.getvalue()), len(data)))
        out.write(data)
        return data
    def _readline(*args, **kwargs):
        data = io.StringIO.readline(in_, *args, **kwargs)
        inpt_ranges.append((len(out.getvalue()), len(data)))
        out.write(data)
        return data
    in_.read = _read
    in_.readline = _readline

    # Call the function with the simulated stdin and stdout
    has_eof_err = False
    try:
        with contextlib.redirect_stdout(out), redirect_stdin(in_):
            retval = func(*args, **kwargs)
    except EOFError:
        has_eof_err = True

    # Check for EOF
    if has_eof_err:
        msg += 'You read all information given and then kept trying to get more input.'
        raise _helpful_failure(self, msg)

    # Check that all of the input was used
    if in_.tell() == 0:
        msg += 'You did not read any input at all.'
        raise _helpful_failure(self, msg)
    rem = in_.read()
    if rem:
        msg += 'Not all of that input was used, you stopped reading input once you got:\n'+(
            _indent_lines(inpt[:-len(rem)].rstrip('\n').split('\n')[-1], 4))
        raise _helpful_failure(self, msg)

    # Leave the rest to the assert function
    return msg, retval, out.getvalue().rstrip(), inpt_ranges

def __diff_line(a, b, limit=0.0):
    """
    Computes a line difference between the a and b strings (in theory they
    should be each a single line that is similar, but they can also be
    multiples lines each (using \n)).

    Returns a string with underlines where there should be insertions in a and
    strikethroughs for things that should be deleted from a.

    The third argument limit determines if a string should be analyzed or not.
    If not analyzed because too much of the line has been changed, then this
    will return None instead of the matching string. A value of 1.0 would make
    this always return None, a value of 0.0 makes this never return None.
    """
    out = ''
    matcher = difflib.SequenceMatcher(a=a, b=b)
    if limit > 0 and limit >= matcher.ratio():
        return None
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag =='equal':
            out += a[i1:i2]
        elif tag == 'delete':
            out += __strikethrough(a[i1:i2])
        elif tag == 'insert':
            out += __underline(b[j1:j2])
        elif tag == 'replace':
            out += __strikethrough(a[i1:i2])
            out += __underline(b[j1:j2])
    return out

def __diff_lines(a, b):
    """
    Computes the difference between the a and b list-of-strings with each string
    being one line. This finds equal sections of the lists and the parts that
    need editing are run through __diff_line individually.

    Returns a string with underlines where there should be insertions in a and
    strikethroughs for things that should be deleted from a. The returned result
    is a list of strings.
    """
    out = []
    matcher = difflib.SequenceMatcher(a=a, b=b)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag =='equal':
            out.extend(a[i1:i2])
        elif tag == 'delete':
            out.extend(__strikethrough(a[i]) for i in range(i1, i2))
        elif tag == 'insert':
            out.extend(__underline(b[j]) for j in range(j1, j2))
        elif tag == 'replace':
            for a_line, b_line in zip(a[i1:i2], b[j1:j2]):
                if (diff := __diff_line(a_line, b_line, 0.5)) is None:
                    # TODO: group some of these lines together?
                    out.append(__strikethrough(a_line))
                    out.append(__underline(b_line))
                else:
                    out.append(diff)
            for i in range(i1 + j2-j1, i2): out.append(__strikethrough(a[i]))
            for j in range(j1 + i2-i1, j2): out.append(__underline(b[j]))
    return out

def __check_output(self, msg, printed, inpt_ranges, expected,
                   _whitespace='relaxed', _ordered=True, _regexp=False):
    printed_orig = printed
    # TODO: compare without input ranges or add input to expected
    #for start, length in inpt_ranges:
    #    printed = printed[:start] + printed[start+length:]
    expected_orig = expected
    if _whitespace == 'relaxed':
        printed = '\n'.join(line.rstrip() for line in printed_orig.rstrip('\n').split('\n'))
        expected = '\n'.join(line.rstrip() for line in expected.rstrip('\n').split('\n'))
    elif _whitespace == 'ignore':
        printed = ''.join(printed_orig.split())
        expected = ''.join(expected.split())
    elif _whitespace == 'strict':
        printed = printed_orig

    if not _ordered or not _regexp:
        printed = printed.split('\n')
        expected = expected.split('\n')

    if not _ordered:
        printed.sort()
        expected.sort()

    if not _regexp:
        mismatch = printed != expected
    elif isinstance(printed, list):
        mismatch = any(re.search(e, p) is None for e, p in zip(expected, printed))
    else:
        mismatch = re.search(expected, printed) is None
    if mismatch:
        single_line = '\n' not in expected_orig and '\n' not in printed_orig
        expected_note = actual_note = ''
        if _regexp:
            expected_note = ' (this is a regular-expression, so will likely look cryptic)'
        if inpt_ranges:
            for start, length in inpt_ranges:
                printed_orig = __bold_substr(printed_orig, start, start+length)
            actual_note = ' (green text is user entered)'
        msg += f'''Expected output{expected_note}: {_indent_lines_maybe(expected_orig, 4, single_line)}'''
        msg += f'''\nActual output{actual_note}: {_indent_lines_maybe(printed_orig, 4, single_line)}'''
        if not _regexp and _whitespace != 'ignore':
            # diffs not supported for whitespace='ignore' or _regexp
            # TODO: support whitespace='ignore'
            if single_line:
                diff = __diff_line(printed[0], expected[0])
            else:
                diff = '\n'.join(__diff_lines(printed, expected))
            msg += '\nDifference (\u0333  are things your output is missing, \u0334  are things your output has extra):\n'
            msg += _indent_lines(diff, 4)

        if _whitespace == 'ignore': msg += '\nNote: all whitespace is ignored'
        if not _ordered: msg += '\nNote: order of the lines does not matter'

        raise _helpful_failure(self, msg)

def _assertOutputEqual(self, expected, func, *args,
                       _whitespace='relaxed', _ordered=True, _regexp=False, **kwargs):
    """
    Assert that the output (written to stdout) equals the expected output. The function object must
    be passed in (not already called). If it takes arguments, they can be passed in the args and
    kwargs arguments.

    Optionally, the _whitespace keyword argument can be given to determine how whitespace is
    compared. It can be either 'strict' (whitespace must be exactly equal), 'relaxed' (the default,
    trailing whitespace on each line is ignored), or 'ignore' (all whitespace is ignored).

    The optional _ordered keyword can be given as False to cause the order of the lines to not
    matter when checking the output. This is not compatible with ignoring the whitespace.

    The optional _regexp keyword can be given as True to cause the `expected` argument to be
    treated as as a regular expression during matching.

    Not all combinations of keyword arguments will produce reasonable results. Specifically,
    when using _ordered=False with _regexp=True or _whitespace='ignore'.
    """
    msg = f"The function call was: {__call_to_str(func, args, kwargs)}\n"
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        retval = func(*args, **kwargs)
    __check_output(self, msg, out.getvalue(), (), expected, _whitespace, _ordered, _regexp)
    return retval

def _assertOutputEqualUsingUserInput(self, inpt, output, func, *args,
                                     _whitespace='relaxed', _ordered=True, _regexp=False, **kwargs):
    """
    Assert that the output (written to stdout) equals the expected output. The function object must
    be passed in (not already called). If it takes arguments, they can be passed in the args and
    kwargs arguments. Additionally, the function grabs user input (from stdin) and this is checked
    for as well. The input is given in the inpt argument and is added to the printed output.

    The optional _whitespace, _ordered, and _regexp keyword arguments are treated as per
    assertOutputEqual().
    """
    msg, retval, out, inpt_ranges = __check_input(self, func, inpt, args, kwargs)
    __check_output(self, msg, out, inpt_ranges, output, _whitespace, _ordered, _regexp)
    return retval

def _assertEqualUsingUserInput(self, inpt, expected, func, *args, _must_output_args=True, **kwargs):
    """
    Assert that the return value is equal when calling the function with the given arguments and
    keyword arguments along with providing the given input to stdin to be read in. It makes sure
    that all of the input is read. By default you also makes sure that provided arguments also
    show up in the output, but settings _must_output_args=False this will not be checked.
    """
    # Call the function and deal with input checks
    msg, retval, out, _ = __check_input(self, func, inpt, args, kwargs)

    # Check that the return value is correct
    if retval != expected:
        msg += f'Expected return value: {_repr(expected)}\nActual return value:   {_repr(retval)}'
        raise _helpful_failure(self, msg)

    # Check that all the pieces of text showed up in the output
    if _must_output_args:
        for arg in itertools.chain(args, kwargs.values()):
            if isinstance(arg, str):
                if arg not in out:
                    msg += f'The argument value "{arg}" was supposed to appear in the output.\n'
                    msg += f'The actual output was:\n{_indent_lines(out, 4)}'
                    raise _helpful_failure(self, msg)

@contextlib.contextmanager
def _assertNoPrint(self, print_func_okay=False, msg="You are not allowed to use print(), instead use return values"):
    """
    Context manager that raises an assert error if print() is called (with any file) or if
    sys.stdout is written to from any source. Used like:

    with self.assertNoPrint():
        pass # code to run that should never print() or write to stdout
    """
    orig_print = builtins.print
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        try:
            if not print_func_okay:
                builtins.print = lambda *args, **kwargs: _raise_helpful_failure(self, msg)
            yield None
        finally:
            builtins.print = orig_print
            if output.getvalue(): raise _helpful_failure(self, msg)

@contextlib.contextmanager
def _assertNoInput(self, msg="You are not allowed to use input(), instead use parameters"):
    """
    Context manager that raises an assert error if input() is called or if sys.stdin is read from
    by any source. Has the side effect that this will suppress any EOFError exceptions. Used like:

    with self.assertNoInput():
        pass # code to run that should never input() or read from stdin
    """
    orig_input = builtins.input
    with redirect_stdin(io.StringIO()):
        try:
            builtins.input = lambda prompt="": _raise_helpful_failure(self, msg)
            yield None
        except EOFError:
            raise _helpful_failure(self, msg)
        finally:
            builtins.input = orig_input

def _assertDoc(self, func, min_length=16):
    """
    Asserts that the given module of function has a docstring of at least the given length.
    """
    name = func.__name__ if isinstance(func, types.ModuleType) else f"{func.__name__}()"
    doc = getattr(func, '__doc__', None)
    if doc is None:
        raise _helpful_failure(self, f"No docstring provided for {name}")
    if len(doc.strip()) < min_length:
        raise _helpful_failure(self, f"Docstring for {name} isn't very descriptive...")

def add_test_case_special_asserts():
    """
    Adds several additional assert*() methods to the unittest.TestCase class:
      * assertDoc
      * assertOutputEqual
      * assertEqualUsingUserInput
      * assertOutputEqualUsingUserInput
      * assertNoPrint  (context manager)
      * assertNoInput  (context manager)
    And utility methods:
      * helpful_failure
      * read_file
    """
    unittest.TestCase.read_file = _read_file
    unittest.TestCase.helpful_failure = _helpful_failure
    unittest.TestCase.assertOutputEqual = _assertOutputEqual
    unittest.TestCase.assertEqualUsingUserInput = _assertEqualUsingUserInput
    unittest.TestCase.assertOutputEqualUsingUserInput = _assertOutputEqualUsingUserInput
    unittest.TestCase.assertNoPrint = _assertNoPrint
    unittest.TestCase.assertNoInput = _assertNoInput
    unittest.TestCase.assertDoc = _assertDoc
