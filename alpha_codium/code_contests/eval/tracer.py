import pysnooper

from alpha_codium.settings.config_loader import get_settings

filter_out_lines = ["Starting var:",
                    "exec(",
                    "Source path:",
                    "globals_dict",
                    "tracer.py",
                    "snooping_inner_function()",
                    "run_generated_code",
                    "return function(*args, **kwargs)",
                    "source_line = source[line_no - 1]"
                    "Elapsed time:",
                    "Return value:.. None"]

snooper_kwargs = {
    'color': False,
    'relative_time': True,
    'normalize': True,
    'depth': get_settings().code_tester.trace_depth
}

snooper_kwargs_string = ", ".join(f"{key}={value}" for key, value in snooper_kwargs.items())


class FilteringTracer(pysnooper.tracer.Tracer):
    def trace(self, frame, event, arg):
        if not frame.f_code.co_filename == '<string>':
            return None

        return super().trace(frame, event, arg)


class MockSourceLoader:

    def __init__(self, source):
        self.source = source

    def get_source(self, module_name):
        return self.source

def wrap_solution(check_program):
    import_str = "import pysnooper as pysnooper\n"
    annotation = f"@custom_snoop(output=tracing, {snooper_kwargs_string})\n"
    entrypoint = "def run_code_contests_solution():\n"
    func_body = "\n".join([f"\t{line}" for line in check_program.split("\n")])
    invocation = "\nrun_code_contests_solution()"
    return (import_str + annotation + entrypoint + func_body + invocation).strip()


def trace_code(check_program, tracing):
    my_program = wrap_solution(check_program)
    # __name__  must be unique otherwise the tracer uses caching mechanisms that break it's behavior
    globals_dict = {'__loader__': MockSourceLoader(my_program),
                    'tracing': tracing,
                    '__name__': hash(my_program),
                    'custom_snoop': FilteringTracer}
    exec(my_program, globals_dict, {})


def clean_trace(trace_output):
    trace_lines = trace_output.split("\n")
    clean_lines = [line for line in trace_lines if not
    any(substring in line for substring in filter_out_lines)]
    clean_output = "\n".join(clean_lines)
    return clean_output
