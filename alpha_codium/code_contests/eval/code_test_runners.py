import abc
import traceback
from abc import abstractmethod
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from typing import List, Optional

import tqdm

from alpha_codium.code_contests.eval.local_exec import (
    ExecutionResult,
    MultiTestResult,
    ProgramStatus,
    calculate_tests_pass_fail,
    execute_candidate_code,
)
from alpha_codium.settings.config_loader import get_settings
from alpha_codium.log import get_logger

logger = get_logger(__name__)


class PythonTestsRunner(abc.ABC):
    test_program = "x=input()\nprint(x)"
    test_inputs = ["hello"]
    test_outputs = test_inputs

    @staticmethod
    def factory(runner_type, *args, **kwargs):
        if runner_type == 'local':
            return LocalPythonTestsRunner(*args, **kwargs)
        elif runner_type == 'code_contests':
            return CodeContestsGeneralPythonTestsRunner(*args, **kwargs)
        else:
            raise ValueError(f"Unknown method type: {runner_type}")

    @abstractmethod
    def test_interpreter(self):
        pass

    @abstractmethod
    def run_tests(self, test_id, candidate_id, candidate, test_inputs, tests_outputs, snoop=False):
        pass

    def format_exception(self, e):
        formatted_lines = traceback.format_exception(type(e), e, e.__traceback__)
        return ("\n".join(formatted_lines[-3:]))

    @abstractmethod
    def create_executor(self):
        pass

    @staticmethod
    def remove_if_main(script: str):
        new_content = script
        if 'if __name__ ==' in script:
            result_lines = script.split('\n')
            start_dedent = False
            for i, line in enumerate(result_lines):
                if 'if __name__ ==' in line:
                    start_dedent = True
                    result_lines[i] = ''
                if start_dedent:
                    result_lines[i] = result_lines[i][4:]
            new_content = '\n'.join(result_lines)
        return new_content

    @staticmethod
    def flatten_result_list_by_index(results_list):
        result = {}
        for task_name, candidate_results_list in results_list.items():
            max_index = max(candidate_results_list, key=lambda x: x[0])[0] + 1
            result_list = [None] * max_index
            for index, value in candidate_results_list:
                result_list[index] = value
            result[task_name] = result_list
        return result

    def print_test_results(self, result: MultiTestResult, test_inputs: List[str] = None):
        if result.compilation_result:
            if get_settings().solve.reduce_verbose:
                logger.debug(
                    f"compilation results:{result.compilation_result.program_status if result.compilation_result else ''}")
                logger.debug(result.compilation_result.sandbox_result)
                logger.debug(result.compilation_result.stderr)
            else:
                logger.info(
                    f"compilation results:{result.compilation_result.program_status if result.compilation_result else ''}")
                logger.info(result.compilation_result.sandbox_result)
                logger.info(result.compilation_result.stderr)

        for i, test_res in enumerate(result.test_results):
            if get_settings().solve.reduce_verbose:
                logger.debug(f"input:\n{test_inputs[i]}")
                logger.debug(f"expected vs code output:\n{test_res.expected_output}\n---\n{test_res.actual_output}")
            else:
                logger.info(f"input:\n{test_inputs[i]}")
                logger.info(f"expected vs code output:\n{test_res.expected_output}\n---\n{test_res.actual_output}")
            details = f"passed={test_res.passed}"
            if not test_res.passed:
                error = ""
                if test_res.stderr.strip() != "":
                    error = f"strerror: {test_res.stderr}."
                if test_res.sandbox_result:
                    error_lines = test_res.sandbox_result
                    error = f"{error} sandbox error: {error_lines}"
                details = f"{details}. {error}"
            if test_res.program_status == ProgramStatus.kTimeout:
                details = f"runtime of {test_res.execution_duration} exceeded allowed runtime"

            logger.info(f"test-{i} :: status={test_res.program_status}, passed={test_res.passed}")
            if get_settings().solve.reduce_verbose:
                logger.debug(f"{details}")
            else:
                logger.info(f"{details}")
            logger.info("=====================================================================")

    def bulk_test(self, num_workers, predictions, references):
        executor_cls, kw = self.create_executor()
        kw['max_workers'] = num_workers
        with executor_cls(**kw) as executor:
            futures = []
            completion_id = Counter()
            n_samples = 0
            results = defaultdict(list)
            inputs = defaultdict(dict)
            for prediction, reference in zip(predictions, references):
                task_name = prediction["task_name"]
                candidates = prediction["solution_candidates"]
                if not candidates:
                    print(f"skipping {task_name} - no solutions provided")
                    continue
                tests_inputs = reference["tests_inputs"]
                tests_outputs = reference["tests_outputs"]
                if not tests_inputs:
                    print(f"ERROR: {task_name} - no inputs")
                    continue
                if not tests_outputs:
                    print(f"ERROR: {task_name} - no outputs")
                    continue
                print(f"submitting task {task_name} with {len(candidates)}")
                print(f"test inputs: {tests_inputs}")
                print(f"test outputs: {tests_outputs}")
                inputs[task_name]["tests_inputs"] = tests_inputs
                inputs[task_name]["tests_outputs"] = tests_inputs
                inputs[task_name]["candidates"] = []
                for candidate_id, candidate in enumerate(candidates):
                    print(f"\tsubmitting candidate {candidate_id}")
                    inputs[task_name]["candidates"].append(candidate)
                    args = (
                        task_name,
                        candidate_id,
                        candidate,
                        tests_inputs,
                        tests_outputs,
                    )
                    future = executor.submit(self.run_tests, *args)
                    futures.append(future)
                    completion_id[task_name] += 1
                    n_samples += 1

            pbar = tqdm.tqdm(total=len(futures), desc="Processing tasks", ncols=100)  # create a progress bar
            for future in as_completed(futures):
                task_id, candidate_id, test_result = future.result()
                print(task_id)
                results[task_id].append((candidate_id, test_result))
                pbar.update(1)  # update the progress bar by one step
            pbar.close()
            flattened_results = self.flatten_result_list_by_index(results)
        return inputs, flattened_results


