import argparse

from alpha_codium.gen.dataset_solver import solve_dataset
from alpha_codium.log import get_logger, setup_logger

logger = get_logger(__name__)

parser = argparse.ArgumentParser()
parser.add_argument("--dataset_name", type=str, default="valid_and_test_processed")
parser.add_argument("--split_name", type=str, default="valid")
parser.add_argument("--database_solution_path", type=str, default="")
if __name__ == "__main__":
    args = parser.parse_args()
    setup_logger()

    # set default database_solution_path
    args.database_solution_path = args.database_solution_path
    if not args.database_solution_path:
        args.database_solution_path = f"./{args.dataset_name}_{args.split_name}_solution_database.json"
        logger.info(f"args.database_solution_path: {args.database_solution_path}")

    solve_dataset(dataset_name=args.dataset_name,
                  split_name=args.split_name,
                  database_solution_path=args.database_solution_path)
