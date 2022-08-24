import os.path
import ast

def _indent_lines(string, spaces):
    if string == '': return string
    spaces = ' '*spaces
    return spaces + ('\n'+spaces).join(string.splitlines())

def _indent_lines_maybe(string, spaces, no):
    return string if no else ('\n' + _indent_lines(string, spaces))

def _repr(x, force_long=False): # pylint: disable=invalid-name
    x = x if not force_long and isinstance(x, str) and '\n' in x and len(x) < 20 else repr(x)
    return ('\n' + _indent_lines(x, 4)) if '\n' in x or len(x) > 20 else x

def _get_line_of_code(filename, line_num):
    # TODO: any wrapped lines of code need to be discovered
    with open(filename, 'r') as file:
        return file.readlines()[line_num-1]

def _get_verbose_code_from_frame(frame, desc='The test'):
    filename = frame.f_code.co_filename
    line_num = frame.f_lineno
    func_name = frame.f_code.co_name
    return '%s was in %s on line %d in %s():\n    %s'%(
        desc, os.path.basename(filename), line_num, func_name,
        _get_line_of_code(filename, line_num).strip()) # TODO: deal with multi-line code

def _get_verbose_code_from_tb(traceback, desc='The test'):
    filename = traceback.tb_frame.f_code.co_filename
    line_num = traceback.tb_lineno
    func_name = traceback.tb_frame.f_code.co_name
    return f'{desc} was in {os.path.basename(filename)} on line {line_num} in {func_name}()\n' + \
        _get_line_of_code(filename, line_num).strip() # TODO: deal with multi-line code

def _get_ast_node_from_frame(frame):
    filename = frame.f_code.co_filename
    line_num = frame.f_lineno
    with open(filename) as file:
        code = ast.parse(file.read(), filename=filename)
    for node in ast.walk(code):
        if hasattr(node, 'lineno') and \
            node.lineno <= line_num <= getattr(node, 'end_lineno', node.lineno):
            return node
    return None
