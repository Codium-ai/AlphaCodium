import os

from evaluate import load as load_metric

from alpha_codium.code_contests.data.provider import CodeContestDataProvider
from alpha_codium.config_loader import get_settings


def calculate_metrics(ds, k_values=[1, 10, 100]):  # noqa: B006

    metric_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "code_contests_metric.py"
    )
    metric = load_metric(metric_path, config_name=get_settings().code_tester.tester_type, module_type="metric")
    pass_at_k, inputs, result = metric.compute(
        predictions=ds["predictions"], references=ds["references"], k=k_values
    )
    return pass_at_k, inputs, result


def evaluate_code_contest_dataset(
        dataset_name,
        split_name='valid',
        k_values=[1, 10, 10],  # noqa: B006
        evaluation_test_type='private_tests',
        path_to_solutions_column='solutions.solution',
        task_name_column='name',
        sample_rate=0.1,
):
    cc = CodeContestDataProvider(dataset_name)
    ds = cc.dataset[split_name]
    ds = cc.sample(ds, fraction=sample_rate)
    ds = CodeContestDataProvider.prepare_code_contest_split_for_eval(ds=ds,
                                                                     evaluation_test_type=evaluation_test_type,
                                                                     task_name_column=task_name_column,
                                                                     path_to_solutions_column=path_to_solutions_column)
    pass_at_k, inputs, result = calculate_metrics(ds, k_values=k_values)
    print(pass_at_k)


def evaluate_gen_dataset(evaluation_test_type, ground_truth_dataset, ground_truth_split, k_values, solution_dataset):
    evaluation_set = CodeContestDataProvider(dataset_location=solution_dataset)
    gt_set = CodeContestDataProvider(dataset_location=ground_truth_dataset).dataset
    if ground_truth_split:
        gt_set = gt_set[ground_truth_split]
    prepared_solutions = evaluation_set.prepare_for_evaluation(evaluation_set.dataset, gt_set,
                                                               evaluation_test_type=evaluation_test_type)
    pass_at_k, inputs, evaluation_results = calculate_metrics(prepared_solutions, k_values)
    print(pass_at_k)


if __name__ == "__main__":
    evaluate_code_contest_dataset("assaf_test", evaluation_test_type="private_tests", sample_rate=0.05)
