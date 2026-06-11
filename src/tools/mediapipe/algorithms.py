import cv2
import os
import numpy as np
import mediapipe as mp
from src.tools.setting import GlobalSettings


class mediaWork():
    """
    Wrapper for Mediapipe hand detection and hand landmark processing.\n
    It can draw 2D hands, draw hands using depth data, or return detected hand points.
    """

    def __init__(self):
        """
        Create the Mediapipe hand landmarker.
        """
        # Get Mediapipe classes
        baseOptions = mp.tasks.BaseOptions
        handLandmarker = mp.tasks.vision.HandLandmarker
        handLandmarkerOptions = mp.tasks.vision.HandLandmarkerOptions
        visionRunningMode = mp.tasks.vision.RunningMode

        # Get detection settings from global settings
        detectionConfidence = GlobalSettings["detectionConfidence"]
        presenceConfidence = GlobalSettings["presenceConfidence"]
        trackingConfidence = GlobalSettings["trackingConfidence"]

        # Get the hand landmark model path
        model_path = os.path.join(os.path.dirname(
            __file__), "hand_landmarker.task")

        # Create the hand landmarker options
        options = handLandmarkerOptions(
            base_options=baseOptions(model_asset_path=model_path),
            running_mode=visionRunningMode.VIDEO,
            num_hands=2,
            min_hand_detection_confidence=detectionConfidence,
            min_hand_presence_confidence=presenceConfidence,
            min_tracking_confidence=trackingConfidence
        )

        # Create the hand landmarker
        self.hands = handLandmarker.create_from_options(options)

        # Set Mediapipe hand connections
        self.HAND_CONNECTIONS = [
            (0, 1), (1, 2), (2, 3), (3, 4),
            (0, 5), (5, 6), (6, 7), (7, 8),
            (0, 9), (9, 10), (10, 11), (11, 12),
            (0, 13), (13, 14), (14, 15), (15, 16),
            (0, 17), (17, 18), (18, 19), (19, 20),
            (5, 9), (9, 13), (13, 17)
        ]

        # Set default variables
        self.wrist = []
        self.results = None
        self.timeStamp = 0

    def draw2dHands(self, img, fps, onlyBlack=False):
        """
        Detect and draw 2D hand landmarks on an image.\n
        :param img: Image to process.
        :param fps: Source frame rate.
        :param onlyBlack: If `True`, draw only the landmarks on a black image, defaults to `False`.
        :returns: Returns the annotated image.
        """
        # Find hands in the image
        img = self._findHands(img, fps)

        # Get 2D landmark positions
        data = self._findPosition2D(img)

        # Draw the landmarks
        img = self._drawLandmarks(img, data, onlyBlack)
        return img

    def draw3dHands(self, img, fps, pcl, cameraParameters, onlyBlack=False):
        """
        Detect and draw hand landmarks using depth data.\n
        :param img: Image to process.
        :param fps: Source frame rate.
        :param pcl: Point cloud data used to get 3D positions.
        :param cameraParameters: Camera parameters used with the point cloud.
        :param onlyBlack: If `True`, draw only the landmarks on a black image, defaults to `False`.
        :returns: Returns the annotated image.
        """
        # Find hands in the image
        img = self._findHands(img, fps)

        # Get landmark positions with depth data
        data = self._findPositionDepth(img, pcl, cameraParameters)

        # Draw the landmarks
        img = self._drawLandmarks(img, data, onlyBlack)
        return img

    def get3dpoints(self, img, fps, pcl=None, cameraParameters=None):
        """
        Get hand points from an image.\n
        If point cloud and camera parameters are given, 3D points are returned.\n
        Otherwise, 2D landmark data is returned.\n
        :param img: Image to process.
        :param fps: Source frame rate.
        :param pcl: Point cloud data, defaults to `None`.
        :param cameraParameters: Camera parameters, defaults to `None`.
        :returns: Returns left and right hand point arrays.
        """
        # Find hands in the image
        img = self._findHands(img, fps)

        # Use depth data if available
        if pcl is not None and cameraParameters is not None:
            return self._findPositionDepth(img, pcl, cameraParameters)
        else:
            return self._findPosition2D(img)

    def _findHands(self, img, fps):
        """
        Run Mediapipe hand detection on an image.\n
        :param img: Image to process.
        :param fps: Source frame rate.
        :returns: Returns the RGB image used by Mediapipe.
        """
        # Convert the image to RGB
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        # Create the Mediapipe image
        mpImage = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        # Detect hands for the current video timestamp
        self.results = self.hands.detect_for_video(
            mpImage, int(self.timeStamp))

        # Update the timestamp
        safeFps = fps if fps > 10 else 30
        self.timeStamp += 1000 / safeFps
        return rgb

    def _findPositionDepth(self, img, pcl, cameraParameters):
        """
        Get 2D and 3D hand landmark positions from the current detection results.\n
        :param img: RGB image used for detection.
        :param pcl: Point cloud data used to get 3D positions.
        :param cameraParameters: Camera parameters used with the point cloud.
        :returns: Returns the left and right hand landmark arrays.
        """
        # Get image size
        h, w, _ = img.shape

        # Set default hand data
        leftData = []
        rightData = []

        # Guard clause if no hands were detected
        if not self.results.hand_landmarks:
            return np.array(leftData), np.array(rightData)

        # Process every detected hand
        for idx, landmarks in enumerate(self.results.hand_landmarks):
            category_name = self.results.handedness[idx][0].category_name
            handData = []

            # Process every landmark
            for _, landmark in enumerate(landmarks):
                px = landmark.x * w
                py = landmark.y * h

                # Set default 3D coordinates
                x3D = None
                y3D = None
                z3D = None

                # Get point cloud data at the landmark position
                if np.isfinite(px) and np.isfinite(py):
                    if 0 <= px < w and 0 <= py < h:
                        ix = int(px)
                        iy = int(py)

                        # Get point from Zed point cloud object
                        if hasattr(pcl, "get_value"):
                            err, pointCloudValue = pcl.get_value(ix, iy)

                            if err != 0:
                                pointCloudValue = None

                        # Get point from numpy point cloud array
                        else:
                            pointCloudValue = pcl[iy, ix]

                        # Save the 3D coordinates if valid
                        if pointCloudValue is not None:
                            tx = pointCloudValue[0]
                            ty = pointCloudValue[1]
                            tz = pointCloudValue[2]

                            if np.isfinite(tx) and np.isfinite(ty) and np.isfinite(tz):
                                x3D = float(tx)
                                y3D = float(ty)
                                z3D = float(tz)

                # Always keep the 2D point so drawing still works.
                handData.append([px, py, x3D, y3D, z3D])

            # Save hand data by handedness
            if category_name == "Left":
                leftData = handData
            elif category_name == "Right":
                rightData = handData

        return np.array(leftData, dtype=object), np.array(rightData, dtype=object)

    def _findPosition2D(self, img):
        """
        Get 2D hand landmark positions from the current detection results.\n
        :param img: RGB image used for detection.
        :returns: Returns the left and right hand landmark arrays.
        """
        # Set default hand data
        leftData = []
        rightData = []

        # Get image size
        h, w, _ = img.shape

        # Process every detected hand
        if self.results.hand_landmarks:
            for idx, landmarks in enumerate(self.results.hand_landmarks):
                category_name = self.results.handedness[idx][0].category_name

                # Process every landmark
                for landmark in landmarks:
                    coords = [landmark.x * w, landmark.y * h,
                              landmark.x, landmark.y, landmark.z]

                    # Save landmark by handedness
                    if category_name == "Left":
                        leftData.append(coords)
                    elif category_name == "Right":
                        rightData.append(coords)

        return np.array(leftData), np.array(rightData)

    def _drawLandmarks(self, img, data, black):
        """
        Draw hand landmarks and connections on an image.\n
        :param img: Image to draw on.
        :param data: Left and right hand landmark arrays.
        :param black: If `True`, draw on a black image.
        :returns: Returns the annotated image.
        """
        # Create the output image
        annotated = np.zeros_like(img) if black else np.copy(img)

        # Get left and right hand data
        leftData, rightData = data

        # Draw each hand
        for handData in [leftData, rightData]:
            # Guard clause if the hand is incomplete
            if len(handData) != 21:
                continue

            # Draw every hand point
            for point in handData:
                x = point[0]
                y = point[1]

                # Skip invalid points
                if not np.isfinite(x) or not np.isfinite(y):
                    continue

                cv2.circle(
                    annotated,
                    (int(x), int(y)),
                    5,
                    (0, 255, 0),
                    -1
                )

            # Draw hand connections
            for a, b in self.HAND_CONNECTIONS:
                x1 = handData[a][0]
                y1 = handData[a][1]
                x2 = handData[b][0]
                y2 = handData[b][1]

                # Skip invalid connections
                if not (
                    np.isfinite(x1) and np.isfinite(y1) and
                    np.isfinite(x2) and np.isfinite(y2)
                ):
                    continue

                cv2.line(
                    annotated,
                    (int(x1), int(y1)),
                    (int(x2), int(y2)),
                    (0, 255, 0),
                    2
                )

        return annotated
