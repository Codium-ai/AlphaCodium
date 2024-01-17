import copy
import functools
import logging
import yaml

from alpha_codium.gen.utils import load_yaml
from alpha_codium.settings.config_loader import get_settings
from alpha_codium.llm.ai_invoker import send_inference
from alpha_codium.log import get_logger

logger = get_logger(__name__)


async def run_generate_possible_solutions(self, problem):
    counter_retry = 0
    while True:
        try:
            logger.info("--generate possible solutions stage--")
            if get_settings().get("solve.use_direct_solutions", False):
                return problem

            # get settings
            problem['max_num_of_possible_solutions'] = get_settings().get('possible_solutions.max_num_of_possible_solutions')
            problem['use_test_explanations_possible_solutions'] = get_settings().get('possible_solutions.use_test_explanations')
            f = functools.partial(self._run, problem=problem, prompt="code_contests_prompt_generate_possible_solutions")

            # inference
            response_possible_solutions, _ = await send_inference(f)
            response_possible_solutions_yaml = load_yaml(response_possible_solutions)

            if get_settings().get('possible_solutions.remove_bruce_force_solutions'):
                for i, s in enumerate(response_possible_solutions_yaml['possible_solutions']):
                    if 'brute' in s['name'].lower():
                        response_possible_solutions_yaml['possible_solutions'].pop(i)
                        response_possible_solutions = yaml.dump(response_possible_solutions_yaml, sort_keys=False, line_break="\n")
                        break
            problem['s_possible_solutions'] = response_possible_solutions_yaml['possible_solutions']
            problem['s_possible_solutions_str'] = response_possible_solutions.split('possible_solutions:')[1].strip()

            return problem
        except Exception as e:
            logging.error(f"'possible solutions' stage, counter_retry {counter_retry}, Error: {e}")
            counter_retry += 1
            if counter_retry > 2:
                raise e
