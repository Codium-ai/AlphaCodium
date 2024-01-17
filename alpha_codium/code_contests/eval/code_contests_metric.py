# Copyright 2020 The HuggingFace Datasets Authors and the current dataset script contributor.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""The CodeContestsEval metric estimates the pass@k metric for code synthesis.
This is an evaluation harness for the code_contests problem solving dataset
described in the paper "Evaluating Large Language Models Trained on Code"
(https://arxiv.org/abs/2107.03374)."""
import itertools
import os

import datasets
import evaluate
import numpy as np

from alpha_codium.code_contests.eval.code_test_runners import PythonTestsRunner

local_runner = 'local'
code_contests_runner = 'code_contests'


_CITATION = """\

"""

_DESCRIPTION = """\
This metric implements the evaluation harness for Deepmind's code_contests dataset.
"""

_KWARGS_DESCRIPTION = """
Calculates how good are predictions given some references, using certain scores
Args:
    predictions: list of candidates to evaluate. Each candidates should be a list
        of strings with several code candidates to solve the problem.
    references: a list with a test for each prediction. Each test should evaluate the
        correctness of a code candidate.
    k: number of code candidates to consider in the evaluation (Default: [1, 10, 100])
    num_workers: number of workers used to evaluate the canidate programs (Default: 4).
    timeout:
Returns:
    pass_at_k: dict with pass rates for each k
    results: dict with granular results of each unittest
Examples:
    >>> code_eval = evaluate.load("code_eval")
    >>> test_cases = ["assert add(2,3)==5"]
    >>> candidates = [["def add(a,b): return a*b", "def add(a, b): return a+b"]]
    >>> pass_at_k, results = code_eval.compute(references=test_cases, predictions=candidates, k=[1, 2])
    >>> print(pass_at_k)
    {'pass@1': 0.5, 'pass@2': 1.0}
"""

_WARNING = """
################################################################################
                                  !!!WARNING!!!
################################################################################
The "code_eval" metric executes untrusted model-generated code in Python.
Although it is highly unlikely that model-generated code will do something
overtly malicious in response to this test suite, model-generated code may act
destructively due to a lack of model capability or alignment.
Users are strongly encouraged to sandbox this evaluation suite so that it
does not perform destructive actions on their host or network. For more
information on how OpenAI sandboxes its code, see the paper "Evaluating Large
Language Models Trained on Code" (https://arxiv.org/abs/2107.03374).

Once you have read this disclaimer and taken appropriate precautions,
set the environment variable HF_ALLOW_CODE_EVAL="1". Within Python you can to this
with:

>>> import os
>>> os.environ["HF_ALLOW_CODE_EVAL"] = "1"

################################################################################\
"""

_LICENSE = """The MIT License

Copyright (c) OpenAI (https://openai.com)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE."""


os.environ["HF_ALLOW_CODE_EVAL"] = "1"

@evaluate.utils.file_utils.add_start_docstrings(_DESCRIPTION, _KWARGS_DESCRIPTION)
class CodeContestsEval(evaluate.Metric):
    def _info(self):
        if self.config_name not in [
            local_runner, code_contests_runner
        ]:
            raise KeyError(
                "You should supply a configuration name selected in "
                f'[{code_contests_runner}, {local_runner}]'
            )
        return evaluate.MetricInfo(
            # This is the description that will appear on the metrics page.
            description=_DESCRIPTION,
            citation=_CITATION,
            inputs_description=_KWARGS_DESCRIPTION,
            # This defines the format of each prediction and reference
            features=datasets.Features(
                {
                    "predictions": {
                        "task_name": datasets.Value("string"),
                        "solution_candidates": datasets.Sequence(
                            datasets.Value("string")
                        ),
                    },
                    "references": {
                        "tests_inputs": datasets.Sequence(datasets.Value("string")),
                        "tests_outputs": datasets.Sequence(datasets.Value("string")),
                    },
                }
            ),
            homepage="",
            codebase_urls=[""],
            reference_urls=[""],
            license=_LICENSE,
        )

    def _compute(
        self,
        predictions,
        references,
        k=[1, 10, 100],  # noqa: B006
        num_workers=10,
        timeout=3.0,
    ):
        if os.getenv("HF_ALLOW_CODE_EVAL", 0) != "1":
            raise ValueError(_WARNING)

        if os.name == "nt":
            raise NotImplementedError(
                "This metric is currently not supported on Windows."
            )
        runner = PythonTestsRunner.factory(self.config_name)
        inputs, results = runner.bulk_test(num_workers, predictions, references)
        correct, total = self.pass_fail_ratio(results)
        total = np.array(total)
        correct = np.array(correct)
        ks = k
        pass_at_k = {
            f"pass@{k}": estimate_pass_at_k(total, correct, k).mean()
            for k in ks
            if (total >= k).all()
        }

        return pass_at_k, inputs, results

    def pass_fail_ratio(self, results):
        total, correct = [], []
        for task_id, all_candidates_test_results in results.items():
            print(task_id)
            print("======================================")
            candidate_final_results = []
            for candidate_id, test_results in enumerate(all_candidates_test_results):
                _results = [
                    test_result.passed for test_result in test_results.test_results
                ]
                print(f"{candidate_id} test results: {_results}")
                candidate_pass_fail = all(_results)
                print(f"{candidate_id} final pass/fail: {candidate_pass_fail}")
                candidate_final_results.append(candidate_pass_fail)
            total.append(len(candidate_final_results))
            correct.append(sum(candidate_final_results))
            print(f"{task_id} candidates: {candidate_final_results}")
            print("======================================")
        return correct, total


def estimate_pass_at_k(num_samples, num_correct, k):
    """Estimates pass@k of each problem and returns them in an array."""

    def estimator(n: int, c: int, k: int) -> float:
        """Calculates 1 - comb(n - c, k) / comb(n, k)."""
        if n - c < k:
            return 1.0
        return 1.0 - np.prod(1.0 - k / np.arange(n - c + 1, n + 1))

    if isinstance(num_samples, int):
        num_samples_it = itertools.repeat(num_samples, len(num_correct))
    else:
        assert len(num_samples) == len(num_correct)
        num_samples_it = iter(num_samples)

    return np.array(
        [estimator(int(n), int(c), k) for n, c in zip(num_samples_it, num_correct)]
    )
