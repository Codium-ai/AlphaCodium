import argparse
import json
from collections import OrderedDict

from alpha_codium.code_contests.data.provider import CodeContestDataProvider
from alpha_codium.log import get_logger

logger = get_logger(__name__)

def evaluate_dataset_solution(dataset_name='valid_and_test_processed',
                               split_name='test',
                               solution_path_database='valid_database_solution.json'):
    """
    Evaluate the performance of dataset solutions.

    Args:
        dataset_name (str, optional): The name of the dataset. Defaults to 'valid_and_test_processed'.
        split_name (str, optional): The name of the split. Defaults to 'test'.
        solution_path_database (str, optional): The path to the solution database file. Defaults to 'valid_database_solution.json'.
    """

    # Load the dataset and solution database
    data_provider = CodeContestDataProvider(dataset_location=dataset_name)
    ds = data_provider.dataset[split_name]
    with open(solution_path_database, 'r') as f:
        database_solutions = json.load(f)
        database_solutions[split_name] = OrderedDict(
            sorted(database_solutions[split_name].items(), key=lambda x: int(x[0])))

    # Initialize counters for passed and failed problems
    total_passed = 0
    total_failed = 0

    # Iterate over the solutions in the database
    for sol in database_solutions[split_name]:
        try:
            key_str = sol
            key_int = int(key_str)
            problem = ds[key_int]
            if problem.get('is_valid_problem', True) is False:
                print(f"problem {key_int} is not valid")
                continue
            solution = database_solutions[split_name][sol]
            passed_current = -1

            # scanning the iterations
            v_iter =[v for v in solution.values() if (v is not None and 'solution' in v)]
            for v in v_iter:
                if not v:
                    continue
                test_failed_generate = v['test_failed_generate']
                test_failed_private = v['test_failed_private']
                test_passed_generate = v['test_passed_generate']
                test_passed_private = v['test_passed_private']
                if 'test_timeout_generate' in v:
                    test_timeout_generate = v['test_timeout_generate']
                    test_timeout_private = v['test_timeout_private']
                else:
                    test_timeout_generate = 0
                    test_timeout_private = 0

                if ((test_failed_generate + test_timeout_generate + test_failed_private + test_timeout_private) == 0 and
                        (test_passed_generate + test_passed_private) > 0):
                    print(f"problem {key_int} passed all tests")
                    passed_current=1
                    break
                else:
                    passed_current = 0
            if passed_current == 1:
                total_passed += 1
            elif passed_current == 0:
                total_failed += 1
        except Exception as e:
            print(f"Error: {e}")
            pass

    # Print the total number of passed and failed problems
    print(f"total_passed: {total_passed}, total_failed: {total_failed}")

    # Calculate the pass rate
    pass_rate = total_passed / (total_passed + total_failed)
    print(f"pass rate: {pass_rate}")

parser = argparse.ArgumentParser()
parser.add_argument("--dataset_name", type=str, default="valid_and_test_processed")
parser.add_argument("--split_name", type=str, default="valid")
parser.add_argument("--database_solution_path", type=str, default="./gpt_3_solution_database_valid.json")

if __name__ == "__main__":
    args = parser.parse_args()
    evaluate_dataset_solution(dataset_name=args.dataset_name,
                              split_name=args.split_name,
                              solution_path_database=args.database_solution_path)
