import functools
import logging

from alpha_codium.gen.stages.indirect.run_validate_ai_test import run_validate_ai_tests
from alpha_codium.gen.utils import load_yaml
from alpha_codium.settings.config_loader import get_settings
from alpha_codium.llm.ai_invoker import send_inference
from alpha_codium.log import get_logger

logger = get_logger(__name__)


async def run_code_structure_generation(self, problem):
    counter_retry = 0
    while True:
        try:
            logger.info("--code structure generation stage--")

            # get prompt
            f = functools.partial(self._run, problem=problem, prompt="code_contests_prompts_generate_code_structure")

            response_code, _ = await send_inference(f)

            # clean up the response
            response_code = response_code.rstrip("` \n")
            if response_code.startswith("```python"):
                response_code = response_code[10:]
            elif response_code.startswith("python"):
                response_code = response_code[6:]

            problem['code_structure'] = response_code
            return problem
        except Exception as e:
            logging.error(f"'code structure generation' stage, counter_retry {counter_retry}, Error: {e}")
            counter_retry += 1
            if counter_retry > 2:
                raise e
