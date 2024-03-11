import functools
import logging
from alpha_codium.gen.stages.debug import exec_code, FunctionCall

from alpha_codium.gen.stages.indirect.run_validate_ai_test import run_validate_ai_tests
from alpha_codium.gen.utils import load_yaml
from alpha_codium.settings.config_loader import get_settings
from alpha_codium.llm.ai_invoker import send_inference
from alpha_codium.log import get_logger
import yaml

logger = get_logger(__name__)

def function_call_representer(dumper, obj):
    # Directly creating a representation dictionary including all fields
    # without filtering out None values, focusing on 'output' serialization

    inpp = (", ".join([repr(e) for e in obj.input[0]]) + ", ") if obj.input[0] else ""
    inpp += ", ".join([k+"="+repr(v) for k, v in obj.input[1].items()])

    node = {
        'function': obj.function,
        'input': repr(inpp) if inpp != None else None,
        # Serializing 'output' using its __repr__(), ensuring it's a string in the YAML
        'output': obj.output if obj.output != None else None,
        'exception': repr(obj.exception) if obj.exception != None else None,
        'calls': obj.calls,
    }
    return dumper.represent_dict(node.items())

def string_representer(dumper, data):
    return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')

yaml.add_representer(FunctionCall, function_call_representer)
yaml.add_representer(str, string_representer)

max_iter = 10
async def run_public_tests(self, problem):
    counter_retry = 0
    while True:
        try:
            logger.info("--debugging stage--")
            inputs = problem['public_tests']['input']
            outputs = problem['public_tests']['output']
            success_n = 0
            for _, (inp, outp) in enumerate(zip(inputs,outputs)):
                for iter in range(max_iter):
                    global_excep, callstack, output = exec_code(problem['code'], inp)
                    problem['test_input'] = inp
                    problem['test_output'] = outp
                    problem['output'] = output or ""
                    problem['global_excep'] = repr(global_excep) if global_excep else ""
                    problem['callstack_str'] = yaml.dump(callstack, allow_unicode=True, default_flow_style=False) if callstack else ""

                    if output == None or (output.strip() != outp.strip()):
                        logger.info(f"Failed to pass the test after {iter+1} attempts, the output is incorrect.")
                        if iter == max_iter - 1:
                            logger.info(f"Giving up.")
                            continue
                        else:
                            #TODO  Go through ALL functoin calls, if max output tokens allows.
                            f = functools.partial(self._run, problem=problem, prompt="code_contests_prompts_debug")
                            problem['callstack_analysis'], _ = await send_inference(f)

                            f = functools.partial(self._run, problem=problem, prompt="code_contests_prompts_fix_code")
                            fixed_code, _ = await send_inference(f)

                            fixed_code = fixed_code.rstrip("` \n")
                            if fixed_code.startswith("```python"):
                                fixed_code = fixed_code[10:]
                            elif fixed_code.startswith("python"):
                                fixed_code = fixed_code[6:]

                            problem['code'] = fixed_code
                            pass
                    else:
                        #TODO: take care of too long runtime.
                        success_n +=1
                        logger.info(f"Passed tests after {iter+1} attempts")
                        break

            logger.info(f"Passed {success_n} tests")
            return problem
        except Exception as e:
            logging.error(f"'tests' stage, counter_retry {counter_retry}, Error: {e}")
            counter_retry += 1
            if counter_retry > 2:
                raise e
