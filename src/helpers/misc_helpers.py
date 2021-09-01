def format_execute(input_content):
    executing_string = """async def temp_func():
    {}
""".format(input_content.partition("```")[2].strip("`").replace("\n", "    \n    "))
    return executing_string
