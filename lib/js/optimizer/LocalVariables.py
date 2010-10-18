#
# JavaScript Tools - Optimizer for local variable names
# Copyright 2010 Sebastian Werner
#

from js.tokenizer.Tokenizer import keywords
from copy import copy
import string, logging

__all__ = ["optimize"]

empty = ("null", "this", "true", "false", "number", "string", "regexp")


#
# Public API
#

def optimize(node, translate=None, pos=0):
    if node.type == "script" and hasattr(node, "parent"):
        # before going into a function scope, make a copy of the parent scope
        # to not modify the parent scope and badly influence the variable length
        # of other child scopes
        translate = {} if not translate else copy(translate)
        pos = __optimizeScope(node, translate, pos)
        
    for child in node:
        optimize(child, translate, pos)
      


#
# Implementation
#

def baseEncode(num, alphabet=string.ascii_letters):
    if (num == 0):
        return alphabet[0]
    arr = []
    base = len(alphabet)
    while num:
        rem = num % base
        num = num // base
        arr.append(alphabet[rem])
    arr.reverse()
    return "".join(arr)
    

def __encode(pos):
    repl = None
    while repl == None or repl in keywords:
        repl = baseEncode(pos)
        pos += 1
        
    return pos, repl
        
      
def __optimizeScope(node, translate, pos):
    logging.debug("Optimize scope at line: %s", node.line)
    
    parent = getattr(node, "parent", None)
    if parent and parent.type == "function" and hasattr(parent, "params"):
        for i, param in enumerate(parent.params):
            pos, translate[param.value] = __encode(pos)
            param.value = translate[param.value]

    functions = getattr(node, "functions", None)
    if functions:
        for name in functions:
            # Need to check whether a param with that name already exists
            if not name in translate:
                pos, translate[name] = __encode(pos)

    variables = getattr(node, "variables", None)
    if variables:
        for name in variables:
            # Need to check whether a param with that name already exists
            if not name in translate:
                pos, translate[name] = __encode(pos)
        
    __optimizeNode(node, translate, True)
    return pos


def __optimizeNode(node, translate, first=False):
    nodeType = node.type

    # function names
    if nodeType == "function" and hasattr(node, "name") and node.name in translate:
        # logging.debug("Function Name: %s => %s", node.name, translate[node.name])
        node.name = translate[node.name]

    # declarations
    elif nodeType == "declaration":
        name = getattr(node, "name", None)
        if name and name in translate:
            # logging.debug("Variable Declaration: %s => %s", node.name, translate[node.name])
            node.name = translate[node.name]
        else:
            names = getattr(node, "names", None)
            if names:
                for child in names:
                    if child.value in translate:
                        # logging.debug("Variable Destructed Declaration: %s => %s", child.value, translate[child.value])
                        child.value = translate[child.value]

    # every scope relevant identifier (e.g. first identifier for dot-operator, etc.)
    elif nodeType == "identifier" and node.value in translate and getattr(node, "scope", False):
        # logging.debug("Scope Variable: %s => %s", node.value, translate[node.value])
        node.value = translate[node.value]    

    # Don't recurse into types which never have children
    # Don't recurse into closures. These are processed by __optimizeScope later
    if not nodeType in empty and (first or not nodeType == "script"):
        for child in node:
            __optimizeNode(child, translate, False)
