import asyncio
import copy
import json
import os
import shutil
from collections import OrderedDict
import time
import numpy as np
from datasets import Dataset

from alpha_codium.code_contests.data.provider import CodeContestDataProvider
from alpha_codium.log import get_logger, setup_logger
from alpha_codium.gen.utils import evaluate_solution_on_subset
from alpha_codium.settings.config_loader import get_settings

logger = get_logger(__name__)


def preapare_and_clean_dataset(dataset_name='valid_and_test'):

    # process base dataset
    output_dataset_name = 'valid_and_test_processed'
    base_path = os.path.expanduser(get_settings().etl.private_dataset_cache_dir)
    output_path = os.path.join(base_path, output_dataset_name)
    data_provider = CodeContestDataProvider(dataset_location=dataset_name)

    # add and process the multiple_solutions field
    data_provider = add_multiple_solutions_field(data_provider)

    # will add 'is_valid_test' field to all problems
    data_provider = add_is_valid_field(data_provider)

    data_provider = problem_3_validation_fix(data_provider)
    data_provider = problem_29_test_fix(data_provider)
    data_provider = problem_92_test_fix(data_provider)

    # sorting so that 'python' solutions will be first
    data_provider = sort_solution_by_language(data_provider)

    # calc if there are valid solutions to the problem. if not, mark the problem as invalid
    data_provider = calc_is_valid_problem(data_provider)

    # save the dataset
    data_provider.dataset.save_to_disk(output_path)


def calc_is_valid_problem(data_provider):
    get_settings().code_tester.sandbox = False
    th_correct = 0.2  # if less than 20% of the solutions are correct, mark the problem as invalid
    max_tests = 25

    for split_name in ['valid', 'test']:
        ds = data_provider.dataset[split_name]
        ds_dict = ds.to_dict()
        ds_dict['is_valid_problem'] = [True] * len(ds)
        solutions_list = ds_dict['solutions']
        for i, solutions in enumerate(solutions_list):
            logger.info(f"processing problem {i} in split '{split_name}' for valid solutions")
            problem_dict = ds[i]
            s_list = solutions['solution']
            l_list = solutions['language']
            s_list = [s for s, l in zip(s_list, l_list) if 'python' in l.lower()]
            l_list = [l for l in l_list if 'python' in l.lower()]
            if len(s_list) < 5:
                logger.info(f"problem {i} in split '{split_name}' has less than 5 python solutions, cannot validate")
                continue
            test_failed_private_list = []
            test_failed_generated_list = []
            counter = 0
            timeout_len = 60  # 60 seconds
            start_time = time.time()
            for language, sol in zip(l_list, s_list):
                if 'python' not in language.lower():
                    continue
                counter += 1
                if counter > max_tests:
                    continue
                if time.time() > start_time + timeout_len:
                    continue
                # test_results, test_passed_public, test_failed_public, test_timeout_public \
                #     = evaluate_solution_on_subset('public_tests', problem_dict, sol, silent=True, break_on_timeout=True)
                test_results, test_passed_private, test_failed_private, test_timeout_private \
                    = evaluate_solution_on_subset('private_tests', problem_dict, sol, silent=True,
                                                  break_on_timeout=True)
                test_results, test_passed_generate, test_failed_generate, test_timeout_generate \
                    = evaluate_solution_on_subset('generated_tests', problem_dict, sol, silent=True,
                                                  break_on_timeout=True)
                test_failed_private_list.append(test_failed_private)
                test_failed_generated_list.append(test_failed_generate)
                if (time.time() > start_time + timeout_len) and counter > 10:
                    continue
            if not test_failed_private_list:
                logger.info(f"problem {i} in split '{split_name}' has no python solutions")
                continue
            test_failed_private_list = np.array(test_failed_private_list)
            test_failed_generated_list = np.array(test_failed_generated_list)
            frac_correct = np.sum((test_failed_private_list + test_failed_generated_list) == 0) / len(
                test_failed_private_list)

            # final decision
            if frac_correct < th_correct:
                logger.info(f"Failed - problem {i} in split {split_name} is invalid, has {frac_correct*100}% correct solutions, "
                            f"total of {len(test_failed_private_list)} solutions processed")
                ds_dict['is_valid_problem'][i] = False
            else:
                logger.info(f"Passed - problem {i} in split {split_name} is valid, has {frac_correct*100}% correct solutions, "
                            f"total of {len(test_failed_private_list)} solutions processed")

        data_provider.dataset[split_name] = Dataset.from_dict(ds_dict)
    return data_provider
def add_multiple_solutions_field(data_provider):
    for split_name in ['valid', 'test']:
        multiple_solutions_list = np.array([False] * len(data_provider.dataset[split_name]))
        ds = data_provider.dataset[split_name]
        for i, p in enumerate(ds):
            d_output = p['description'].split('Output\n')[1]
            if ('multiple solutions' in p['description'] or 'multiple possible solutions' in p['description']
                    or 'multiple possible solutions' in p['description'] or 'multiple' in d_output):
                # print(f"problem {i} has multiple solutions")
                # print(f"=========\n{p['description']}\n=======\n\n")
                multiple_solutions_list[i] = True
            else:
                multiple_solutions_list[i] = False

        data_provider.dataset[split_name] = data_provider.dataset[split_name].add_column('multiple_solutions',
                                                                                         multiple_solutions_list)
    return data_provider


