import ast
import difflib
import functools
import logging
import yaml
from alpha_codium.llm.ai_invoker import send_inference
from alpha_codium.log import get_logger
from alpha_codium.settings.config_loader import get_settings

logger = get_logger(__name__)


async def run_analyze_and_fix_test_failure(self, problem, error_str):
    counter_retry = 0
    while True:
        try:
            problem['error_str'] = error_str
            f = functools.partial(self._run, problem=problem, prompt=choose_prompt())
            response_analyze_failure, _ = await send_inference(f)
            problem['error_str'] = ''

            response_analyze_failure = response_analyze_failure.rstrip("'` \n") # remove trailing spaces and newlines from yaml response
            if response_analyze_failure.startswith("```yaml"):
                response_analyze_failure = response_analyze_failure[8:]
            response_analyze_failure_yaml = yaml.safe_load(response_analyze_failure)
            problem['response_analyze_failure'] = response_analyze_failure
            code_recent_solution = response_analyze_failure_yaml['fixed_code'].rstrip("'` \n")

            # some cleaning
            if code_recent_solution .startswith("```python"):
                code_recent_solution= code_recent_solution[10:]
            elif code_recent_solution.startswith("python"):
                code_recent_solution = code_recent_solution[6:]
            try:
                ast.parse(code_recent_solution)
            except:
                code_recent_solution_fallback = '\n'.join(code_recent_solution.splitlines()[:-1]).rstrip("'` \n")
                try:
                    ast.parse(code_recent_solution_fallback)
                    code_recent_solution = code_recent_solution_fallback
                except:
                    logger.error(f"Invalid code:\n{code_recent_solution}")
                    return problem
            problem['code_recent_solution'] = code_recent_solution

            # diff patch
            diff = difflib.unified_diff(problem['code_prev_solution'].splitlines(keepends=True),
                                        problem['code_recent_solution'].splitlines(keepends=True))
            # patch = ''.join(diff)
            # if get_settings().solve.reduce_verbose:
            #     logger.debug(f"diff:\n{patch}")
            # else:
            #     logger.info(f"diff:\n{patch}")

            return problem
        except Exception as e:
            logging.error(f"'analyze_and_fix_test_failure' stage, counter_retry {counter_retry}, Error: {e}")
            counter_retry += 1
            if counter_retry > 2:
                raise e

def choose_prompt():
    if get_settings().get("solve.use_direct_solutions", False):
        return "code_contests_prompt_analyze_and_fix_direct"
    else:
        return "code_contests_prompt_analyze_and_fix"
