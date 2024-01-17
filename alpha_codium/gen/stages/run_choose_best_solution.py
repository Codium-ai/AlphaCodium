import functools
import logging
from alpha_codium.llm.ai_invoker import send_inference
from alpha_codium.log import get_logger
from alpha_codium.gen.utils import load_yaml
from alpha_codium.settings.config_loader import get_settings

logger = get_logger(__name__)


async def run_choose_best_solution(self, problem):
    counter_retry = 0
    while True:
        try:
            logger.info("--choose best solution stage--")

            # get settings
            f = functools.partial(self._run, problem=problem, prompt=choose_prompt())

            # inference
            response_best_solution, _ = await send_inference(f)
            response_best_solution_yaml = load_yaml(response_best_solution,
                                                    keys_fix_yaml=["name:", "content:", "why:", "- "])

            # update best solution
            problem['s_best_solution'] = response_best_solution
            if 's_possible_solutions' in problem:
                problem['s_other_solutions'] = []
                for solution in problem['s_possible_solutions']:
                    if solution['name'] != response_best_solution_yaml['name']:
                        problem['s_other_solutions'].append(solution)

            return problem
        except Exception as e:
            logging.error(f"'run_choose_best_solution' stage, counter_retry {counter_retry}, Error: {e}")
            counter_retry += 1
            if counter_retry > 2:
                raise e


def choose_prompt():
    if get_settings().get("solve.use_direct_solutions", False):
        return "code_contests_prompts_choose_best_solution_direct"
    else:
        return "code_contests_prompts_choose_best_solution"