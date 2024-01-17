import re
from typing import List

import yaml

from alpha_codium.code_contests.eval.code_test_runners import eval_solution
from alpha_codium.settings.config_loader import get_settings
from alpha_codium.log import get_logger

logger = get_logger(__name__)


def clip_string(s: str, max_lines: int = None):
    lines = s.split("\n")
    if max_lines is not None and 0 < max_lines < len(lines):
        logger.debug(f"clipping string from {len(lines)} to {max_lines}")
        half_lines = int(max_lines / 2)
        lines = (
                lines[:half_lines] +
                [f"\n.... {len(lines) - max_lines} omitted lines ....\n"] +
                lines[-half_lines:]
        )
        return "\n".join(lines)
    else:
        return s


def render_trace(trace_data):
    if not trace_data:
        return ''

    max_trace_lines = get_settings().code_tester.get("max_trace_lines")
    trace_data = clip_string(trace_data, max_trace_lines)
    return trace_data


def postprocess_response(response):
    response = str(response)
    if response.endswith("stop"):
        response = response[:-4]
    pattern = r'```\w*\n(.*?)```'
    matches = re.findall(pattern, response, re.DOTALL)
    if matches:
        response = matches[0]
    return response


def evaluate_solution_on_subset(evaluation_test_type, problem, solution, silent=False, break_on_timeout=True):
    # evaluate solution
    test_results = None
    if evaluation_test_type:
        test_results = eval_solution(evaluation_test_type=evaluation_test_type, example=problem, prediction=solution,
                                     silent=silent, break_on_timeout=break_on_timeout)

    if test_results[1] == []:
        if not silent:
            logger.info("=====================================")
            logger.info("No tests")
            logger.info("=====================================")
        return test_results, 0, 0, 0

    if (hasattr(test_results[1], 'compilation_result') and
            test_results[1].compilation_result.program_status.name == 'kTimeout'):
        if not silent:
            logger.info("=====================================")
            logger.info("Timeout")
            logger.info("=====================================")
        return test_results, 0, 0, len(test_results[0])

    test_passed = 0
    test_failed = 0
    test_timeout = 0
    if not problem[evaluation_test_type]['input']:
        logger.info(f"No {evaluation_test_type} for this problem")
    else:
        for test in test_results[1].test_results:
            if (hasattr(test, 'program_status') and test.program_status.name == 'kTimeout'):
                test_timeout += 1
            elif not test.passed:
                test_failed += 1
            else:
                test_passed += 1
        if not silent:
            logger.info("=====================================")
            logger.info(f"test_passed: {test_passed}, test_failed: {test_failed}, test_timeout: {test_timeout}")
            logger.info("=====================================")

    return test_results, test_passed, test_failed, test_timeout


def evaluate_on_private_tests(evaluation_test_type, problem, solution, silent=True):
    # evaluate solution
    test_results = None
    if evaluation_test_type:
        test_results = eval_solution(evaluation_test_type=evaluation_test_type, example=problem, prediction=solution, silent=silent)

    test_passed = 0
    test_failed = 0
    test_timeout = 0

    if not test_results[1]:
        logger.info("No tests were run")
        return test_results, 0, 0

    for test in test_results[1].test_results:
        if test.program_status.name=='kTimeout':
            test_timeout += 1
        elif not test.passed:
            test_failed += 1
        else:
            test_passed += 1


    logger.info("=====================================")
    logger.info(f"test_passed: {test_passed}, test_failed: {test_failed}, test_timeout: {test_timeout}")
    logger.info("=====================================")

    return test_results, test_passed, test_failed, test_timeout


def load_yaml(response_text: str, keys_fix_yaml: List[str] = []) -> dict:
    response_text = response_text.rstrip("` \n")
    response_text = response_text.removeprefix('```yaml').rstrip('`')
    try:
        data = yaml.safe_load(response_text)
    except Exception as e:
        data = try_fix_yaml(response_text, keys_fix_yaml=keys_fix_yaml)
        if not data:
            get_logger().info(f"Failed to parse AI YAML prediction: {e}")
    return data


def try_fix_yaml(response_text: str, keys_fix_yaml: List[str] = []) -> dict:
    response_text_lines = response_text.split('\n')

    keys = keys_fix_yaml
    response_text_lines_copy = response_text_lines.copy()
    for i in range(0, len(response_text_lines_copy)):
        for key in keys:
            if response_text_lines_copy[i].strip().startswith(key) and not '|' in response_text_lines_copy[i]:
                response_text_lines_copy[i] = response_text_lines_copy[i].replace(f'{key}',
                                                                                  f'{key} |-\n        ')
    try:
        data = yaml.safe_load('\n'.join(response_text_lines_copy))
        get_logger().info(f"Successfully parsed AI prediction after adding |-\n")
        return data
    except:
        raise "yaml parsing error"