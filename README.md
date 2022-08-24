Helpful Tests
=============

This is a wrapper around Python's provided `unittest` module that provides more explanation with it's feedback for students in introductory computer science courses. It is designed to be used with git-keeper, provides HTML output for diffs, and has a timeout on the execution of code.

To use you need to install this library globally on the server: `sudo pip install git+https://github.com/MoravianUniversity/helpfultests.git@main`

Then in your the `tests/action.sh` file of the assignment you need to have a script similar to:

```sh
#!/bin/bash
cp -f "$1"/*.py .
if [ $? -ne 0 ]; then
    echo "😒 Your repository didn't contain the expected files."
else
    python3 -m helpfultests
fi
exit 0
```

and the `assignment.cfg` file should contain:

```conf
[email]
use_html: true
```

You will likely also have an `_instructor_tests.py` file in the `tests` folder (files with `_` prefix are run as tests last). The instructor tests work like normal `unittest`s except that they can use additional `TestCase` methods:

 * `read_file(filename)`: reads the given text file relative the current working directory and returns it.
 * `helpful_failure(msg)`: returns (not raises) an `AssertException` with the given message but also the attribute `helpful_msg` set to it making it print it literally in the helpful tests framework.
 * `assertOutputEqual(expected, func, *args, _whitespace='relaxed', _ordered=True, _regexp=False, **kwargs)`: asserts that the stdout produced by the calling `func(*args, **kwargs)` is equal to `expected`. The other arguments effect the comparison performed. The return value of the function call is returned as-is.
 * `assertEqualUsingUserInput(inpt, expected, func, *args, _must_output_args=True, **kwargs)`: asserts that the return value of `func(*args, **kwargs)` is equal to `expected` when providing `inpt` to `stdin` for the function. Checks that all of the input is read. If `_must_output_args` is `True` (default) then the arguments and keyword arguments show up in the output of the function, otherwise the output is not checked at all.
 * `assertOutputEqualUsingUserInput(inpt, output, func, *args, _whitespace='relaxed', _ordered=True, _regexp=False, **kwargs)`: combines the two above functions into a single check.
 * `assertNoPrint(print_func_okay=False, msg="...")`: A context manager (used with `with`) to cause a test failure whenever stdout is written to or `print()` is called (unless `print_func_okay` is set to `True` in which case it is allowed but not with `stdout`)
 * `assertNoInput(msg="...")`: A context manager (used with `with`) to cause a test failure whenever stdin is read from or `input()` is called
 * `assertDoc(func_or_module, min_length=16)`: Check that a function or module has documentation and it is of at least the given number of characters.
