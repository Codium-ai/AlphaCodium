import ast
import inspect
import io
import math
import os
import sys
import tempfile
from contextlib import contextmanager
from functools import partial
from typing import Callable, List

import pytest as pytest
from pysnooper import snoop

from alpha_codium.code_contests.eval.local_exec import MultiTestResult, ProgramStatus, execute_candidate_code
from alpha_codium.code_contests.eval.tracer import snooper_kwargs

timeout = 3


@contextmanager
def mock_input_output(mock_input_value):
    new_out = io.StringIO()
    new_in = io.StringIO(mock_input_value + '\n')

    old_out = sys.stdout
    old_in = sys.stdin

    sys.stdout = new_out
    sys.stdin = new_in

    yield new_out

    sys.stdout = old_out
    sys.stdin = old_in


class SandboxCaseContainer:

    def __init__(self, f: Callable):
        self.f = f

    def execute_as_string(self, input: str, sandbox=False):
        return self.execute_as_str_inner([input], trace=False, sandbox=sandbox)

    def execute_as_string_with_tracing(self, input: str, sandbox=False):
        return self.execute_as_str_inner([input], trace=True, sandbox=sandbox)

    def execute_as_str_inner(self, inputs: List[str], trace=False, sandbox=False):
        check_program = self.get_body()
        f = partial(execute_candidate_code, candidate=check_program, inputs=inputs, test_id=self.f.__name__,
                    timeout=timeout, sandbox=sandbox, snoop=trace)
        if sandbox:
            with tempfile.TemporaryDirectory() as temp_dir:
                os.chdir(temp_dir)
                result = f()
        else:
            result = f()

        return result

    def get_body(self):
        function_body = inspect.getsource(self.f)
        func_ast = ast.parse(function_body)
        func_def = [node for node in ast.walk(func_ast) if isinstance(node, ast.FunctionDef)][0]
        body = func_def.body
        lines = [ast.unparse(node).strip() for node in body]
        result = "\n".join(lines).strip()
        print(result)
        return result


def io_solution():
    x = input()
    print(x)


def one_level_and_loop_solution():
    def my_func(val):
        for i in range(val):
            print(i)

    x = int(input())
    my_func(x)


def multi_level_and_loop_solution():
    def printer_inner(val):
        print(val)

    def printer(val):
        print("p")
        printer_inner(val)

    def my_func(val):
        for i in range(val):
            printer(i)

    x = int(input())
    my_func(x)


def recursion_solution():
    def fibonacci(n):
        if n <= 0:
            return 0
        elif n == 1:
            return 1
        else:
            return fibonacci(n - 1) + fibonacci(n - 2)

    x = int(input())
    fib = fibonacci(x)
    print(fib)


def timeout_solution():
    def sleeper(timeout):
        import time
        print(f"sleeping for {timeout + 1}")
        time.sleep(timeout + 1)

    timeout = int(input())
    sleeper(timeout)


def exception_solution():
    def excepter(n):
        raise ValueError(f"test run cannot accept {n}")

    x = int(input())
    excepter(x)


def bad_import_solution():
    print(math.sqrt(int(input())))


test_data = [
    (io_solution, 'hello', 'hello'),  # (function, input, expected output)
    (one_level_and_loop_solution, '4', '0\n1\n2\n3'),
    (multi_level_and_loop_solution, '4', 'p\n0\np\n1\np\n2\np\n3'),
    (recursion_solution, '4', '3'),
]

run_types = ['regular', 'regular_with_tracing', 'as_string', 'as_string_with_tracing']


def data_id(test_case):
    f, input_, output_ = test_case
    return f"{f.__name__}-{hash(str(input_) + str(output_))}"

sandbox_ids=["not-sandboxed", "sandboxed"]


@pytest.mark.parametrize("run_type", run_types)
@pytest.mark.parametrize("sandbox", [False, True], ids=sandbox_ids)
@pytest.mark.parametrize("func, input, expected", test_data, ids=[data_id(case) for case in test_data])
def test_happy_paths(monkeypatch, func, input, expected, run_type, sandbox):
    def assert_passed_and_output(expected, result: MultiTestResult):
        assert len(result.test_results) == 1
        my_result = result.test_results[0]
        assert my_result.stdout == expected
        assert my_result.stderr == ''
        print("trace\n")
        print(my_result.trace)

    my_case = SandboxCaseContainer(func)
    if 'regular' in run_type:
        with mock_input_output(input) as captured_output:
            if 'regular_with_tracing' == run_type:
                with snoop(**snooper_kwargs):
                    my_case.f()
            else:
                my_case.f()
            result = captured_output.getvalue().strip()
            assert expected == result

    elif run_type == 'as_string':
        res = my_case.execute_as_string(input, sandbox=sandbox)
        assert_passed_and_output(expected, res)

    elif run_type == 'as_string_with_tracing':
        res = my_case.execute_as_string_with_tracing(input, sandbox=sandbox)
        assert_passed_and_output(expected, res)


test_exception_data = [
    (timeout_solution, str(timeout), ProgramStatus.kTimeout, ''),
    (exception_solution, '1', ProgramStatus.kFailed, 'test run cannot accept 1'),
    (bad_import_solution, '1', ProgramStatus.kFailed, "NameError: name 'math' is not defined"),
]

def exception_data_id(test_case):
    f, input_, status, _ = test_case
    return f"{f.__name__}-{str(status)}-{hash(input_)}"

@pytest.mark.parametrize("run_type", run_types)
@pytest.mark.parametrize("sandbox", [False, True], ids=sandbox_ids)
@pytest.mark.parametrize("func, input, status, error_string", test_exception_data,
                         ids=[exception_data_id(case) for case in test_exception_data])
def test_runtime_issues(monkeypatch, func, input, status, error_string, run_type, sandbox):
    def assert_status_and_error(result: MultiTestResult, status, err):
        assert len(result.test_results) == 1
        my_result = result.test_results[0]
        assert my_result.program_status == status
        assert err in my_result.sandbox_result
        print("trace")
        print(my_result.trace)
        print("=============")
        print("stack trace")
        print(my_result.sandbox_result)

    my_case = SandboxCaseContainer(func)

    if run_type == 'as_string':
        res = my_case.execute_as_string(input)
        assert_status_and_error(res, status, error_string)

    elif run_type == 'as_string_with_tracing':
        res = my_case.execute_as_string_with_tracing(input)
        assert_status_and_error(res, status, error_string)


if __name__ == '__main__':
    timeout_solution()
