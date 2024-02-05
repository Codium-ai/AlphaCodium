import functools
import logging
from alpha_codium.gen.stages.debug import exec_code

from alpha_codium.gen.stages.indirect.run_validate_ai_test import run_validate_ai_tests
from alpha_codium.gen.utils import load_yaml
from alpha_codium.settings.config_loader import get_settings
from alpha_codium.llm.ai_invoker import send_inference
from alpha_codium.log import get_logger

logger = get_logger(__name__)

iter_num = 10
async def run_public_tests(self, problem):
    counter_retry = 0
    while True:
        try:
            logger.info("--tests stage--")
            inputs = problem['public_tests']['input']
            outputs = problem['public_tests']['output']
            success_n = 0
            for i, (inp, outp) in enumerate(zip(inputs,outputs)):
                for iter in range(iter_num):
                    success = True
                    calls, output = exec_code(problem['code'], inp)
                    #check output of main()
                    # if (not calls[-1]['excep']) and calls[-1]['return_val'] == outp:
                    #     success = True
                    #     break
                    for call in calls:
                        problem['call'] = call
                        if call['excep']:
                            success = False
                            # get prompt
                            f = functools.partial(self._run, problem=problem, prompt="code_contests_prompts_fix_solution")
                            logger.info(f"Failed to pass the test after {iter+1} attempts, there was an exception.")
                            fixed_code, _ = await send_inference(f)
                            # clean up the response
                    if success:
                        if output.strip() != outp.strip():
                            success = False
                            logger.info(f"Failed to pass the test after {iter+1} attempts, the output is incorrect.")
                            #tell LLM that there was no exceptions, but the outputs do not match
                            #let LLM check input/output of each method.
                            f = functools.partial(self._run, problem=problem, prompt="code_contests_prompts_fix_solution")
                            fixed_code, _ = await send_inference(f)

                    if success:
                        success_n +=1
                        logger.info(f"Passed tests after {iter+1} attempts")
                        break
                    elif iter < iter_num - 1:
                        fixed_code = fixed_code.rstrip("` \n")
                        if fixed_code.startswith("```python"):
                            fixed_code = fixed_code[10:]
                        elif fixed_code.startswith("python"):
                            fixed_code = fixed_code[6:]

                        problem['code'] = fixed_code
                    else:
                        #FIXME LLM calls in the last iteratoin are useless
                        logger.info(f"Giving up.")

            logger.info(f"Passed {success_n} tests")
            return problem
        except Exception as e:
            logging.error(f"'tests' stage, counter_retry {counter_retry}, Error: {e}")
            counter_retry += 1
            if counter_retry > 2:
                raise e