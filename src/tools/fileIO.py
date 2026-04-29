import json
import os


@staticmethod
def getDelayFromParent(filePath: str, parentPath: str, workingPath: str) -> int:

    if not os.path.exists(filePath) or not os.path.exists(parentPath):
        return 0
    
    if not os.path.exists(f"{workingPath}\data\ParentDelays.json"):
        return 0

    with open(f"{workingPath}\data\ParentDelays.json", "r") as file:
        jsonObject = json.loads(file.read())
        
        print(filePath)
        print(parentPath)

        if filePath in jsonObject["files"]:
            if parentPath in jsonObject["files"][filePath]:
                return jsonObject["files"][filePath][parentPath]
        return 0
    
@staticmethod
def setDelayForParent(filePath:str, parentPath:str, workingPath:str, delay: int):

    data = []

    if not os.path.exists(filePath) or not os.path.exists(parentPath):
        return 
    
    if not os.path.exists(f"{workingPath}\data"):
        os.makedirs(f"{workingPath}\data")
    
    with open(f"{workingPath}\data\ParentDelays.json", "r") as file:
        data = json.loads(file.read())

    if filePath in data["files"]:
        if parentPath in data["files"][filePath]:
            data["files"][filePath][parentPath] = delay

        else:
            data["files"][filePath][parentPath] = delay

    else:
        data["files"][filePath] = {parentPath : delay}


    with open(f"{workingPath}\data\ParentDelays.json", "w") as file:
        json.dump(data, file, indent=4, ensure_ascii=False)