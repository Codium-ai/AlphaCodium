import copy
import logging

from alpha_codium.settings.config_loader import get_settings
from alpha_codium.gen.stages.run_initial_solve import run_initial_solve
from alpha_codium.gen.stages.run_tests import run_tests
from alpha_codium.log import get_logger

logger = get_logger(__name__)


async def run_initial_code_generation(self, problem):
    counter_retry = 0
    while True:
        try:
            logger.info("--run initial code generation stage--")

            max_attempts = get_settings().get('initial_code_generation.max_attempts', 5)
            counter = 0

            # set the public tests as input
            test_input = problem['public_tests']['input']
            test_output = problem['public_tests']['output']

            # generate an initial code, using the top solution from the previous stage
            problem = await run_initial_solve(self, problem)

            # run the solution on the selected tests
            problem, passed_tests, non_empty_output, error_str, trace_str, tests_timeout, d_tot \
                = run_tests(self, problem, counter, test_input, test_output)

            best_solution = copy.deepcopy(problem['code_recent_solution'])
            best_d = float('inf') # distance to the correct solution

            # set the distance to the correct solution
            if -1 < d_tot < best_d:
                best_solution = copy.deepcopy(problem['code_recent_solution'])
                best_d = d_tot

            while not passed_tests:
                counter += 1
                if counter > max_attempts:
                    logger.error(f"Failed to pass tests after {counter - 1} attempts. exiting the stage")
                    break

                s_best_solution_original = problem['s_best_solution']
                if counter > 1 and 's_possible_solutions' in problem:
                    # give two attempts to the highest ranked solution
                    problem['s_best_solution'] = problem['s_possible_solutions'][
                        counter % len(problem['s_possible_solutions'])]
                problem = await run_initial_solve(self, problem)
                problem['s_best_solution'] = s_best_solution_original

                problem, passed_tests, non_empty_output, error_str, trace_str, tests_timeout, d_tot \
                    = run_tests(self, problem, counter, test_input, test_output)

                if passed_tests:
                    logger.info(f"Passed tests after {counter} attempts")
                    break
                else:
                    logger.info(f"Failed to pass tests after {counter} attempts, d: {d_tot}, best_d so far: {best_d}")

                # save the best solution so far
                if -1 < d_tot < best_d:
                    best_solution = copy.deepcopy(problem['code_recent_solution'])
                    best_d = d_tot

            # set the best solution
            if not passed_tests and best_d < float('inf'):
                logger.error(f'Reverting to best solution so far, d_tot: {best_d}')
                problem['code_recent_solution'] = best_solution

            return problem
        except Exception as e:
            logging.error(f"'initial code generation' stage, counter_retry {counter_retry}, Error: {e}")
            counter_retry += 1
            if counter_retry > 2:
                raise e
