import numpy as np
from src.tools.setting import GlobalSettings
import json
try:
    import pyrealsense2 as rs
except Exception as exc:
    rs = None
    _realsense_import_error = exc


class RealSens():
    """
    Wrapper for the realsens depth camera.\n
    It opens the camera, reads images and point cloud data, and gives access to depth/camera parameters.
    """

    def __init__(self, filePath, live):
        """
        Create and open the RealSense camera.\n
        :param filePath: Path to the input bag file if file mode is used.
        :param live: If `True`, the camera is opened as a live input.
        """
        if rs is None:
            raise RuntimeError(f"pyrealsense2 is not available: {_realsense_import_error}")

        self.live = live
        self.svoMode = False
        self.fps = 30
        self.width = 848
        self.height = 480
        self.min_depth = 0.2
        self.max_depth = 1.5

        self.pipeline = rs.pipeline()
        self.config = rs.config()

        if not live and filePath:
            rs.config.enable_device_from_file(self.config, filePath, repeat_playback=False)

        self.config.enable_stream(
            rs.stream.color,
            self.width,
            self.height,
            rs.format.bgr8,
            self.fps
        )
        self.config.enable_stream(
            rs.stream.depth,
            self.width,
            self.height,
            rs.format.z16,
            self.fps
        )

        self.profile = self.pipeline.start(self.config)
        self.align = rs.align(rs.stream.color)

        depth_sensor = self.profile.get_device().first_depth_sensor()
        depth_sensor.set_option(rs.option.visual_preset, 4)
        self.depth_scale = float(depth_sensor.get_depth_scale())

        color_profile = self.profile.get_stream(
            rs.stream.color).as_video_stream_profile()
        self.camera_params = color_profile.get_intrinsics()

        self.fx = self.camera_params.fx
        self.fy = self.camera_params.fy
        self.cx = self.camera_params.ppx
        self.cy = self.camera_params.ppy

        # Native SDK point cloud generator (mirrors ZED's hardware-side
        # retrieve_measure(XYZ) instead of computing deprojection in Python)
        self.pc = rs.pointcloud()

        self.img = None
        self.depth_img = None
        self.point_cloud = None
        self.point_cloud_img = None

    def read(self):
        """
        Read the next RealSense frame.\n
        :returns: Returns `(True, image)` if a frame was read, otherwise `(False, None)`.
        """
        try:
            frames = self.pipeline.wait_for_frames()
        except RuntimeError:
            return False, None

        aligned_frames = self.align.process(frames)
        color_frame = aligned_frames.get_color_frame()
        depth_frame = aligned_frames.get_depth_frame()

        if not color_frame or not depth_frame:
            return False, None

        self.img = np.asanyarray(color_frame.get_data())
        self.depth_img = (
            np.asanyarray(depth_frame.get_data()).astype(np.float32)
            * self.depth_scale
        )
        points = self.pc.calculate(depth_frame)
        verts = np.asanyarray(points.get_vertices()).view(np.float32)
        verts = verts.reshape(self.height, self.width, 3)

        # Mask out points outside the configured depth range / invalid returns
        z = verts[:, :, 2]
        invalid = ~(np.isfinite(z) & (z != 0.0) & (z >= self.min_depth) & (z <= self.max_depth))
        verts[invalid] = np.nan

        self.point_cloud_img = verts
        self.point_cloud = verts

        return True, self.img

    def get_image(self):
        """
        Retrieve the current image and point cloud.
        """
        return self.read()

    def getFps(self):
        """
        Get the current camera frame rate.\n
        :returns: Returns the camera frame rate.
        """
        return self.fps

    def getFpsCount(self):
        """
        Get the number of frames in a recorded depth file.\n
        :returns: Returns `0` because RealSense live streams do not expose a count.
        """
        return 0

    def getFrameCount(self):
        """
        Get the number of frames in a recorded depth file.\n
        :returns: Returns `0` because RealSense live streams do not expose a count.
        """
        return 0

    def close(self):
        """
        Close the RealSense camera.
        """
        self.pipeline.stop()

    def saveCameraParameters(self, path):
        """
        Save the camera parameters to a JSON file.\n
        :param path: Path where the camera parameter file will be saved.
        """
        with open(path, "w", encoding="utf-8") as file:
            json.dump(self._getCameraParametersDict(), file, indent=4)

    def getDepthAt(self, x, y):
        """
        Get the depth value at a pixel position.\n
        :param x: X position in the image.
        :param y: Y position in the image.
        :returns: Returns the depth value if valid, otherwise returns `None`.
        """
        if self.depth_img is None:
            return None

        x = int(x)
        y = int(y)

        if y < 0 or y >= self.depth_img.shape[0] or x < 0 or x >= self.depth_img.shape[1]:
            return None

        depth_value = self.depth_img[y, x]

        if np.isfinite(depth_value) and depth_value > 0:
            return float(depth_value)

        return None

    def getPointAt(self, x, y):
        """
        Get the 3D point at a pixel position.\n
        :param x: X position in the image.
        :param y: Y position in the image.
        :returns: Returns `(x, y, z)` if valid, otherwise returns `None`.
        """
        if self.point_cloud_img is None:
            return None

        x = int(x)
        y = int(y)

        if y < 0 or y >= self.point_cloud_img.shape[0] or x < 0 or x >= self.point_cloud_img.shape[1]:
            return None

        point = self.point_cloud_img[y, x, :3]

        if np.all(np.isfinite(point)):
            return float(point[0]), float(point[1]), float(point[2])

        return None

    def _getCameraParametersDict(self):
        """
        Get the camera parameters as a dictionary.\n
        :returns: Returns the camera parameters and depth settings.
        :rtype: `dict`
        """
        return {
            "camera_model": "RealSense",
            "units": "meters",

            "resolution": {
                "width": int(self.camera_params.width),
                "height": int(self.camera_params.height)
            },

            "color_camera": {
                "fx": float(self.camera_params.fx),
                "fy": float(self.camera_params.fy),
                "cx": float(self.camera_params.ppx),
                "cy": float(self.camera_params.ppy),
                "disto": [float(x) for x in self.camera_params.coeffs],
                "distortion_model": str(self.camera_params.model)
            },

            "depth": {
                "scale": float(self.depth_scale),
                "minimum_distance": float(self.min_depth),
                "maximum_distance": float(self.max_depth)
            },

            "fps": float(self.fps)
        }