class LocalPythonTestsRunner(PythonTestsRunner):

    def __init__(self):
        super().__init__()
        self.sandbox = get_settings().code_tester.sandbox
        self.calc_trace = get_settings().code_tester.calc_trace

    def test_interpreter(self):
        _, _, result = self.run_tests(0, "test interpreter", PythonTestsRunner.test_program,
                                      PythonTestsRunner.test_inputs, PythonTestsRunner.test_outputs, snoop=True)
        super().print_test_results(result)

    @staticmethod
    def prepare_script(script: str):
        script = LocalPythonTestsRunner.remove_if_main(script)
        return script

        ## nope - ast removes code comments. we dont want that
        # if not script:
        #     return script
        # try:
        #     tree = ast.parse(script)
        #     # Find the if __name__ == '__main__' condition and extract its body
        #     main_body = []
        #     other_nodes = []
        #     for node in tree.body:
        #         if (isinstance(node, ast.If) and
        #                 isinstance(node.test, ast.Compare) and
        #                 isinstance(node.test.left, ast.Name) and
        #                 node.test.left.id == '__name__' and
        #                 isinstance(node.test.ops[0], ast.Eq) and
        #                 isinstance(node.test.comparators[0], ast.Str) and
        #                 node.test.comparators[0].s == '__main__'):
        #             main_body.extend(node.body)
        #         else:
        #             other_nodes.append(node)
        #
        #     # Construct a new module without the condition, appending the body of the if __name__ block
        #     new_tree = ast.Module(body=other_nodes + main_body, type_ignores=[])
        #
        #     # Convert the new AST back to code
        #     new_content = ast.unparse(new_tree)
        # except Exception as e:
        #     raise ValueError("Input is not a legal Python program") from e


    def run_tests(self, test_id, candidate_id, candidate, test_inputs, tests_outputs, timeout=10, snoop=None, break_on_timeout=False):
        try:
            candidate = PythonTestsRunner.remove_if_main(candidate)
        except:  # noqa
            logger.info(
                "candidate program is not a valid Python program. Will attempt to run it anyway and collect as failure")

        to_snoop = snoop if snoop is not None else self.calc_trace
        multi_result = execute_candidate_code(candidate=candidate, inputs=test_inputs,
                                              test_id=test_id, timeout=timeout, sandbox=self.sandbox,
                                              snoop=to_snoop, break_on_timeout=break_on_timeout)
        tests_results = calculate_tests_pass_fail(multi_result, expected_results=tests_outputs)
        return test_id, candidate_id, tests_results

    def create_executor(self):
        return ProcessPoolExecutor, {}  # {'initializer': reliability_guard}


