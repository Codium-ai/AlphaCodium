import copy
import logging

from alpha_codium.gen.stages.indirect.run_analyze_and_fix_test_failure import run_analyze_and_fix_test_failure
from alpha_codium.gen.stages.run_tests import run_tests
from alpha_codium.log import get_logger
from alpha_codium.settings.config_loader import get_settings

logger = get_logger(__name__)


async def run_evaluate_all_ai_tests(self, problem):
    try:
        logger.info("--iterate on all ai tests stage--")

        ai_tests = problem['problem_ai_tests']
        max_allowed_calls = get_settings().get("ai_tests.max_allowed_calls", 6)

        # evaluate ai tests
        actual_number_of_calls = 0
        for i, test in enumerate(ai_tests):
            counter = 0
            test_inputs = test['input']
            test_outputs = test['output']
            if not isinstance(test_inputs, list):
                test_inputs = [test_inputs]
                test_outputs = [test_outputs]

            # run the solution on the tests
            problem, test_passed, non_empty_output, error_str, trace_str, tests_timeout, d_tot \
                = run_tests(self, problem, counter, test_inputs, test_outputs)

            # we passed without changing the code. Add the test to the passed tests list
            if test_passed:
                if test_inputs not in problem['passed_tests']['inputs']:
                    logger.info(f"Passed ai tests without code fixing. adding to passed tests list")
                    problem['passed_tests']['inputs'] += test_inputs
                    problem['passed_tests']['outputs'] += test_outputs
            else:
                # cap the number of calls to the ai
                if actual_number_of_calls >= max_allowed_calls:
                    if i < len(ai_tests) - len(problem['public_tests']['input']):  # don't skip public tests
                        logger.error(f"Failed to pass ai test. reached max number of calls")
                        continue

                logger.error(f"Failed to pass ai tests. trying to fix code")
                last_code_solution = copy.deepcopy(problem['code_recent_solution'])

                # run 'analyze_and_fix_test_failure' stage
                problem = await run_analyze_and_fix_test_failure(self, problem, error_str)
                actual_number_of_calls += 1

                problem, test_passed2, non_empty_output2, error_str2, trace_str2, tests_timeout2, d_tot2 \
                    = run_tests(self, problem, counter, test_inputs, test_outputs)

                if not test_passed2 and (not 'sandbox error: ' in error_str):
                    logger.error(f"Failed to pass ai tests with fixed code.")
                    problem['code_recent_solution'] = last_code_solution
                else:  # we passed the test after fixing the code

                    # running previous passed tests again to make sure we didn't break anything
                    if problem['passed_tests']['inputs']:
                        problem, all_passed_prev, non_empty_output, error_str, trace_str, tests_timeout, d_tot \
                            = run_tests(self, problem, counter,
                                        problem['passed_tests']['inputs'],
                                        problem['passed_tests']['outputs'])
                        if not all_passed_prev:
                            logger.error(f"The fix broke prev passed tests. reverting to last solution")
                            problem['code_recent_solution'] = last_code_solution
                            continue

                    if test_passed2:
                        logger.info(f"Fixed current test, and passed prev tests. using new solution")
                        if test_inputs not in problem['passed_tests']['inputs']:
                            problem['passed_tests']['inputs'] += test_inputs
                            problem['passed_tests']['outputs'] += test_outputs
                    else:
                        logger.info(f"Code doesnt crash, but still fails the test. using new solution")

        return problem
    except Exception as e:
        logging.error(f"Error in 'run_evaluate_all_ai_tests': {e}")
        return problem
