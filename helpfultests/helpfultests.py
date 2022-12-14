"""
Unittest framework for intro CS course. This provides extremely easy to read error messages for the
failures and errors generated by the unittest framework included with Python.

It also adds a few other features including having a timeout on the execution of code.
"""

import re
import os.path
import warnings
import signal
import unittest
import ast

from ._utils import _get_verbose_code_from_tb

class Timeout(RuntimeError):
    """Exception raised when a timeout occurs."""

class timeout: # pylint: disable=invalid-name
    """
    Context manager that raises a Timeout exception if the context (i.e. with statement) is not
    exited before the timeout occurs. If the Timeout is caught but the context is not exited, it
    will be continually be generated again every timeout iteration.
    """
    def __init__(self, seconds):
        self.seconds = seconds

    def __handle_timeout(self, signum, frame):
        """Called when a timeout occurs"""
        raise Timeout(f'test timed out after {self.seconds}s.')

    def __enter__(self):
        """Turns on the alarm timer which will call __handle_timeout"""
        signal.signal(signal.SIGALRM, self.__handle_timeout)
        signal.setitimer(signal.ITIMER_REAL, self.seconds, self.seconds)

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Turns off the alarm timer"""
        signal.setitimer(signal.ITIMER_REAL, 0, self.seconds)

def _skip_unittest_frames(traceback):
    while traceback is not None and '__unittest' in traceback.tb_frame.f_globals:
        traceback = traceback.tb_next
    return traceback

def _print_import_error(ex):
    msg = str(ex).splitlines()
    if msg[-1].startswith("SyntaxError") or msg[-1].startswith("IndentationError"):
        err = 'a syntax' if msg[-1].startswith("SyntaxError") else 'an indentation'
        filename, line_num = re.search(r'"([^"]+?.py)", line (\d+)', msg[-4]).groups()
        line_num = int(line_num)
        print(f'😞 Your code has {err} error on line {line_num} of {os.path.basename(filename)}')
        print(f'   {msg[-3]}\n   {msg[-2]}')
    elif msg[-1].startswith("EOFError"):
        print("😞 Your code has input() calls at the top level, all of your code must be in functions.")
    else:
        print("😞 Your code failed to import for an unknown reason.")
        print()
        print('\n'.join(msg))


class HelpfulTestResult(unittest.TestResult):
    """
    The TestResult collector object for helpful unittesting framework. Keeps track of a few extra
    things that the original TestResult doesn't.
    """
    def __init__(self):
        super().__init__()
        self.successes = []
        self.helpful_failures = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.successes.append(test)

    def addFailure(self, test, err):
        super().addFailure(test, err)
        _, value, _ = err
        # type should always be a subclass of AssertionError using the default setup
        self.helpful_failures.append((test, getattr(value, 'helpful_msg', self.failures[-1][1])))

    def addError(self, test, err):
        super().addError(test, err)
        if issubclass(err[0], ImportError):
            raise err[1] # just pass it up along to the test runner who will deal with it
        if issubclass(err[0], Timeout):
            msg = '⌛ Took too long to run, perhaps you have an infinite loop or an extra input() call?\n'
            traceback = _skip_unittest_frames(err[2])
            msg += _get_verbose_code_from_tb(traceback) + '\n'
            # TODO: make sure this stays in student's code
            while (traceback.tb_next is not None and
                   traceback.tb_next.tb_frame.f_code.co_filename != __file__):
                traceback = traceback.tb_next
            msg += _get_verbose_code_from_tb(traceback, 'The line of code running')
            self.errors[-1] = (test, msg)

class HelpfulTestRunner:
    """
    The Helpful Testing framework Test Runner - implements the single method run() that is required
    for Python's unittest module.
    """
    def run(self, testcase):
        """
        The main run() for the Helpful Testing Framework. Uses HelpfulTestResults to accumulate
        results and the timeout class to restrict the amount of time for any particular test.
        """
        result = HelpfulTestResult()
        #registerResult(result)

        # Run the tests
        with warnings.catch_warnings(), timeout(1):
            result.startTestRun()
            try:
                testcase(result)
            except ImportError as ex:
                _print_import_error(ex)
                return result
            finally:
                result.stopTestRun()

        if result.wasSuccessful():
            print("🙂 All tests passed successfully!")
        else:
            print("🙁 Your code did not pass all of the tests.")
        print()

        for msg, lst in (
                ('Succeeded: %d', result.successes),
                ('Skipped: %d (incomplete extra credit or alternate options)', result.skipped)
            ):
            if lst:
                print(msg % len(lst))
                for test in lst:
                    if isinstance(test, tuple): test = test[0]
                    print(f'  {HelpfulTestRunner.get_test_name(test)}')
                print()

        for msg, lst in (
                ("Failed: %d (your code didn't return/output the expected value)",
                 result.helpful_failures),
                ('Errored: %d (your code crashed during the test)', result.errors)
            ):
            if lst:
                print('='*75)
                print()
                print(msg % len(lst))
                print()
                for test, exc in lst:
                    print(f'  {HelpfulTestRunner.get_test_name(test)}:')
                    print('    ' + ("\n    ".join(exc.splitlines())))
                    
        return result

    @staticmethod
    def get_test_name(test):
        """
        Gets the name of a test including it's class, method, and any short description proviced.
        """
        # pylint: disable=protected-access
        name = f'{test.__class__.__name__}.{test._testMethodName}'
        desc = test.shortDescription()
        return f'{name}\n{desc}' if desc else name

def __has_doc(body):
    return isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Str)

def check_module_structure(name, require_doc=False, forbid_useless_pass=False):
    """
    Makes sure that a module only contains a single string at the very beginning (for
    documentation), optional imports after that, optional assignment statements after that,
    function definitions, and then a single if at the very end.

    Optionally can also check that every function has documentation and that there are no pass
    statements directly inside functions that have other code.
    """
    filename = name + '.py' # TODO
    with open(filename) as file:
        root = ast.parse(file.read(), filename)
    body = root.body[:]
    # Documentation check
    if not __has_doc(body[0]):
        pass # TODO
    body.pop(0)
    # Import and assignment checks
    while body and isinstance(body[0], (ast.Import, ast.ImportFrom)):
        body.pop(0)
    while body and isinstance(body[0], ast.Assign):
        # TODO: body[0].value should only be simple types
        body.pop(0)
    # Function checks
    func_count = 0
    while body and isinstance(body[0], ast.FunctionDef):
        func_count += 1
        has_doc = __has_doc(body)
        if require_doc and not has_doc: pass # TODO
        if (forbid_useless_pass and len(body[0].body) > (2 if has_doc else 1) and
                any(isinstance(stmt, ast.Pass) for stmt in body[0].body)):
            pass # TODO
        body.pop(0)
    if func_count == 0:
        pass # TODO
    # Final if statment
    if not body:
        pass # TODO
    if len(body) > 1:
        pass # TODO
    if not isinstance(body[0], ast.If) or body[0].orelse is not None or len(body[0].body) != 1:
        pass # TODO
    test = body[0].test
    call = body[0].body[0]
    # TODO: left or comparators[0] must be a Name with .id == "__name__" with the other being a
    # Str with s == "__main__"
    if not isinstance(test, ast.Compare) or test.ops != [ast.Eq] or len(test.comparators) != 1:
        pass # TODO
    if not isinstance(call, ast.Expr) or not isinstance(call.value, ast.Call):
        pass # TODO