class CodeContestsGeneralPythonTestsRunner(PythonTestsRunner):
    def __init__(
            self,
            path_to_python_bin: str = get_settings().get("code_contests_tester.path_to_python_bin"),
            path_to_python_lib: List[str] = get_settings().get("code_contests_tester.path_to_python_lib"),
            num_threads: int = 1,
            stop_on_first_failure: bool = get_settings().get("code_contests_tester.stop_on_first_failure"),
            timeout: int = get_settings().get("code_contests_tester.timeout")
    ):

        try:
            from code_contests_tester import Py3TesterSandboxer, TestOptions  # noqa: F401
        except ImportError as e:
            raise ValueError("Error: cannot import the test sandbox on your environment") from e

        options = TestOptions()
        options.num_threads = num_threads
        options.stop_on_first_failure = stop_on_first_failure

        def compare_func(a, b):
            return a == b

        self.tester = Py3TesterSandboxer(path_to_python_bin, path_to_python_lib)
        self.options = options
        self.compare_func = compare_func
        self.test_interpreter()

    def test_interpreter(self):
        result=self.tester.test(
            PythonTestsRunner.test_program,
            PythonTestsRunner.test_inputs,
            self.options,
            PythonTestsRunner.test_outputs,
            self.compare_func,
        )
        internal_results = self.cpp_to_python_results(result)
        passed = internal_results.test_results[0].stdout == PythonTestsRunner.test_outputs
        print(f"interpreter test {'did not' if not passed else ''} pass")


    def cpp_to_python_results(self, cpp_results):

        def cpp_exec_result_to_python(cpp_result):
            python_result = ExecutionResult(
                program_status=ProgramStatus[f"k{str(cpp_result.program_status.name)}"],
                program_hash=cpp_result.program_hash,
                stdout=cpp_result.stdout,
                stderr=cpp_result.stderr,
                #execution_duration=cpp_result.execution_duration,
                sandbox_result=cpp_result.sandbox_result,
                passed=cpp_result.passed,
                trace=None  # This field does not exist in the C++ class; set a default or derive as needed
            )
            return python_result
        if cpp_results.compilation_result:
            compilation_result = cpp_exec_result_to_python(cpp_results.compilation_result)

        if cpp_results.test_results:
            test_results = [cpp_exec_result_to_python(item) for item in cpp_results.test_results]

        return MultiTestResult(test_results=test_results, compilation_result=compilation_result)

    def run_tests(self, test_id, candidate_id, candidate, test_inputs, tests_outputs, timeout=10, snoop=None):
        multi_result = self.tester.test(
            candidate, test_inputs, self.options, tests_outputs, self.compare_func
        )

        internal_results = self.cpp_to_python_results(multi_result)
        tests_results = calculate_tests_pass_fail(internal_results, expected_results=tests_outputs)
        return test_id, candidate_id, tests_results


    def create_executor(self):
        return ThreadPoolExecutor, {}


def eval_solution(evaluation_test_type: str = "private_tests",
                  example: dict = {},  # noqa # the code contest problem
                  prediction: str = '',  # python code to be evaluated
                  test_inputs: Optional[List[str]] = None,
                  test_outputs: Optional[List[str]] = None,
                  silent=False,
                  break_on_timeout=False):
    if not test_inputs:
        test_inputs = example.get(evaluation_test_type).get("input") if example.get(evaluation_test_type) else None
    if not test_outputs:
        test_outputs = example.get(evaluation_test_type).get("output") if example.get(evaluation_test_type) else None

    is_valid_test_list = example.get(evaluation_test_type).get("is_valid_test") if example.get(
        evaluation_test_type) else None
    if is_valid_test_list:
        test_inputs = [test_inputs[i] for i, is_valid in enumerate(is_valid_test_list) if is_valid]
        test_outputs = [test_outputs[i] for i, is_valid in enumerate(is_valid_test_list) if is_valid]
    if test_inputs and test_outputs:
        test_runner = PythonTestsRunner.factory(get_settings().code_tester.tester_type)
        _, _, results = test_runner.run_tests(
            test_id=example["name"],
            candidate_id="id",
            candidate=prediction,
            test_inputs=test_inputs,
            tests_outputs=test_outputs,
            timeout=3,
            break_on_timeout = break_on_timeout,
        )
        if not silent:
            test_runner.print_test_results(results, test_inputs)
        return test_inputs, results
    else:
        # logger.error(f"example '{example['name']}', type: '{evaluation_test_type}' doesn't have tests")
        return test_inputs, []


if __name__ == '__main__':
    runner = LocalPythonTestsRunner()
    error_program = """

x = input()

def f1(val):
    return f2(val)

def f2(val):
    return int(val)/0
    
f1(x)

"""
    program = """
if __name__ == '__main__':
    x = input()
    y=0
    for i in range(10):
        y = int(x) + i
        print(y)
"""

    _, _, results = runner.run_tests("test", 1, program, ["1", "2"], ["1", "2"], snoop=True)
    runner.print_test_results(results, ["1", "2"])
