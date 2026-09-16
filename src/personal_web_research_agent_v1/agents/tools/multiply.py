from langchain_core.tools import tool

@tool
def multiply(a: int, b: int):
    """Multiplication function that multiplies two numbers together"""
    print("multiplication tool is being used")
    return a * b