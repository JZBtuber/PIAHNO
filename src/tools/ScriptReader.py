import subprocess

def getFileType(path:str) -> str:
    """
    Returns the type of the file in the path
    """
    if path:
        for i in range(len(path) - 1, 0, - 1):
            if path[i] == '.':
                return path[i:]
            

def getScore(pathToScript, pathToFiles: object):
    """
    Returns the score for the inputs for the script.
    """
    fileType = getFileType(pathToScript)

    if isinstance(pathToFiles, str):
        files = [pathToFiles]
    else:
        files = pathToFiles

    if fileType == ".py":
        return runPythonScript(pathToScript,files)

def runPythonScript(pathToSript, pathToFiles):
    """
    Run the python script at the path with the given files.
    """
    argumentArray =["python", pathToSript]

    for _, file in enumerate(pathToFiles):
        argumentArray.append(file)

    result = subprocess.run(argumentArray,
                            capture_output=True,
                            check=True,
                            timeout=15)
    return result
