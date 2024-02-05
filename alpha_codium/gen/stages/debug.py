
import inspect
from functools import wraps
import types
from alpha_codium.log import get_logger


logger = get_logger(__name__)

def log_inputs_outputs_errors(func, calls):
    @wraps(func)
    def wrapper(*args, **kwargs):
        arg_str = ", ".join([f"{repr(arg)}" for arg in args])
        kwarg_str = ", ".join([f"{key}={repr(value)}" for key, value in kwargs.items()])
        logger.debug(f"Calling {func.__name__} with arguments: {arg_str}, {kwarg_str}")

        exception_info = None
        return_val = None
        try:
            return_val = func(*args, **kwargs)
            logger.debug(f"{func.__name__} returned: {repr(return_val)}")
        except Exception as e:
            exception_info = e
            logger.debug(f"Error in {func.__name__}: {str(e)}")
            #raise  # Re-raise the exception
        finally:
            # Store the call information including exception if any
            calls.append({"func":func.__name__, "args":args, "kwargs":kwargs, "return_val":return_val, "excep":exception_info})
            return return_val
    return wrapper

def apply_logging_decorator_to_module(module, calls):
    for name, obj in inspect.getmembers(module):
        if inspect.isfunction(obj):
            setattr(module, name, log_inputs_outputs_errors(obj, calls))

def exec_code(code, inp):
    #TODO Timeout
    #TODO multiple inputs
    # Step 1: Convert candidate code to a module

    candidate_module = types.ModuleType("code_module")
    exec(code, candidate_module.__dict__)

    calls = []
    # Step 2: Apply logging decorator to all functions in the candidate module
    apply_logging_decorator_to_module(candidate_module, calls)

    # Now, when you call functions from my_module, the decorator will log inputs, outputs, and errors
    inputs = inp.strip().split('\n')
    inputs = iter(inputs)  # Create an iterator over the inputs

    # Define a new input function that returns the next item from the iterator
    #original_input = candidate_module.__dict__['__builtins__']['input']  # Backup the original input function
    candidate_module.__dict__['__builtins__']['input'] = lambda prompt='': next(inputs)

    captured_outputs = []  # List to store captured print outputs

    # Custom print function that captures outputs
    def custom_print(*args, **kwargs):
        captured_outputs.append(' '.join(map(str, args)))

    candidate_module.__dict__['__builtins__']['print'] = custom_print

    try:
        candidate_module.main()  # Call the main function with the overridden input
    finally:
        pass
        #__builtins__.input = original_input  # Restore the original input function
    return calls, '\n'.join(captured_outputs)

