from langchain_core.tools import tool

@tool
def add(a: int, b: int):
    """This is an addition function that adds two numbers together"""
    print("addition tool is being used")
    return a + b

