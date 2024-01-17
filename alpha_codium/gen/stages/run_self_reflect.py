import functools
import logging
import yaml

from alpha_codium.gen.stages.indirect.run_fix_self_reflect import run_validate_self_reflect
from alpha_codium.settings.config_loader import get_settings
from alpha_codium.gen.utils import postprocess_response
from alpha_codium.llm.ai_invoker import send_inference
from alpha_codium.log import get_logger

logger = get_logger(__name__)


async def run_self_reflect(self, problem):
    counter_retry = 0
    while True:
        try:
            logger.info("--reflection stage--")

            # get settings
            validate_self_reflection = get_settings().get('self_reflection.validate_self_reflection', False)
            actual_number_of_tests = len(problem['public_tests']['input'])
            problem['actual_number_of_tests'] = actual_number_of_tests
            f = functools.partial(self._run, problem=problem, prompt="code_contests_prompt_reflect")

            # inference
            response_reflect, _ = await send_inference(f)
            response_reflect = response_reflect.rstrip("` \n")
            try:
                response_reflect_yaml = yaml.safe_load(response_reflect)
            except yaml.YAMLError:
                response_reflect = postprocess_response(response_reflect)  # try to include only the yaml part
                response_reflect_yaml = yaml.safe_load(response_reflect)

            # check number of tests
            actual_number_of_tests = len(problem['public_tests']['input'])
            calculated_number_of_tests = len(response_reflect_yaml['tests_explanations'])
            if actual_number_of_tests != calculated_number_of_tests:
                raise (f"Error: number of tests in self-reflection ({calculated_number_of_tests}) "
                       f"does not match the actual number of tests ({actual_number_of_tests})")
            problem['response_reflect'] = response_reflect
            try:
                problem['self_reflection'] = '- ' + '\n- '.join(response_reflect_yaml['self_reflection'])
                if problem['self_reflection'].startswith('- - '):
                    problem['self_reflection'] = problem['self_reflection'][2:]
            except:
                problem['self_reflection'] = response_reflect_yaml['self_reflection']
            problem['tests_explanations'] = response_reflect_yaml['tests_explanations']
            problem['tests_explanations_str'] = response_reflect.split('tests_explanations:')[1]

            # double validation self-reflection
            if validate_self_reflection:
                problem = await run_validate_self_reflect(self, problem)

            for s in problem['tests_explanations']:
                s['input'] = s['input'].replace('\\n', '\n')
                s['output'] = s['output'].replace('\\n', '\n')
                s['explanation'] = s['explanation'].replace('\\n', '\n')

            return problem
        except Exception as e:
            logging.error(f"'run_self_reflect' stage, counter_retry {counter_retry}, Error: {e}")
            counter_retry += 1
            if counter_retry > 2:
                raise e
