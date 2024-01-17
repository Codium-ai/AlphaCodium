import difflib
import functools
import logging
from alpha_codium.settings.config_loader import get_settings
from alpha_codium.llm.ai_invoker import send_inference
from alpha_codium.log import get_logger

logger = get_logger(__name__)


async def run_fix_code_from_tests_failure(self, problem,error_str):
    counter_retry = 0
    while True:
        try:
            problem['error_str'] = error_str
            f = functools.partial(self._run, problem=problem, prompt="code_contests_prompt_fix_solution")
            response_fixed_code, _ = await send_inference(f)
            problem['error_str'] = ''

            # some cleaning
            response_fixed_code = response_fixed_code.rstrip("'` \n") # remove trailing spaces and newlines from yaml response
            if response_fixed_code.startswith("```python"):
                response_fixed_code = response_fixed_code[10:]
            problem['code_recent_solution'] = response_fixed_code

            # diff patch
            diff = difflib.unified_diff(problem['code_prev_solution'].splitlines(keepends=True),
                                        response_fixed_code.splitlines(keepends=True))
            # patch = ''.join(diff)
            # if get_settings().solve.reduce_verbose:
            #     logger.debug(f"diff:\n{patch}")
            # else:
            #     logger.info(f"diff:\n{patch}")

            return problem

        except Exception as e:
            logging.error(f"fix_code_from_tests_failure' stage, counter_retry {counter_retry}, Error: {e}")
            counter_retry += 1
            if counter_retry > 2:
                raise e


