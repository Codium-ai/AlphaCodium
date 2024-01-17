import argparse

from alpha_codium.gen.coding_competitor import solve_problem
from alpha_codium.log import setup_logger
from alpha_codium.settings.config_loader import get_settings

parser = argparse.ArgumentParser()
parser.add_argument("--dataset_name", type=str, default="valid_and_test_processed")
parser.add_argument("--split_name", type=str, default="valid")
parser.add_argument("--problem_number", type=int, default=0)
parser.add_argument("--problem_name", type=str, default="")

if __name__ == "__main__":
    args = parser.parse_args()
    setup_logger()
    solve_problem(dataset_name=args.dataset_name,
                  split_name=args.split_name,
                  problem_number=args.problem_number,
                  problem_name=args.problem_name)
