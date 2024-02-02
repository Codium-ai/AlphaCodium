import os
import os.path
from typing import Iterable

import duckdb
import numpy as np
import pandas as pd
from datasets import Dataset, DatasetDict, load_dataset, load_from_disk
from datasets.features.features import Sequence, Value

from alpha_codium.settings.config_loader import get_settings

problem_translations = ("source", "difficulty")

solution_translations = ("solutions", "incorrect_solutions")


class CodeContestDataProvider:

    def __init__(self, dataset_location, connection=None):
        self.private_datasets_root = os.path.expanduser(
            get_settings().config.private_dataset_cache_dir
        )
        (
            self.dataset_location,
            self.dataset_name,
            self.load_from_disk,
        ) = self.parse_location(dataset_location)
        self.dataset = self.load_dataset()
        self.connection = connection or duckdb.connect()
        self.connect(self.dataset)


    @staticmethod
    def find_problem(ds, problem_name, split_name=None, evaluation_test_type = None):
        if split_name:
            ds = ds[split_name]
        example = None
        if not problem_name:
            for e in ds:
                if evaluation_test_type:
                    tests = e.get(evaluation_test_type)
                    if tests and tests.get("input"):
                        example = e
                        break
                else:
                    example = e
                    break
        else:
            problems = ds.filter(lambda example: example['name'] == problem_name)
            if problems:
                example = problems[0]
            else:
                raise ValueError(
                    f"problem with name {problem_name} doesn't exist in dataset {ds.info.dataset_name} in split {split_name}")
        return example

    @staticmethod
    def prepare_for_evaluation(
        predictions, source_of_truth, evaluation_test_type
    ):
        preds = predictions
        sot = source_of_truth
        sot = sot.select_columns(["name", evaluation_test_type])
        sot = sot.rename_column("name", "task_name")
        sot = sot.flatten()
        sot = sot.rename_column(f"{evaluation_test_type}.input", "tests_inputs")
        sot = sot.rename_column(f"{evaluation_test_type}.output", "tests_outputs")

        joined = sot.to_pandas().merge(preds.to_pandas(), on="task_name", how="left")
        joined["predictions"] = joined[["task_name", "solution_candidates"]].to_dict(
            "records"
        )
        joined["references"] = joined[["tests_inputs", "tests_outputs"]].to_dict(
            "records"
        )

        # Retain only the 'predictions' and 'references' columns
        joined = joined[["predictions", "references"]]
        restructured_dataset = Dataset.from_pandas(joined)
        return restructured_dataset

    def parse_location(self, dataset_location):
        result_location = dataset_location
        dataset_name = dataset_location.split(os.path.sep)[-1]
        load_from_disk = True
        if load_from_disk:
            if not result_location.startswith(os.path.sep):
                result_location = os.path.join(
                    self.private_datasets_root, result_location
                )
        return result_location, dataset_name, load_from_disk

    @staticmethod
    def prepare_code_contest_split_for_eval(
        ds, evaluation_test_type="public_tests", task_name_column="name",
            path_to_solutions_column="solutions.solution"
    ):
        solutions = ds.flatten()
        solutions = solutions.rename_column(
            path_to_solutions_column, "solution_candidates"
        )
        solutions = solutions.rename_column(task_name_column, "task_name")
        solutions = solutions.select_columns(["task_name", "solution_candidates"])
        return CodeContestDataProvider.prepare_for_evaluation(
            predictions=solutions,
            source_of_truth=ds,
            evaluation_test_type=evaluation_test_type,
        )

    def show(self, ds, paths_to_python, paths_to_free_text):
        result = ds.flatte()

        def format_example(example):
            for code_col in paths_to_python:
                import black

                example[code_col] = black.format_str(example[code_col])
            for col in paths_to_free_text:
                example[col] = example[col].replace("\\n", "\n")

        pretty = result.map(format_example)
        return pretty

    def load_dataset(self):
        if self.load_from_disk:
            f = load_from_disk
        else:
            f = load_dataset

        return f(self.dataset_location)

    def connect(self, ds):
        if hasattr(ds, "keys"):
            for split in self.dataset.keys():
                split_ds = self.dataset[split]
                table = split_ds.data.table
                self.connection.register(f"{split_ds.info.dataset_name}_{split}", table)
        else:
            self.connection.register(f"{ds.info.dataset_name}", ds.data.table)

    def get_splits(self):
        return self.dataset.keys()

    @staticmethod
    def sample(ds, fraction=0.1):
        table = ds
        sample_size = int(len(table) * fraction)
        indices = np.random.choice(len(table), sample_size, replace=False)
        sampled_table = table.select(indices)
        return sampled_table

    def query(self, query_string) -> pd.DataFrame:
        return self.connection.query(query_string).df()

    def translate_references(self, ds):
        expand = False
        if not isinstance(ds, DatasetDict):
            to_translate = {"ds": ds}
            expand = True
        else:
            to_translate = ds
        for ds_name, ds_val in to_translate.items():
            for col in problem_translations:
                translated_col = ds_val.features[col].int2str(ds_val[col])
                ds_val = ds_val.remove_columns([col])
                ds_val = ds_val.add_column(col, translated_col)

            def translate_sequence_references(example, ds):
                for col in solution_translations:
                    translator = ds.features[col].feature["language"]
                    arr = example[col]["language"]
                    translated_solution = [translator.int2str(item) for item in arr]
                    example[col]["language"] = translated_solution

                return example

            new_features = ds_val.features.copy()
            for col in solution_translations:
                new_features[col] = Sequence(
                    feature={"language": Value("string"), "solution": Value("string")}
                )

            ds_val = ds_val.map(
                lambda example, ds=ds_val: translate_sequence_references(
                    example=example, ds=ds
                ),
                features=new_features,
            )
            to_translate[ds_name] = ds_val
        result = to_translate
        if expand:
            result = result[ds]
        return result

    def filter_solution_by_languages(self, ds, languages: Iterable[str], keep=True):
        languages_set = set(languages)

        def filter_solutions_by_languages(example):
            for sol_col in solution_translations:
                langs = example[sol_col]["language"]
                sols = example[sol_col]["solution"]

                filtered_languages = [
                    lang for lang in langs if (lang in languages_set) == keep
                ]
                filtered_solutions = [
                    s
                    for idx, s in enumerate(sols)
                    if (langs[idx] in languages_set) == keep
                ]

                example[sol_col] = {
                    "language": filtered_languages,
                    "solution": filtered_solutions,
                }

            return example

        ds = ds.map(filter_solutions_by_languages)
        return ds
