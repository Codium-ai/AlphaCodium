import copy
import logging

from alpha_codium.gen.stages.indirect.run_analyze_and_fix_test_failure import run_analyze_and_fix_test_failure
from alpha_codium.gen.stages.indirect.run_analyze_tests_failure import run_analyze_test_failure
from alpha_codium.gen.stages.indirect.run_fix_code_from_tests_failure import run_fix_code_from_tests_failure
from alpha_codium.settings.config_loader import get_settings
from alpha_codium.gen.stages.run_tests import run_tests
from alpha_codium.log import get_logger

logger = get_logger(__name__)


async def run_evaluate_public_tests(self, problem):
    counter_retry = 0
    while True:
        try:
            logger.info("--iterate on public tests stage--")

            # configurations
            problem['use_self_reflection_public'] = get_settings().get('public_tests.use_self_reflection', False)
            max_allowed_fixes = get_settings().get("public_tests.max_allowed_calls", 6)
            max_fixes_per_test = get_settings().get("public_tests.max_fixes_per_test", 3)
            if len(problem['public_tests']['input']) == 1:
                max_fixes_per_test += 1

            # evaluate on public tests one by one
            test_inputs_all = problem['public_tests']['input']
            test_outputs_all = problem['public_tests']['output']
            test_explanations_all = problem['tests_explanations']
            all_passed_public = True
            number_of_llm_fixes = 0
            for test_inputs, test_outputs, test_explanation in zip(test_inputs_all, test_outputs_all,
                                                                    test_explanations_all):
                if not isinstance(test_inputs, list):
                    test_inputs = [test_inputs]
                    test_outputs = [test_outputs]
                problem['test_explanation_current'] = test_explanation
                problem['use_test_explanations_public'] = get_settings().get('public_tests.use_test_explanations', False)

                # loop to fix specific test
                counter_test = 0
                passed_specific_test = False
                last_code_solution = copy.deepcopy(problem['code_recent_solution'])
                best_solution = copy.deepcopy(problem['code_recent_solution'])
                best_d = float('inf')
                while not passed_specific_test:

                    # run the code on the test
                    problem, passed_specific_test, non_empty_output, error_str, trace_str, tests_timeout, d_tot \
                        = run_tests(self, problem, counter_test, test_inputs, test_outputs)

                    # save the best solution so far
                    if -1 < d_tot < best_d:
                        if counter_test > 0:
                            logger.info(f"Found better solution, d_tot: {d_tot}")
                        best_solution = copy.deepcopy(problem['code_recent_solution'])
                        best_d = d_tot

                    # cap the number of calls to the ai
                    if not passed_specific_test and number_of_llm_fixes >= max_allowed_fixes:
                        logger.debug(f"Failed to pass public test. reached max number of calls")
                        break

                    # analyze the tests results
                    counter_test += 1
                    logger.info(f"counter: {counter_test}")
                    if passed_specific_test:
                        logger.info(f"Passed a public test after {counter_test-1} attempts")
                        if test_inputs not in problem['passed_tests']['inputs']:
                            problem['passed_tests']['inputs'] += test_inputs
                            problem['passed_tests']['outputs'] += test_outputs
                        break
                    elif counter_test > max_fixes_per_test:
                        logger.debug(f"Failed to pass public tests after {max_fixes_per_test} attempts")
                        break
                    elif not non_empty_output:
                        logging.debug("Failed to pass public tests. actual_output is empty")
                        problem['code_recent_solution'] = last_code_solution
                        continue
                    else:
                        # tests run. save the last solution
                        problem['code_prev_solution'] = copy.deepcopy(problem['code_recent_solution'])

                    if not get_settings().get("public_tests.single_stage_fix", False):
                        # run 'analyze_and_fix_test_failure' stage
                        problem = await run_analyze_and_fix_test_failure(self, problem, error_str)
                    else:
                        # run 'analyze_test_failure' stage
                        problem = await run_analyze_test_failure(self, problem, error_str)

                        # run 'fix_code_from_tests_failure' stage
                        problem = await run_fix_code_from_tests_failure(self, problem, error_str)
                    number_of_llm_fixes += 1

                    # evaluate previous tests that passed. if they fail, revert to last solution
                    if problem['passed_tests']['inputs']:
                        problem, passed_prev_test, non_empty_output, error_str, trace_str, tests_timeout, d_tot \
                            = run_tests(self, problem, counter_test,
                                        problem['passed_tests']['inputs'],
                                        problem['passed_tests']['outputs'])
                        if not passed_prev_test:
                            logger.error(f"The fix broke prev passed tests. reverting to last solution")
                            problem['code_recent_solution'] = last_code_solution
                            continue

                # if not passed_specific_test:
                #     if problem['passed_tests']['inputs']:
                #         logger.error(f"Public test - reverting to initial solution, where: '{problem['passed_tests']['inputs']}' passed")
                #         problem['code_recent_solution'] = last_code_solution
                #     else: # no solution passed so far.
                #         pass
                #         logger.error("No solution passed so far. continuing to next test")
                #         # logger.error(f'Public test -  Reverting to best solution so far, d_tot: {best_d}')
                #         # problem['code_recent_solution'] = best_solution
                all_passed_public = all_passed_public and passed_specific_test

            if all_passed_public:
                logger.info(f"==================")
                logger.info(f"Passed all public tests")
                logger.info(f"==================")
            else:
                logger.info(f"==================")
                logger.info(f"Failed to pass all public tests")
                logger.info(f"==================")

            return problem
        except Exception as e:
            logging.error(f"'public tests' stage, counter_retry {counter_retry}, Error: {e}")
            counter_retry += 1
            if counter_retry > 2:
                raise e
