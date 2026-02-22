"""Sample Python workflow for testing."""


def run(ctx):
    ctx.log("python workflow executed")
    result = ctx.run("echo from_python")
    return result
