"""
Wrappers for the TestCase.assert* functions to add helpful_msg attributes to the raised assertions
so that the error messages are more helpful.

The following functions are not wrapped at the moment:
    assertRegex, assertNotRegex
    assertRaises, assertRaisesRegex
    assertWarns, assertWarnsRegex
    assertLogs

Also IsInstance and IsNotInstance do not support a function call as the second argument (they will
report the original error message in that case).
"""

import os.path
import sys
import ast
from unittest import TestCase

from astor.code_gen import to_source

__all__ = ['wrap_test_case_asserts']


def __indent_lines(string, spaces):
    if string == '': return string
    spaces = ' '*spaces
    return spaces + ('\n'+spaces).join(string.splitlines())

def __get_line_of_code(filename, line_num):
    # TODO: any wrapped lines of code need to be discovered
    with open(filename, 'r') as file:
        return file.readlines()[line_num-1]

def __get_verbose_code_from_frame(frame, desc='The test'):
    filename = frame.f_code.co_filename
    line_num = frame.f_lineno
    func_name = frame.f_code.co_name
    return '%s was in %s on line %d in %s():\n    %s'%(
        desc, os.path.basename(filename), line_num, func_name,
        __get_line_of_code(filename, line_num).strip()) # TODO: deal with multi-line code

def __get_ast_node_from_frame(frame):
    filename = frame.f_code.co_filename
    line_num = frame.f_lineno
    with open(filename) as file:
        code = ast.parse(file.read(), filename=filename)
    for node in ast.walk(code):
        if hasattr(node, 'lineno') and \
            node.lineno <= line_num <= getattr(node, 'end_lineno', node.lineno):
            return node
    return None

def __is_value(node):
    return isinstance(node, (ast.Num, ast.Str, ast.Bytes, ast.NameConstant, ast.Ellipsis,
                             ast.Attribute, ast.Name,
                             ast.List, ast.Tuple, ast.Set, ast.Dict, ast.Subscript))

def __extract_from_assert_call(node, max_check=2):
    if not (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)): return None, -1
    func, args = node.value.func, node.value.args
    if not (isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and
            func.value.id == 'self' and func.attr.startswith('assert')): return None, -1
    if isinstance(args[0], ast.Call) and __is_value(args[1]):
        return to_source(args[0]).strip(), 0
    if max_check > 1 and isinstance(args[1], ast.Call) and __is_value(args[0]):
        return to_source(args[1]).strip(), 1
    return None, -1

def __repr(x, force_long=False): # pylint: disable=invalid-name
    x = x if not force_long and isinstance(x, str) and '\n' in x and len(x) < 20 else repr(x)
    return ('\n' + __indent_lines(x, 4)) if '\n' in x or len(x) > 20 else x

def __add_helpful_msg(name, ex, *args, **kwargs):
    frame = sys._getframe().f_back.f_back # pylint: disable=protected-access
    code = __get_verbose_code_from_frame(frame)
    node = __get_ast_node_from_frame(frame)

    msg = code + '\n'
    if name not in __NO_FUNC_CALL:
        call, index = __extract_from_assert_call(node, __NUM_ARGS.get(name, 2))
        if call is not None:
            msg += 'The function call was: ' + call + '\n'

    values = {}
    if __NUM_ARGS.get(name, 2) == 1: # True, False, IsNone, and IsNotNone
        values['actual'] = args[0]
        #values['expected'] = not needed
    else:
        if index == 0:
            values['actual'] = args[0]
            values['expected'] = args[1]
            if name in ('Greater', 'GreaterEqual', 'Less', 'LessEqual'):
                # TODO: this may actually result in more confusion
                name = {'Greater':'LessEqual', 'LessEqual':'Greater',
                        'GreaterEqual':'Less', 'Less':'GreaterEqual'}[name]
        else:
            values['expected'] = args[0]
            values['actual'] = args[1]

        # Special cases that need to be handled
        if name in ('AlmostEqual', 'NotAlmostEqual'):
            if len(args) == 2 or args[2] is not None or kwargs.get('places', None) is not None:
                values['places'] = places = kwargs.get('places', args[2] if len(args) > 2 else 7)
                values['actual'] = round(values['actual'], places)
                values['expected'] = round(values['expected'], places)
            else:
                values['delta'] = args[4] if kwargs.get('delta', None) is None else kwargs['delta']
                name += 'Delta'

        if name in ('Is', 'IsNot'):
            values['expected_id'] = id(values['expected'])
            values['actual_id'] = id(values['actual'])

        if name in ('IsInstance', 'IsNotInstance'):
            if index != 0: return # not supported in reverse
            values['actual_type'] = type(values['actual']).__name__
            if isinstance(values['expected'], type):
                values['expected'] = values['expected'].__name__
            else:
                values['expected'] = tuple(cls.__name__ for cls in values['expected'])

        if name in ('In', 'NotIn'):
            pass
            # TODO: in some cases switch to (Not)Contains, also deal with naming of variables

    for attr in ('actual', 'expected'):
        if attr in values: values[attr] = __repr(values[attr])
    msg += __TEMPLATES[name].format(**values)
    ex.helpful_msg = msg

