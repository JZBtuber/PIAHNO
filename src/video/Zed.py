import numpy as np
from src.tools.setting import GlobalSettings
import json
try:
    import pyzed.sl as sl
except Exception as exc:
    sl = None
    _pyzed_import_error = exc


class Zed():
    """
    Wrapper for the Zed depth camera.\n
    It opens the camera, reads images and point cloud data, and gives access to depth/camera parameters.
    """

    def __init__(self, filePath, live):
        """
        Create and open the Zed camera.\n
        :param filePath: Path to the input file if file mode is used.
        :param live: If `True`, the camera is opened as a live input.
        """
        if sl is None:
            raise RuntimeError(f"pyzed.sl is not available: {_pyzed_import_error}")

        # Create the Zed input type
        self.InputType = sl.InputType()
        self.fps = 30

        # Set live mode options
        if live:
            self.svoMode = False

        # Create the Zed camera object
        self.zed = sl.Camera()

        # Choose the camera resolution from global settings
        if GlobalSettings["zedResolution"] == "VGA":
            resolution = sl.RESOLUTION.VGA
        elif GlobalSettings["zedResolution"] == "HD720":
            resolution = sl.RESOLUTION.HD720
        elif GlobalSettings["zedResolution"] == "HD1080":
            resolution = sl.RESOLUTION.HD1080
        elif GlobalSettings["zedResolution"] == "HD2K":
            resolution = sl.RESOLUTION.HD2K
        else:
            resolution = sl.RESOLUTION.HD1080

        # Choose the depth mode from global settings
        if GlobalSettings["zedMode"] == "Neural_Light":
            mode = sl.DEPTH_MODE.NEURAL_LIGHT
        elif GlobalSettings["zedMode"] == "Neural":
            mode = sl.DEPTH_MODE.NEURAL
        elif GlobalSettings["zedMode"] == "Neural_Complete":
            mode = sl.DEPTH_MODE.NEURAL_PLUS
        else:
            mode = sl.DEPTH_MODE.NEURAL_LIGHT

        # Create and configure the Zed initialization parameters
        self.init_params = sl.InitParameters(input_t=self.InputType)
        self.init_params.camera_resolution = resolution
        self.init_params.camera_fps = GlobalSettings["zedFps"]
        self.init_params.depth_mode = mode
        self.init_params.coordinate_units = sl.UNIT.METER
        self.init_params.depth_minimum_distance = GlobalSettings["zedDepthMin"]
        self.init_params.depth_maximum_distance = GlobalSettings["zedDepthMax"]

        # Open the camera
        err = self.zed.open(self.init_params)
        if err != sl.ERROR_CODE.SUCCESS:
            self.zed.close()
            raise RuntimeError(f"Failed to open ZED camera: {err!r}")

        # Create and set RuntimeParameters after opening the camera
        self.runtime_parameters = sl.RuntimeParameters()

        # Setting the depth confidence parameters
        self.runtime_parameters.confidence_threshold = int(GlobalSettings.get("zedConfidenceThreshold", 40))

        # Get Camera Calibration Parameters
        camera_info = self.zed.get_camera_information()
        self.camera_params = camera_info.camera_configuration.calibration_parameters.left_cam

        # Save camera intrinsics
        self.fx = self.camera_params.fx  # Focal length in pixels (x-axis)
        self.fy = self.camera_params.fy  # Focal length in pixels (y-axis)
        self.cx = self.camera_params.cx  # X-coordinate of the principal point
        self.cy = self.camera_params.cy  # Y-coordinate of the principal point

        # Declare image, depth, point cloud
        self.image = sl.Mat()
        self.depth = sl.Mat()
        self.point_cloud = sl.Mat()
        self.confidence_map = sl.Mat()

        # Set default numpy image variables
        self.img = None
        self.depth_img = None
        self.point_cloud_img = None
        self.confidence_img = None

    def read(self):
        """
        Read the next Zed frame.\n
        :returns: Returns `(True, image)` if a frame was read, otherwise `(False, None)`.
        """
        # Grab the next frame
        if self.zed.grab(self.runtime_parameters) != sl.ERROR_CODE.SUCCESS:
            return False, None

        # Retrieve image and point cloud data
        self.zed.retrieve_image(self.image, sl.VIEW.LEFT)
        self.zed.retrieve_measure(self.point_cloud, sl.MEASURE.XYZ, sl.MEM.CPU)

        # Convert the Zed matrices to numpy arrays
        self.img = self.image.get_data()
        self.point_cloud_img = self.point_cloud.get_data()

        return True, self.img

    def get_image(self):
        """
        Retrieve the image, confidence view, point cloud and confidence map.
        """
        # Retrieve left rectified image
        self.zed.retrieve_image(self.image, sl.VIEW.LEFT)

        # Retrieve depth map. Depth is aligned on the left image
        self.zed.retrieve_image(self.depth, sl.VIEW.CONFIDENCE)

        # Retrieve colored point cloud. Point cloud is aligned on the left image.
        self.zed.retrieve_measure(
            self.point_cloud, sl.MEASURE.XYZRGBA, sl.MEM.CPU)

        # Retrieve confidence map.
        self.zed.retrieve_measure(
            self.confidence_map, sl.MEASURE.CONFIDENCE, sl.MEM.CPU)

        # Convert Zed image to numpy array
        self.img = self.image.get_data()
        self.depth_img = self.depth.get_data()

    def getFps(self):
        """
        Get the current camera or SVO frame rate.\n
        :returns: Returns the camera frame rate.
        """
        # Use SVO file FPS if in SVO mode
        if self.svoMode:
            fps = self.zed.get_camera_information().camera_configuration.fps
            return fps if fps > 0 else 30.0

        return self.init_params.camera_fps

    def getFpsCount(self):
        """
        Get the number of frames in the SVO file.\n
        :returns: Returns the SVO frame count if in SVO mode, otherwise returns `0`.
        """
        # Return the SVO frame count only in SVO mode
        if self.svoMode:
            return self.zed.get_svo_number_of_frames()
        else:
            return 0

    def getFrameCount(self):
        """
        Get the number of frames in the SVO file.\n
        :returns: Returns the SVO frame count if in SVO mode, otherwise returns `0`.
        """
        # Return the SVO frame count only in SVO mode
        if self.svoMode:
            return self.zed.get_svo_number_of_frames()
        return 0

    def close(self):
        """
        Close the Zed camera.
        """
        self.zed.close()

    def saveCameraParameters(self, path):
        """
        Save the camera parameters to a JSON file.\n
        :param path: Path where the camera parameter file will be saved.
        """
        # Write camera parameters as JSON
        with open(path, "w", encoding="utf-8") as file:
            json.dump(self._getCameraParametersDict(), file, indent=4)

    def getDepthAt(self, x, y):
        """
        Get the depth value at a pixel position.\n
        :param x: X position in the image.
        :param y: Y position in the image.
        :returns: Returns the depth value if valid, otherwise returns `None`.
        """
        # Get the depth value at the selected pixel
        err, depth_value = self.depth.get_value(int(x), int(y))

        # Return the depth if it is valid
        if err == sl.ERROR_CODE.SUCCESS and np.isfinite(depth_value):
            return float(depth_value)

        return None

    def getPointAt(self, x, y):
        """
        Get the 3D point at a pixel position.\n
        :param x: X position in the image.
        :param y: Y position in the image.
        :returns: Returns `(x, y, z)` if valid, otherwise returns `None`.
        """
        # Get the 3D point at the selected pixel
        err, point = self.point_cloud.get_value(int(x), int(y))

        # Return the point if it is valid
        if err == sl.ERROR_CODE.SUCCESS:
            x3d, y3d, z3d, rgba = point

            if np.isfinite(x3d) and np.isfinite(y3d) and np.isfinite(z3d):
                return float(x3d), float(y3d), float(z3d)

        return None

    def _getCameraParametersDict(self):
        """
        Get the camera parameters as a dictionary.\n
        :returns: Returns the camera parameters and depth settings.
        :rtype: `dict`
        """
        # Create the camera parameter dictionary
        return {
            "camera_model": "ZED",
            "units": "meters",

            "resolution": {
                "width": self.camera_params.image_size.width,
                "height": self.camera_params.image_size.height
            },

            "left_camera": {
                "fx": float(self.camera_params.fx),
                "fy": float(self.camera_params.fy),
                "cx": float(self.camera_params.cx),
                "cy": float(self.camera_params.cy),

                "disto": [float(x) for x in self.camera_params.disto],
                "v_fov": float(self.camera_params.v_fov),
                "h_fov": float(self.camera_params.h_fov),
                "d_fov": float(self.camera_params.d_fov)
            },

            "depth": {
                "minimum_distance": float(self.init_params.depth_minimum_distance),
                "maximum_distance": float(self.init_params.depth_maximum_distance)
            },

            "fps": float(self.fps)
        }
