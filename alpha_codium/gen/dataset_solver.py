import json
import os
import shutil
from collections import OrderedDict

from alpha_codium.code_contests.data.provider import CodeContestDataProvider
from alpha_codium.gen.coding_competitor import CodeContestsCompetitor
from alpha_codium.gen.utils import evaluate_solution_on_subset
from alpha_codium.log import setup_logger, get_logger
from alpha_codium.settings.config_loader import get_settings


def solve_dataset(dataset_name='valid_and_test_processed',
                  split_name='valid',
                  database_solution_path='solution_database.json'):

    # load dataset
    data_provider = CodeContestDataProvider(dataset_location=dataset_name)
    setting = get_settings()
    num_problems = len(data_provider.dataset[split_name])
    base_path = os.getcwd()
    setting.solve.reduce_verbose = True

    ## load previous solution-database if exists
    try:
        with open(database_solution_path, 'r') as f:
            database = json.load(f)
            database[split_name] = OrderedDict(sorted(database[split_name].items(), key=lambda x: int(x[0])))
    except:
        print(f"Failed to load database from {database_solution_path}")
        database = {split_name: {}}

    # iterate on problems
    for problem_number in range(0, num_problems):

        # skip if already ran
        logger = setup_logger()

        num_iterations =  setting.get("dataset.num_iterations", 1)
        prev = database[split_name].get(str(problem_number), {}).get(f'iteration_{num_iterations-1}', {})
        if not ((prev == {}) or (prev is None)):
            print(f"problem_number {problem_number} already ran")
            continue

        # check if problem is valid (at least one of the provided solutions actually passes the generated tests)
        if data_provider.dataset[split_name][problem_number].get('is_valid_problem', True) is False:
            logger.info(f"problem {problem_number} is not valid")
            continue

        os.chdir(base_path)
        logger.info(f"problem_number: {problem_number}")
        problem_name = data_provider.dataset[split_name][int(problem_number)]['name']
        logger.info(f"problem_name: {problem_name}")
        problem = data_provider.find_problem(ds=data_provider.dataset, problem_name=problem_name, split_name=split_name)
        logger.info(f"problem['cf_tags']: {problem['cf_tags']}")

        # solve problem
        problem_database = {problem_number: {}}
        solver = CodeContestsCompetitor()
        for iteration in range(setting.get("dataset.num_iterations", 1)):
            it_str = f"iteration_{iteration}"
            problem_database[problem_number][it_str] = {}

            # skip if iteration already ran
            prev_iter = database[split_name].get(str(problem_number), {}).get(it_str, {})
            if not ((prev_iter == {}) or (prev_iter is None)):
                print(f"prev_iter {iteration} already ran")
                problem_database[problem_number][it_str] = prev_iter
                if is_solved(prev_iter):
                    logger.info(f"codium solved problem {problem_number} in iteration {iteration}")
                    break
                continue

            # solve problem
            solution = solver.solve_problem_in_dataset(problem, iteration, logger)

            logger.info(f"solution code:\n{solution}")
            if not solution:
                logger.info(f"Failed to solve problem {problem_number} in iteration {iteration}")
                continue
            logger.info(f"Evaluating solution on public tests...")
            test_results, test_passed_public, test_failed_public, test_timeout_public = evaluate_solution_on_subset(
                'public_tests', problem, solution, silent=True)

            logger.info(f"evaluating solution on private tests...")
            test_results, test_passed_private, test_failed_private, test_timeout_private = evaluate_solution_on_subset(
                'private_tests', problem, solution, silent=True)

            logger.info(f"evaluating solution on generated tests...")
            test_results, test_passed_generate, test_failed_generate, test_timeout_generate = evaluate_solution_on_subset(
                'generated_tests', problem, solution, silent=True)

            logger.info(
                f"\ntest_passed_public: {test_passed_public}, test_failed_public: {test_failed_public}, test_timeout_public: {test_timeout_public}\n"
                f"test_passed_private: {test_passed_private}, test_failed_private: {test_failed_private}, test_timeout_private: {test_timeout_private}\n"
                f"test_passed_generate: {test_passed_generate}, test_failed_generate: {test_failed_generate}, test_timeout_generate: {test_timeout_generate}\n")

            problem_database[problem_number][it_str]['solution'] = solution
            problem_database[problem_number][it_str]['test_passed_private'] = test_passed_private
            problem_database[problem_number][it_str]['test_failed_private'] = test_failed_private
            problem_database[problem_number][it_str]['test_timeout_private'] = test_timeout_private
            problem_database[problem_number][it_str]['test_passed_generate'] = test_passed_generate
            problem_database[problem_number][it_str]['test_failed_generate'] = test_failed_generate
            problem_database[problem_number][it_str]['test_timeout_generate'] = test_timeout_generate
            problem_database[problem_number][it_str]['test_passed_public'] = test_passed_public
            problem_database[problem_number][it_str]['test_failed_public'] = test_failed_public
            problem_database[problem_number][it_str]['test_timeout_public'] = test_timeout_public
            os.chdir(base_path)
            if is_solved(problem_database[problem_number][it_str]):
                logger.info(f"codium solved problem {problem_number} in iteration {iteration}")
                break
            else:
                logger.info(f"codium failed to solve problem {problem_number} in iteration {iteration}")
        database[split_name][problem_number] = problem_database[problem_number]
        os.chdir(base_path)
        with open(database_solution_path, 'w') as f:
            json.dump(database, f)


def is_solved(s):
    if s['test_failed_private'] == 0 and s['test_failed_generate'] == 0 and \
            s['test_timeout_private'] == 0 and s['test_timeout_generate'] == 0 and \
            (s['test_passed_private'] + s['test_passed_generate']) > 0:
        return True
    else:
        return False
