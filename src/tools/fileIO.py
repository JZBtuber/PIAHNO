from src.tools.setting import GlobalSettings
import json
import os


def getDelayFromParent(filePath: str, parentPath: str, workingPath: str) -> int:
    """
    Get the saved delay between a file and its parent file.\n
    :param `str` filePath: Path to the child file.
    :param `str` parentPath: Path to the parent file.
    :param `str` workingPath: Working path of the app.
    :returns: Returns the saved delay if it exists, otherwise returns `0`.
    :rtype: `int`
    """
    # Guard clause if one of the paths does not exist
    if not os.path.exists(filePath) or not os.path.exists(parentPath):
        return 0

    # Get the parent delay file path
    delayPath = os.path.join(os.getcwd(), "data", "ParentDelays.json")

    # Guard clause if the delay file does not exist
    if not os.path.exists(delayPath):
        return 0

    # Try to load the delay data
    try:
        with open(delayPath, "r", encoding="utf-8") as file:
            data = json.load(file)
    except (json.JSONDecodeError, OSError):
        return 0

    # Get the delay from the saved data
    return data.get("files", {}).get(filePath, {}).get(parentPath, 0)


def setDelayForParent(filePath: str, parentPath: str, workingPath: str, delay: int):
    """
    Save the delay relative to the parent for the children.\n
    :param `str` filePath: Path to the child file.
    :param `str` parentPath: Path to the parent file.
    :param `str` workingPath: Working path of the app.
    :param `int` delay: Delay to save.
    """
    # Guard clause if one of the paths does not exist
    if not os.path.exists(filePath) or not os.path.exists(parentPath):
        return

    # Create the delay data paths
    dataDir = os.path.join(os.getcwd(), "data")
    delayPath = os.path.join(dataDir, "ParentDelays.json")

    # Create the data directory if needed
    os.makedirs(dataDir, exist_ok=True)

    # Set default data
    data = {"files": {}}

    # Load the existing delay data if it exists
    if os.path.exists(delayPath):
        try:
            with open(delayPath, "r", encoding="utf-8") as file:
                data = json.load(file)
        except (json.JSONDecodeError, OSError):
            data = {"files": {}}

    # Create the files section if needed
    if "files" not in data:
        data["files"] = {}

    # Create the child file section if needed
    if filePath not in data["files"]:
        data["files"][filePath] = {}

    # Save the delay under the child and parent paths
    data["files"][filePath][parentPath] = delay

    # Write the delay data to the file
    with open(delayPath, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4, ensure_ascii=False)


def saveSettings() -> None:
    """
    **Saving the app settings.**\n
    Saving and overwriting the settings of the app to
    settings.json in the current working directory.
    """
    # Get the settings file path
    path = os.path.join(os.getcwd(), "settings.json")

    # Write the global settings to the file
    with open(path, "w", encoding="utf-8") as file:
        json.dump(GlobalSettings, file, indent=4, ensure_ascii=False)


def loadSettings() -> None:
    """
    **Loading the app settings.** \n
    Loading the settings for the current session from 
    settings.json in the current working directory.
    """
    # Get the settings file path
    path = os.path.join(os.getcwd(), "settings.json")

    # Load the settings if the file exists
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as file:
                data = json.load(file)
                GlobalSettings.update(data)
        except (json.JSONDecodeError, OSError):
            return


def saveScripts(paths: list[str]) -> None:
    """
    Save the scripts to load next time.\n
    :param `list[str]` paths: List of paths to save.
    """
    # Get the scripts file path
    path = os.path.join(os.getcwd(), "scripts.json")

    # Write the script paths to the file
    with open(path, "w", encoding="utf-8") as file:
        json.dump({"Scripts": paths}, file, indent=4, ensure_ascii=False)


def loadScripts():
    """
    Load the paths to the scripts.\n
    :returns: Returns the saved script paths if they exist.
    """
    # Get the scripts file path
    path = os.path.join(os.getcwd(), "scripts.json")

    # Load the script paths if the file exists
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as file:
                data = json.load(file)
                return data["Scripts"]
        except (json.JSONDecodeError, OSError):
            return
