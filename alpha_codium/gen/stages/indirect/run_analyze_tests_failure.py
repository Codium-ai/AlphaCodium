import difflib
import functools
import logging
import yaml

from alpha_codium.settings.config_loader import get_settings
from alpha_codium.llm.ai_invoker import send_inference
from alpha_codium.log import get_logger

logger = get_logger(__name__)


async def run_analyze_test_failure(self, problem,error_str):
    counter_retry = 0
    while True:
        try:
            problem['error_str'] = error_str
            f = functools.partial(self._run, problem=problem, prompt="code_contests_prompt_analyze_failure")
            response_analyze_failure, _ = await send_inference(f)
            problem['error_str'] = ''

            response_analyze_failure = response_analyze_failure.rstrip("'` \n") # remove trailing spaces and newlines from yaml response
            if response_analyze_failure.startswith("```yaml"):
                response_analyze_failure = response_analyze_failure[8:]
            problem['response_analyze_failure'] = response_analyze_failure
            response_analyze_failure_yaml = yaml.safe_load(response_analyze_failure)
            problem['what_went_wrong'] = response_analyze_failure_yaml['what_went_wrong']
            problem['fixed_flow'] = response_analyze_failure_yaml['fixed_flow']
            return problem
        except Exception as e:
            logging.error(f"'analyze_test_failure' stage, counter_retry {counter_retry}, Error: {e}")
            counter_retry += 1
            if counter_retry > 2:
                raise e