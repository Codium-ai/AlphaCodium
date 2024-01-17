import copy
import functools
import logging
import yaml

from alpha_codium.settings.config_loader import get_settings
from alpha_codium.gen.utils import postprocess_response
from alpha_codium.llm.ai_invoker import send_inference
from alpha_codium.log import get_logger

logger = get_logger(__name__)


async def run_validate_self_reflect(self, problem):
    try:
        logger.info("--validate reflection stage--")
        f = functools.partial(self._run, problem=problem, prompt="code_contests_prompts_validate_reflection")

        # inference
        response_validate_reflect, _ = await send_inference(f)
        response_validate_reflect = response_validate_reflect.rstrip("` \n")
        try:
            response_validate_reflect_yaml = yaml.safe_load(response_validate_reflect)
        except yaml.YAMLError:
            response_validate_reflect = postprocess_response(response_validate_reflect)  # try to include only the yaml part
            response_validate_reflect_yaml = yaml.safe_load(response_validate_reflect)

        # check number of tests
        actual_number_of_tests = len(problem['public_tests']['input'])
        calculated_number_of_tests = len(response_validate_reflect_yaml['fixed_tests_explanations'])
        if actual_number_of_tests != calculated_number_of_tests:
            raise (f"Error: number of tests in validate self-reflection ({calculated_number_of_tests}) "
                   f"does not match the actual number of tests ({actual_number_of_tests})")

        problem['response_validate_self_reflect'] = response_validate_reflect
        problem['tests_explanations'] = response_validate_reflect_yaml['fixed_tests_explanations']
        problem['tests_explanations_str'] = response_validate_reflect.split('tests_explanations:')[1]

        # re-order the public tests from easiest to hardest
        problem['public_tests']['original'] = copy.deepcopy(problem['public_tests'])
        problem['public_tests']['input'] = [t['input'] for t in problem['tests_explanations']]
        problem['public_tests']['output'] = [t['output'] for t in problem['tests_explanations']]
        problem['public_tests']['explanation'] = [t['explanation'] for t in problem['tests_explanations']]

        return problem
    except Exception as e:
        logging.error(f"Failed 'run_validate_self_reflect', Error: {e}")
        return problem
