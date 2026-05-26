from src.tools.setting import GlobalSettings
import json
import os


def getDelayFromParent(filePath: str, parentPath: str, workingPath: str) -> int:
    if not os.path.exists(filePath) or not os.path.exists(parentPath):
        return 0

    delayPath = os.path.join(os.getcwd(), "data", "ParentDelays.json")

    if not os.path.exists(delayPath):
        return 0

    try:
        with open(delayPath, "r", encoding="utf-8") as file:
            data = json.load(file)
    except (json.JSONDecodeError, OSError):
        return 0

    return data.get("files", {}).get(filePath, {}).get(parentPath, 0)


def setDelayForParent(filePath: str, parentPath: str, workingPath: str, delay: int):
    if not os.path.exists(filePath) or not os.path.exists(parentPath):
        return

    dataDir = os.path.join(os.getcwd(), "data")
    delayPath = os.path.join(dataDir, "ParentDelays.json")

    os.makedirs(dataDir, exist_ok=True)

    data = {"files": {}}

    if os.path.exists(delayPath):
        try:
            with open(delayPath, "r", encoding="utf-8") as file:
                data = json.load(file)
        except (json.JSONDecodeError, OSError):
            data = {"files": {}}

    if "files" not in data:
        data["files"] = {}

    if filePath not in data["files"]:
        data["files"][filePath] = {}

    data["files"][filePath][parentPath] = delay

    with open(delayPath, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4, ensure_ascii=False)


def saveSettings() -> None:
    """
    **Saving the app settings.**
    Saving and overwriting the settings of the app to
    settings.json in the current working directory"""
    path = os.path.join(os.getcwd(), "settings.json")

    with open(path, "w", encoding="utf-8") as file:
        json.dump(GlobalSettings, file, indent=4, ensure_ascii=False)


def loadSettings() -> None:
    """
    **Loading the app settings.** 
    Loading the settings for the current session from 
    settings.json in the current working directory.
    """
    path = os.path.join(os.getcwd(), "settings.json")

    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as file:
                 data = json.load(file)
                 GlobalSettings.update(data)
        except (json.JSONDecodeError, OSError):
            return