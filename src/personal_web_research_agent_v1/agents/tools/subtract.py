from langchain_core.tools import tool

@tool
def subtract(a: int, b: int):
    """Subtraction function that subtracts b from a"""
    print("subtraction tool is being used")
    return a - b