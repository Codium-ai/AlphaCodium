import inspect
from functools import wraps
import types
from alpha_codium.log import get_logger
import traceback
from pydantic import BaseModel
from typing import Any, List, Optional


logger = get_logger(__name__)

import functools
import yaml

class FunctionCall(BaseModel):
    function: str
    input: Any = None
    output: Any = None
    exception: Optional[str] = None
    calls: List['FunctionCall'] = []

FunctionCall.update_forward_refs()

def log_function_call(func, call_stack):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        func_input = args if args else kwargs
        call_info = FunctionCall(
            function=func.__name__,
            input= (args, kwargs)
        )

        # Append call_info to the calls list of the last item in call_stack if it exists
        if call_stack:
            call_stack[-1].calls.append(call_info)

        # Always push the current call_info onto the call_stack
        call_stack.append(call_info)

        try:
            result = func(*args, **kwargs)
            call_info.output = result
            return result
        except Exception as e:
            call_info.exception = str(e)
            if len(call_stack) > 1:
                raise
        finally:
            # Pop the current call_info from the call_stack
            if len(call_stack) > 1:
                call_stack.pop()

    return wrapper


def exec_code(code, inp):
    #TODO Timeout
    #TODO multiple inputs
    # Step 1: Convert candidate code to a module

    candidate_module = types.ModuleType("code_module")
    #TODO What if the code has syntax error?
    try:
        exec(code, candidate_module.__dict__)
    except Exception as e:
        return e, None, None

    call_stack = []
    # Step 2: Apply logging decorator to all functions in the candidate module
    for name, obj in inspect.getmembers(candidate_module):
        if inspect.isfunction(obj):
            setattr(candidate_module, name, log_function_call(obj, call_stack))

    # Now, when you call functions from my_module, the decorator will log inputs, outputs, and errors
    inputs = inp.strip().split('\n')
    inputs = iter(inputs)  # Create an iterator over the inputs

    # Define a new input function that returns the next item from the iterator
    #original_input = candidate_module.__dict__['__builtins__']['input']  # Backup the original input function
    candidate_module.__dict__['input'] = lambda prompt='': next(inputs)

    captured_outputs = []  # List to store captured print outputs

    # Custom print function that captures outputs
    def custom_print(*args, **kwargs):
        end = kwargs.get('end', '\n')  # Get 'end' from kwargs or use '\n' as default
        captured_outputs.append(' '.join(map(str, args)) + end)

    candidate_module.__dict__['print'] = custom_print

    try:
        candidate_module.main()
    except Exception as e:
        print(e)
    finally:
        pass
        #__builtins__.input = original_input  # Restore the original input function
    return None, call_stack[0], ''.join(captured_outputs)
