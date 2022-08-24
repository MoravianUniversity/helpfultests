import io
import os
import contextlib
import unittest
import warnings

from .helpfultests import HelpfulTestRunner, timeout, Timeout, _print_import_error
from ._testcase_assert_mod import wrap_test_case_asserts
from ._testcase_assert_add import add_test_case_special_asserts, _assertNoPrint, _assertNoInput

def __styling(ch, last_ch, marker, current, start, end):
    if ch == marker:
        return '' if current else start, True
    elif current and last_ch != marker:
        return end + ch, False
    else:
        return ch, current

def __convert_to_html(text):
    #with contextlib.redirect_stdout(output), contextlib.redirect_stdout(output):

    # Note that none of the modes (bold, underline, strikethrough) can be nested
    ch_map = {'\n': '<br>', '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;', "'": '&apos;'}
    ins_ = '<ins style="text-decoration:underline;background-color:#d4fcbc;">' 
    del_ = '<del style="text-decoration:line-through;background-color:#fbb;color:#555;">'
    b_ = '<b style="font-style:italic;font-weight:bolder;color:green;">'
    output = '<pre>'
    bolding = underlining = strikethrough = False
    last_ch = ''
    for raw_ch in text:
        ch = raw_ch
        if ch in ch_map:
            ch = ch_map[ch]
        else:
            # de-bold the character
            x = ord(ch)
            if   120812 <= x < 120812+10: ch = chr(x-120812+48) # numbers
            elif 120276 <= x < 120276+26: ch = chr(x-120276+65) # uppercase
            elif 120302 <= x < 120302+26: ch = chr(x-120302+97) # lowercase
        ch, bolding = __styling(ch, last_ch, '\u2060', bolding, b_, '</b>')
        ch, underlining = __styling(ch, last_ch, '\u0333', underlining, ins_, '</ins>')
        ch, strikethrough = __styling(ch, last_ch, '\u0334', strikethrough, del_, '</del>')
        output += ch
        last_ch = raw_ch
    if bolding: output += '</b>'
    if underlining: output += '</ins>'
    if strikethrough: output += '</del>'
    output += '</pre>'
    return output


def main():
    # TODO: needs lots of work (arguments, return code, ...)
    wrap_test_case_asserts()
    add_test_case_special_asserts()

    # Discover the tests but also do some checks since they will be imported
    tc = unittest.TestCase()
    msg = "🤐 You are not allowed to use print() or input() at the top level, everything must be in functions"
    try:
        with warnings.catch_warnings(), timeout(1), _assertNoPrint(tc, msg=msg), _assertNoInput(tc, msg=msg):
            tests = unittest.defaultTestLoader.discover(os.getcwd(), '[!_]*.py')
    except ImportError as ex:
        _print_import_error(ex)
        return
    except AssertionError as ex:
        print(getattr(ex, 'helpful_msg', str(ex)))
        return
    except Timeout as ex:
        print('⌛ Took too long to import, you shouldn\'t have any code not in functions\n')
        return

    # Assume these are fine
    instructor_tests = unittest.defaultTestLoader.discover(os.getcwd(), '_*.py')

    # Run the unittests
    output = io.StringIO()
    try:
        with contextlib.redirect_stdout(output):
            HelpfulTestRunner().run(unittest.TestSuite((tests, instructor_tests)))
    finally:
        print(__convert_to_html(output.getvalue()))

if __name__ == "__main__":
    main()
