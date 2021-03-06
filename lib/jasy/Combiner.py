#
# Jasy - JavaScript Tooling Framework
# Copyright 2010-2011 Sebastian Werner
#

import logging, os, random

__all__ = ["Combiner"]


class Combiner():
    """ Combines the code/path of a list of classes into one string """
    
    def __init__(self, classList):
        self.__classList = classList
        
    
    def getCombinedCode(self):
        """ Combines the unmodified content of the stored class list """

        return "".join([classObj.getText() for classObj in self.__classList])
    
    
    def getCompressedCode(self, permutation=None, translation=None, optimization=None, format=None):
        """ Combines the compressed result of the stored class list """

        return "".join([classObj.getCompressed(permutation, translation, optimization, format) for classObj in self.__classList])


    def getLoaderCode(self, bootCode, relativeRoot, session):
        logging.info("Generating loader...")

        files = []
        for classObj in self.__classList:
            project = classObj.getProject()

            fromMainProjectRoot = os.path.join(session.getRelativePath(project), project.getClassPath(True), classObj.getLocalPath())
            fromWebFolder = os.path.relpath(fromMainProjectRoot, relativeRoot).replace(os.sep, '/')

            files.append('"%s"' % fromWebFolder)

        loader = ",".join(files)
        boot = "function(){%s}" % bootCode if bootCode else ""
        result = 'jasy.io.Queue.load([%s], %s, null, true)' % (loader, boot)

        return result