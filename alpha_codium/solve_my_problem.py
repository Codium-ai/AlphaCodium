import argparse
import json

from alpha_codium.gen.coding_competitor import solve_problem, solve_my_problem
from alpha_codium.log import setup_logger
from alpha_codium.settings.config_loader import get_settings

parser = argparse.ArgumentParser()
parser.add_argument("--my_problem_json_file", type=str, default="my_problem_example.json")

if __name__ == "__main__":
    args = parser.parse_args()
    setup_logger()
    
    with open(args.my_problem_json_file, "r") as my_problem:
        solve_my_problem(json.load(my_problem))