__NUM_ARGS = {
    # Number of args before 'msg' argument; if not listed it is 2 that are 'first', 'second'
    'True': 1, 'False': 1, 'IsNone': 1, 'IsNotNone': 1,
    'AlmostEqual': 3, 'NotAlmostEqual': 3,
}

__NO_FUNC_CALL = {'In', 'NotIn'}

__TEMPLATES = {
    # pylint: disable=line-too-long
    'Equal': 'Expected return value: {expected}\nActual return value:   {actual}',
    'NotEqual': 'Expected return value to *not* be: {expected}\nActual return value: {actual}',

    'Greater': 'Expected return value to be greater than: {expected}\nActual return value: {actual}',
    'GreaterEqual': 'Expected return value to be greater than or equal to: {expected}\nActual return value: {actual}',
    'Less': 'Expected return value to be less than: {expected}\nActual return value: {actual}',
    'LessEqual': 'Expected return value to be less than or equal to: {expected}\nActual return value: {actual}',

    'AlmostEqual':'Expected return value: {expected} once rounded to {places} places\n'+
                  'Actual return value:   {actual} once rounded to {places} places',
    'NotAlmostEqual':'Expected return value to *not* be: {expected} once rounded to {places} places\n'+
                     'Actual return value: {actual} once rounded to {places} places',
    'AlmostEqualDelta':'Expected return value: {expected}±{delta}\nActual return value:   {actual}',
    'NotAlmostEqualDelta':'Expected return value to *not* be: {expected}±{delta}\n'+
                          'Actual return value: {actual}',

    'True': 'Expected return value to be True but was: {actual}',
    'False': 'Expected return value to be False but was: {actual}',
    'IsNone': 'Expected return value to be None but was: {actual}',
    'IsNotNone': 'Expected return value to *not* be None but was: {actual}',

    'Is': 'Expected return value: {expected} with id {expected_id}\n'+
          'Actual return value:   {actual} with id {actual_id}',
    'IsNot': 'Expected return value to *not* be: {actual} with id {actual_id}',

    'IsInstance': 'Expected return value to have type {expected}\n'+
                  'Actual return value:   {actual} has type {actual_type}',
    'NotIsInstance': 'Expected return value to *not* have type {expected}\n'+
                     'Actual return value: {actual} has type {actual_type}',

    'In': 'Expected return value to be in: {second}\nActual return value: {first}',
    'NotIn': 'Expected return value to *not* be in: {second}\nActual return value: {first}',
    'Contains': 'Expected return value to contain: {first}\nActual return value: {second}',
    'NotContains': 'Expected return value to *not* contain: {first}\nActual return value: {second}',
}

__ASSERT = {}

"""
assertMultiLineEqual(self, first, second, msg=None)
assertSequenceEqual(self, first, second, msg=None, seq_type=None)
assertListEqual(self, first, second, msg=None)
assertTupleEqual(self, first, second, msg=None)
assertSetEqual(self, first, second, msg=None)
assertDictEqual(self, first, second, msg=None)
assertCountEqual(self, first, second, msg=None)
"""

def __make_assert_function(name):
    def __assert_wrapper(self, *args, **kwargs):
        try:
            __ASSERT[name](self, *args, **kwargs)
        except AssertionError as ex:
            n = __NUM_ARGS.get(name, 2)
            if kwargs.get('msg', None) is None and (len(args) <= n or args[n] is None):
                __add_helpful_msg(name, ex, *args, **kwargs)
            raise
    return __assert_wrapper

def wrap_test_case_asserts():
    """
    Wraps the assert functions of the unittest.TestCase class to provide different error messages.
    """
    for name in __TEMPLATES:
        fullname = 'assert' + name
        if not hasattr(TestCase, fullname): continue
        __ASSERT[name] = getattr(TestCase, fullname)
        setattr(TestCase, fullname, __make_assert_function(name))
