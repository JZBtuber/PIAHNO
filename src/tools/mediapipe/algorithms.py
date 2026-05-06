import cv2
import os
import numpy as np
import mediapipe as mp



class mediaWork():
    def __init__(self, maxHands = 2, detectionConfidence = 0.90, trackingConfidence = 0.90):
        
        baseOptions = mp.tasks.BaseOptions
        handLandmarker = mp.tasks.vision.HandLandmarker
        handLandmarkerOptions = mp.tasks.vision.HandLandmarkerOptions
        visionRunningMode = mp.tasks.vision.RunningMode
        
        model_path = os.path.join(os.path.dirname(__file__), "hand_landmarker.task")
        
        options = handLandmarkerOptions(
            base_options=baseOptions(model_asset_path=model_path),
            running_mode=visionRunningMode.VIDEO,
            num_hands=maxHands,
            min_hand_detection_confidence=detectionConfidence,
            min_hand_presence_confidence=0.90,
            min_tracking_confidence=trackingConfidence
        )

        self.hands = handLandmarker.create_from_options(options)
        self.HAND_CONNECTIONS = [
        (0,1),(1,2),(2,3),(3,4),
        (0,5),(5,6),(6,7),(7,8),
        (0,9),(9,10),(10,11),(11,12),
        (0,13),(13,14),(14,15),(15,16),
        (0,17),(17,18),(18,19),(19,20),
        (5,9),(9,13),(13,17)
        ]

        self.wrist = []
        self.results = None
        self.timeStamp = 0


    def draw2dHands(self, img, fps, onlyBlack=False):
        img = self._findHands(img, fps)
        data = self._findPosition2D(img)
        img = self._drawLandmarks(img, data, onlyBlack)
        return img
    

    def draw3dHands(self, img, fps, pcl, cameraParameters, onlyBlack=False):
        img = self._findHands(img, fps)
        data = self._findPositionDepth(img, pcl, cameraParameters)
        img = self._drawLandmarks(img, data, onlyBlack)
        return img
    

    def get3dpoints(self, img, fps, pcl = None, cameraParameters = None):
        img = self._findHands(img, fps)

        if pcl is not None and cameraParameters is not None:
            return self._findPositionDepth(img, pcl, cameraParameters)
        else:
            return self._findPosition2D(img)


    def _findHands(self, img, fps):
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        mpImage = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        self.results = self.hands.detect_for_video(mpImage, int(self.timeStamp))
        
        safeFps = fps if fps > 10 else 30
        self.timeStamp += 1000 / safeFps
        return rgb
    
    def _findPositionDepth(self, img, pcl, cameraParameters):
        h, w, _ = img.shape
        leftData = []
        rightData = []

        if not self.results.hand_landmarks:
            return np.array(leftData), np.array(rightData)

        for idx, landmarks in enumerate(self.results.hand_landmarks):
            category_name = self.results.handedness[idx][0].category_name
            handData = []

            for id, landmark in enumerate(landmarks):
                px = landmark.x * w
                py = landmark.y * h

                x3D = None
                y3D = None
                z3D = None

                if np.isfinite(px) and np.isfinite(py):
                    if 0 <= px < w and 0 <= py < h:
                        ix = int(px)
                        iy = int(py)

                        if hasattr(pcl, "get_value"):
                            err, pointCloudValue = pcl.get_value(ix, iy)

                            if err != 0:
                                pointCloudValue = None
                        else:
                            pointCloudValue = pcl[iy, ix]

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

            if category_name == "Left":
                leftData = handData
            elif category_name == "Right":
                rightData = handData

        return np.array(leftData, dtype=object), np.array(rightData, dtype=object)


    def _findPosition2D(self, img):
        leftData = []
        rightData = []
        h, w, _ = img.shape

        if self.results.hand_landmarks:
            for idx, landmarks in enumerate(self.results.hand_landmarks):
                category_name = self.results.handedness[idx][0].category_name
                for landmark in landmarks:
                    coords = [landmark.x * w, landmark.y * h, landmark.x, landmark.y, landmark.z]
                    if category_name == "Left":
                        leftData.append(coords)
                    elif category_name == "Right":
                        rightData.append(coords)
        
        return np.array(leftData), np.array(rightData)
                    
    
    def _drawLandmarks(self, img, data, black):
        annotated = np.zeros_like(img) if black else np.copy(img)

        leftData, rightData = data

        for handData in [leftData, rightData]:
            if len(handData) != 21:
                continue

            for point in handData:
                x = point[0]
                y = point[1]

                if not np.isfinite(x) or not np.isfinite(y):
                    continue

                cv2.circle(
                    annotated,
                    (int(x), int(y)),
                    5,
                    (0, 255, 0),
                    -1
                )

            for a, b in self.HAND_CONNECTIONS:
                x1 = handData[a][0]
                y1 = handData[a][1]
                x2 = handData[b][0]
                y2 = handData[b][1]

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
    
    