import subprocess

def getFileType(path:str) -> str:
    """
    Returns the type of the file in the path.\n
    :param `str` path: Path to get the file type from.
    :returns: Returns the file extension if one is found.
    :rtype: `str`
    """
    #Guard clause if the path is empty
    if path:
        #Look for the last dot in the path
        for i in range(len(path) - 1, 0, - 1):
            if path[i] == '.':
                return path[i:]
            

def getScore(pathToScript, pathToFiles: object):
    """
    Returns the score for the inputs for the script.\n
    :param pathToScript: Path to the script to run.
    :param `object` pathToFiles: Path or list of paths to give to the script.
    :returns: Returns the result of the script execution.
    """
    #Get the script file type
    fileType = getFileType(pathToScript)

    #Make sure the files are stored in a list
    if isinstance(pathToFiles, str):
        files = [pathToFiles]
    else:
        files = pathToFiles

    #Run the script from its file type
    if fileType == ".py":
        return runPythonScript(pathToScript,files)

def runPythonScript(pathToSript, pathToFiles):
    """
    Run the python script at the path with the given files.\n
    :param pathToSript: Path to the python script to run.
    :param pathToFiles: List of files to give as arguments to the script.
    :returns: Returns the completed subprocess result.
    """
    #Create the base command
    argumentArray =["python", pathToSript]

    #Add the input files as arguments
    for _, file in enumerate(pathToFiles):
        argumentArray.append(file)

    #Run the script and get the result
    result = subprocess.run(argumentArray,
                            capture_output=True,
                            check=True,
                            timeout=15)
    return result