def sort_solution_by_language(data_provider):
    # sorting so that 'python' solutions will be first
    for split_name in ['valid', 'test']:
        ds_dict = data_provider.dataset[split_name].to_dict()
        solutions_list = ds_dict['solutions']
        for i, p in enumerate(solutions_list):
            np_lang = np.array(p['language'])
            ind_sorted = np.concatenate(
                (np.argwhere(np_lang == 'PYTHON3'), np.argwhere(np_lang == 'CPP'), np.argwhere(np_lang == 'JAVA')))
            p['solution'] = [p['solution'][i[0]] for i in ind_sorted]
            p['language'] = [p['language'][i[0]] for i in ind_sorted]
        data_provider.dataset[split_name] = Dataset.from_dict(ds_dict)
    return data_provider
def add_is_valid_field(data_provider):
    for split_name in ['valid', 'test']:
        ds_dict = data_provider.dataset[split_name].to_dict()
        ds_dict['public_tests'][0]['is_valid_test'] = None
        ds_dict['private_tests'][0]['is_valid_test'] = None
        ds_dict['generated_tests'][0]['is_valid_test'] = None
        data_provider.dataset[split_name] = Dataset.from_dict(ds_dict)
    return data_provider

def problem_3_validation_fix(data_provider):
    # problem 3 validation fix generated tests
    ind_problem_valid = 3
    split_name = 'valid'
    dataset_dict = data_provider.dataset[split_name].to_dict()
    p_3 = data_provider.dataset[split_name][ind_problem_valid]
    p_3_generated_tests = p_3['generated_tests']
    is_valid_test = [True] * len(p_3_generated_tests['input'])
    count_false = 0
    count_correct = 0
    for i, input in enumerate(p_3_generated_tests['input']):
        n, m, x = input.splitlines()[0].split()
        n = int(n)
        m = int(m)
        a = input.splitlines()[1].split()
        b = input.splitlines()[2].split()
        if (n != len(a) or m != len(b)):  # according to the description, they should be equal
            count_false += 1
            is_valid_test[i] = False
        else:
            count_correct += 1
    dataset_dict['generated_tests'][ind_problem_valid]['is_valid_test'] = is_valid_test
    data_provider.dataset[split_name] = Dataset.from_dict(dataset_dict)
    return data_provider

def problem_29_test_fix(data_provider):
    ind_problem_test = 29
    split_name = 'test'
    dataset_dict = data_provider.dataset[split_name].to_dict()
    p_29 = data_provider.dataset[split_name][ind_problem_test]
    p_29_generated_tests = p_29['generated_tests']
    is_valid_arr_generated = [True] * len(p_29_generated_tests['input'])
    for i, input in enumerate(p_29_generated_tests['input']):
        for l in input.split():
            l_n = np.array(list(map(int, l.split())))
            if any(l_n < 0):  # according to the description, they should be >=0
                is_valid_arr_generated[i] = False
                break

        s = input.split('\n', 1)
        n = int(s[0].strip())
        a = s[1].strip().split('\n')
        for j in range(n):
            num_elements = int(a[2 * j].strip())
            if num_elements != len(a[2 * j + 1].strip().split(' ')):  # according to the description, they should be equal
                is_valid_arr_generated[i] = False
                break


    dataset_dict['generated_tests'][ind_problem_test]['is_valid_test'] = is_valid_arr_generated
    data_provider.dataset[split_name] = Dataset.from_dict(dataset_dict)
    return data_provider

def problem_92_test_fix(data_provider):
    ind_problem_test = 92
    split_name = 'test'
    dataset_dict = data_provider.dataset[split_name].to_dict()
    p_92 = data_provider.dataset[split_name][ind_problem_test]
    p_92_private_tests = p_92['private_tests']
    is_valid_arr_private = [True] * len(p_92_private_tests['input'])
    for i, input in enumerate(p_92_private_tests['input']):
        if len(set(
                input)) != 4:  # {'a', 'b',  '1', '\n'} - according to the description, the string should contain only 'a' and 'b'
            is_valid_arr_private[i] = False

    p_92_generated_tests = p_92['generated_tests']
    is_valid_arr_generated = [True] * len(p_92_generated_tests['input'])
    for i, input in enumerate(p_92_generated_tests['input']):
        if len(set(
                input)) != 4:  # {'a', 'b',  '1', '\n'} - according to the description, the string should contain only 'a' and 'b'
            is_valid_arr_generated[i] = False

    dataset_dict['generated_tests'][ind_problem_test]['is_valid_test'] = is_valid_arr_generated
    dataset_dict['private_tests'][ind_problem_test]['is_valid_test'] = is_valid_arr_private
    data_provider.dataset[split_name] = Dataset.from_dict(dataset_dict)
    return data_provider

if __name__ == "__main__":
    preapare_and_clean_dataset()
