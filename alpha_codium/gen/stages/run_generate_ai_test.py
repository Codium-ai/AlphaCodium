import functools
import logging

from alpha_codium.gen.stages.indirect.run_validate_ai_test import run_validate_ai_tests
from alpha_codium.gen.utils import load_yaml
from alpha_codium.settings.config_loader import get_settings
from alpha_codium.llm.ai_invoker import send_inference
from alpha_codium.log import get_logger

logger = get_logger(__name__)


async def run_generate_ai_tests(self, problem):
    counter_retry = 0
    while True:
        try:
            logger.info("--generate ai tests stage--")

            # get settings
            validate_ai_tests = get_settings().get('generate_ai_tests.validate_ai_tests', False)
            problem['number_of_ai_tests'] = get_settings().get("generate_ai_tests.number_of_ai_tests", 8)
            problem['use_test_explanations_possible_solutions'] = get_settings().get('generate_ai_tests.use_test_explanations')

            # get prompt
            f = functools.partial(self._run, problem=problem, prompt="code_contests_prompts_generate_ai_tests")

            # inference
            response_problem_tests, _ = await send_inference(f)
            problem['problem_ai_tests'] = load_yaml(response_problem_tests,
                                                    keys_fix_yaml=["input:", "output:", "explanation:"])['tests']
            problem['problem_ai_simple_test'] = problem['problem_ai_tests'][0]

            if validate_ai_tests:
                problem = await run_validate_ai_tests(self, problem)

            # adding public tests to the beginning and end of the list, for the ai-iterate stage
            if get_settings().get('generate_ai_tests.add_public_tests_to_ai_tests', False):
                for public_input, public_output in zip(problem['public_tests']['input'],
                                                       problem['public_tests']['output']):
                    # to the beginning of the list
                    problem['problem_ai_tests'].insert(0, {'input': public_input, 'output': public_output})
                    # to the end of the list
                    problem['problem_ai_tests'].append({'input': public_input, 'output': public_output})

            return problem
        except Exception as e:
            logging.error(f"'generate ai tests' stage, counter_retry {counter_retry}, Error: {e}")
            counter_retry += 1
            if counter_retry > 2:
                raise e
