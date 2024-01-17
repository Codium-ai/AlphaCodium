import functools
import logging

from alpha_codium.gen.utils import load_yaml
from alpha_codium.llm.ai_invoker import send_inference
from alpha_codium.log import get_logger

logger = get_logger(__name__)


async def run_validate_ai_tests(self, problem):
    counter_retry = 0
    while True:
        try:
            logger.info("--validate ai tests stage--")

            f = functools.partial(self._run, problem=problem, prompt="code_contests_prompts_validate_ai_tests")
            response_problem_tests, _ = await send_inference(f)
            problem['problem_ai_tests'] = load_yaml(response_problem_tests,
                                        keys_fix_yaml=["input:", "output:", "explanation", "what_was_wrong:"])['tests']

            # clean up and parse the response
            for p in problem['problem_ai_tests']:
                p['input'] = str(p['input']).replace('\\n', '\n')
                p['output'] = str(p['output']).replace('\\n', '\n')

            return problem
        except Exception as e:
            logging.error(f"'validate ai tests' stage, counter_retry {counter_retry}, Error: {e}")
            counter_retry += 1
            if counter_retry > 2:
                # raise e
                return problem
