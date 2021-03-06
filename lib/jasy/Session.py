#
# Jasy - JavaScript Tooling Framework
# Copyright 2010-2011 Sebastian Werner
#

import logging, itertools, time, atexit, json
from jasy.core.Permutation import Permutation
from jasy.core.Translation import Translation
from jasy.core.Info import *
from jasy.core.Profiler import *
from jasy.core.LocaleData import *

from jasy.Project import Project
from jasy.File import *
from jasy.Resolver import Resolver
from jasy.Optimization import Optimization
from jasy.Combiner import Combiner
from jasy.Sorter import Sorter


def toJSON(obj, sort_keys=False):
    return json.dumps(obj, separators=(',',':'), ensure_ascii=False, sort_keys=sort_keys)
    

class Session():
    def __init__(self):
        atexit.register(self.close)

        self.__timestamp = time.time()
        self.__projects = []
        self.__localeProjects = {}
        self.__fields = {}
        
        self.addProject(Project(coreProject()))
    
    
    #
    # Project Managment
    #
        
    def addProject(self, project, main=False):
        """ Adds the given project to the list of known projects """
        
        self.__projects.append(project)
        
        # That's the project from where all paths are computed
        if main:
            logging.info("Main project is: %s" % project.getName())
            self.__mainProject = project

        # Import project defined fields which might be configured using "activateField()"
        fields = project.getFields()
        for name in fields:
            entry = fields[name]

            if name in self.__fields:
                raise Exception("Field '%s' was already defined!" % (name))

            if "check" in entry:
                check = entry["check"]
                if check in ["Boolean", "String", "Number"] or type(check) == list:
                    pass
                else:
                    raise Exception("Unsupported check: '%s' for field '%s'" % (check, name))
                    
            if "detect" in entry:
                detect = entry["detect"]
                if not self.getClass(detect):
                    raise Exception("Field '%s' uses unknown detection class %s." % (name, detect))
                
            self.__fields[name] = entry
        
        
    def getProjects(self, permutation=None):
        """ 
        Returns all currently known projects.
        Automatically adds the currently configured locale project.
        """
        
        # Dynamically add the locale matching CLDR project to the list
        dyn = []
        
        if permutation:
            locale = permutation.get("locale")
            if locale != None and locale != "default":
                if not locale in self.__localeProjects:
                    localePath = localeProject(locale)
                    if not os.path.exists(localePath):
                        storeLocale(locale)
                
                    self.__localeProjects[locale] = Project(localePath)
            
                dyn.append(self.__localeProjects[locale])
        
        return dyn + self.__projects
        
        
    def getMainProject(self):
        """
        The main project is basically the project with the currently running build script
        """
        
        return self.__mainProject
        
        
    def getRelativePath(self, project):
        """ Returns the relative path of any project to the main project """
        mainProject = self.__mainProject
        
        mainPath = mainProject.getPath()
        projectPath = project.getPath()
        
        return os.path.relpath(projectPath, mainPath)
        
        
        
    def getClass(self, className):
        """
        Queries all currently known projects for the given class and returns the class object
        """
        for project in self.__projects:
            classes = project.getClasses()
            if className in classes:
                return classes[className]
        

    
    #
    # Core
    #
        
    def clearCache(self, permutation=None):
        """ Clears all caches of known projects """
        
        for project in self.getProjects():
            project.clearCache()

    def close(self):
        """ Closes the session and stores cache to the harddrive. """
        
        logging.info("Closing session...")
        for project in self.getProjects():
            project.close()
    
    
    #
    # Permutation Support
    #
    
    def setField(self, name, value):
        """
        Statically configure the value of the given field.
        
        This field is just injected into Permutation data and used for permutations, but as
        it only holds a single value all alternatives paths are removed/ignored.
        """
        
        if not name in self.__fields:
            raise Exception("Unsupported field (not defined by any project): %s" % name)

        entry = self.__fields[name]
        
        # Replace current value with single value
        entry["values"] = [value]
        
        # Additonally set the default
        entry["default"] = value

        # Delete detection if configured by the project
        if "detect" in entry:
            del entry["detect"]
        
        
    def permutateField(self, name, values=None, detect=None, default=None):
        """
        Adds the given key/value pair to the session for permutation usage.
        
        It supports an optional test. A test is required as soon as there is
        more than one value available. The detection method and values are typically 
        already defined by the project declaring the key/value pair.
        """
        
        if not name in self.__fields:
            raise Exception("Unsupported field (not defined by any project): %s" % name)

        entry = self.__fields[name]
            
        if values:
            if type(values) != list:
                values = [values]

            entry["values"] = values

            # Verifying values from build script with value definition in project manifests
            if "check" in entry:
                check = entry["check"]
                for value in values:
                    if check == "Boolean":
                        if type(value) == bool:
                            continue
                    elif check == "String":
                        if type(value) == str:
                            continue
                    elif check == "Number":
                        if type(value) in (int, float):
                            continue
                    else:
                        if value in check:
                            continue

                    raise Exception("Unsupported value %s for %s" % (value, name))
                    
            if default is not None:
                entry["default"] = default
                    
        elif "check" in entry and entry["check"] == "Boolean":
            entry["values"] = [True, False]
            
        elif "check" in entry and type(entry["check"]) == list:
            entry["values"] = entry["check"]
            
        elif "default" in entry:
            entry["values"] = [entry["default"]]
            
        else:
            raise Exception("Could not permutate field: %s! Requires value list for non-boolean fields which have no defaults." % name)

        # Store class which is responsible for detection (overrides data from project)
        if detect:
            if not self.getClass(detect):
                raise Exception("Could not permutate field: %s! Unknown detect class %s." % detect)
                
            entry["detect"] = detect
            
        
        
    def getPermutations(self):
        """
        Combines all values to a set of permutations.
        These define all possible combinations of the configured settings
        """

        fields = self.__fields
        values = { key:fields[key]["values"] for key in fields if "values" in fields[key] }
               
        # Thanks to eumiro via http://stackoverflow.com/questions/3873654/combinations-from-dictionary-with-list-values-using-python
        names = sorted(values)
        combinations = [dict(zip(names, prod)) for prod in itertools.product(*(values[name] for name in names))]
        permutations = [Permutation(combi, fields) for combi in combinations]

        return permutations


    def __exportFields(self):
        """
        Converts data from values to a compact data structure for being used to 
        compute a checksum in JavaScript.
        """
        
        #
        # Export structures:
        # 1. [ name, 1, test, [value1, ...] ]
        # 2. [ name, 2, value ]
        # 3. [ name, 3, test, default? ]
        #
        
        export = []
        for key in sorted(self.__fields):
            source = self.__fields[key]
            
            content = []
            content.append("'%s'" % key)
            
            # We have available values to permutate for
            if "values" in source:
                values = source["values"]
                if "detect" in source and len(values) > 1:
                    # EXPORT STRUCT 1
                    content.append("1")
                    content.append(source["detect"])

                    if "default" in source:
                        # Make sure that default value is first in
                        values = values[:]
                        values.remove(source["default"])
                        values.insert(0, source["default"])
                    
                    content.append(toJSON(values))
            
                else:
                    # EXPORT STRUCT 2
                    content.append("2")
                    content.append(toJSON(values[0]))

            # Has no relevance for permutation, just insert the test
            else:
                if "detect" in source:
                    # EXPORT STRUCT 3
                    content.append("3")

                    # Add detection class
                    content.append(source["detect"])
                    
                    # Add default value if available
                    if "default" in source:
                        content.append(toJSON(source["default"]))
                
                else:
                    # Has no detection and no permutation. Ignore it completely
                    continue
                
            export.append("[%s]" % ",".join(content))
            
        return "[%s]" % ",".join(export)

    
    
    def writeLoader(self, fileName, optimization=None, formatting=None):
        """
        Writes a so-called loader script to the given location. This script contains
        data about possible permutations based on current session values. It returns
        the classes which are included by the script so you can exclude it from the 
        real build files.
        """
        
        permutation = Permutation({
          "fields" : self.__exportFields()
        })
        
        resolver = Resolver(self.getProjects(), permutation)
        resolver.addClassName("jasy.Env")
        resolver.addClassName("jasy.io.Queue")
        resolver.addClassName("jasy.io.Script")
        resolver.addClassName("jasy.io.StyleSheet")
        classes = Sorter(resolver, permutation).getSortedClasses()
        compressedCode = Combiner(classes).getCompressedCode(permutation, None, optimization, formatting)
        writefile(fileName, compressedCode)
        
        return resolver.getIncludedClasses()
    
    
    
    
    #
    # Translation Support
    #
    
    def getAvailableTranslations(self):
        """ 
        Returns a set of all available translations 
        
        This is the sum of all projects so even if only one 
        project supports fr_FR then it will be included here.
        """
        
        supported = set()
        for project in self.__projects:
            supported.update(project.getTranslations().keys())
            
        return supported
    
    
    def getTranslation(self, locale):
        """ 
        Returns a translation object for the given locale containing 
        all relevant translation files for the current project set. 
        """
        
        # Prio: de_DE => de => C (default locale) => Code
        check = [locale]
        if "_" in locale:
            check.append(locale[:locale.index("_")])
        check.append("C")
        
        files = []
        for entry in check:
            for project in self.__projects:
                translations = project.getTranslations()
                if translations and entry in translations:
                    files.append(translations[entry])
        
        return Translation(locale, files)

