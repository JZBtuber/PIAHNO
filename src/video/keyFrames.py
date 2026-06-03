from src.gui.Core import basicWindowWidget, basicWorker

from PyQt6.Qt3DExtras import Qt3DWindow, QOrbitCameraController, QSphereMesh, QPhongMaterial, QCylinderMesh
from PyQt6.QtGui import QVector3D, QQuaternion
from PyQt6.QtWidgets import QWidget, QFileDialog
from PyQt6.Qt3DCore import QEntity, QTransform
from PyQt6.QtCore import Qt, QThread, pyqtSignal, pyqtSlot

import numpy as np
import scipy.io


class KeyWorker(basicWorker):
    """
    Worker used to read key frame files and emit 3D points over time.
    """
    pointsReady = pyqtSignal(object)

    def __init__(self, path, isLive):
        """
        Create the key frame worker.\n
        :param path: Path to the key frame file.
        :param isLive: If `True`, the worker uses a live input.
        """
        super().__init__(path, isLive)

        # Set default variables
        self.rows = None
        self.frames = []
        self.frame_index = 0

    # ---------------------------------------------------------#
    # Workers's life time
    # ---------------------------------------------------------#

    def beforeLoop(self):
        """
        Load and prepare the key frame file before the main loop starts.\n
        :raises: `ValueError` if the key frame file has an incorrect format.
        """
        # Load the key frame file from its type
        if self.path[-4:] == ".npy":
            self.rows = np.load(self.path, allow_pickle=True)
        elif self.path[-4:] == ".csv":
            self.rows = np.loadtxt(self.path, delimiter=',')
        elif self.path[-4:] == ".mat":
            mat = scipy.io.loadmat(self.path)
            self.rows = mat["array"]

        # Guard clause if the loaded data does not have the expected format
        if self.rows.ndim != 2 or self.rows.shape[1] < 6:
            raise ValueError("KeyFrame file has incorrect format.")

        # Format:
        # col 0 = frame index
        # col 1 = timestamp in ms
        # col 2 = point id
        # col 3 = x
        # col 4 = y
        # col 5 = z

        # Get every unique frame ID
        frame_ids = np.unique(self.rows[:, 0]).astype(int)

        self.frames = []

        # Create one frame entry for each frame ID
        for frame_id in frame_ids:
            frame_rows = self.rows[self.rows[:, 0] == frame_id]

            # Guard clause if the frame has no rows
            if len(frame_rows) == 0:
                continue

            # Get the frame timestamp
            timestamp_ms = int(frame_rows[0, 1])

            # Sort by point id so point 0 always updates sphere 0, etc.
            frame_rows = frame_rows[np.argsort(frame_rows[:, 2])]

            # Get the 3D points
            points = frame_rows[:, 3:6].astype(float)

            self.frames.append((timestamp_ms, points))

        # Reset the frame index
        self.frame_index = 0

    def loop(self):
        """
        Emit every point frame that should be shown at the current master time.
        """
        # Stop if there are no frames left
        if self.frame_index >= len(self.frames):
            self.running = False
            return

        # Get current synchronized time
        now_ms = self.getMasterTimeMs()

        # Emit every frame that should already be shown
        while self.frame_index < len(self.frames):
            timestamp_ms, points = self.frames[self.frame_index]

            if timestamp_ms > now_ms:
                break

            self.pointsReady.emit(points)
            self.frame_index += 1

        QThread.msleep(1)

    def afterLoop(self):
        """
        Clear loaded key frame data after the worker stops.
        """
        # Clear loaded data
        self.rows = None
        self.frames = []


class KeyFeed(basicWindowWidget):
    """
    Widget used to display key frame hand points in 3D.
    """

    def __init__(self, ID: int, workingDir: str):
        """
        Create the key frame feed widget.\n
        :param `int` ID: ID of the widget.
        :param `str` workingDir: Working directory of the app.
        """
        super().__init__(KeyWorker, ID, workingDir=workingDir)

        # Set feed options
        self.inputType = "keyFrame"
        self.isLiveFeed = False

        # Set Mediapipe hand connections
        self.HAND_CONNECTIONS = [
            (0, 1, 6), (1, 2, 1), (2, 3, 1), (3, 4, 1),         # thumb
            (1, 5, 6), (5, 6, 2), (6, 7, 2), (7, 8, 2),         # index
            (5, 9, 6), (9, 10, 3), (10, 11, 3), (11, 12, 3),    # middle
            (9, 13, 6), (13, 14, 4), (14, 15, 4), (15, 16, 4),  # ring
            (13, 17, 6), (17, 18, 5), (18, 19, 5), (19, 20, 5),  # pinky
            (0, 17, 6),                                 # palm edge
        ]

        # Create the 3D view
        self.view = Qt3DWindow()
        self.container = QWidget.createWindowContainer(self.view)

        # Create the 3D root entity
        self.root = QEntity()
        self.view.setRootEntity(self.root)

        # Set the 3D background color
        self.view.defaultFrameGraph().setClearColor(Qt.GlobalColor.black)

        # Create storage for point entities
        self.sphere_entities = []
        self.sphere_transforms = []

        # Create storage for bone entities
        self.bone_transforms = []
        self.bone_meshes = []

        # Set display scale values
        self.point_scale = 100 * 0.25
        self.sphere_radius = 0.3 * 0.40
        self.bone_radius = 0.1 * 0.25

        # Set up the 3D scene
        self.setup_camera()
        self.setup_orbit_controller()
        self.setup_point_spheres(21)
        self.setup_bones()

        self.mainWidget = self.container

        self.makeBasicWidget()

    # ---------------------------------------------------------#
    # Setup of the widget's basics
    # ---------------------------------------------------------#

    def setup_camera(self):
        """
        Set up the 3D camera.
        """
        # Get the 3D view camera
        self.camera = self.view.camera()

        # Set the camera projection
        self.camera.lens().setPerspectiveProjection(
            45.0,
            16 / 9,
            0.1,
            1000.0
        )

        # Set the camera position and direction
        self.camera.setPosition(QVector3D(0, 3, 8))
        self.camera.setViewCenter(QVector3D(0, 0, 0))
        self.camera.setUpVector(QVector3D(0, 1, 0))

    def setup_orbit_controller(self):
        """
        Set up the orbit camera controller.
        """
        # Create the orbit controller
        self.controller = QOrbitCameraController(self.root)
        self.controller.setCamera(self.camera)

        # Set controller speed
        self.controller.setLinearSpeed(20.0)
        self.controller.setLookSpeed(90.0)

    def setup_point_spheres(self, count: int):
        """
        Create the 3D spheres used to show hand points.\n
        :param `int` count: Number of spheres to create.
        """
        # Create every point sphere
        for i in range(count):
            entity = QEntity(self.root)
            material = QPhongMaterial(self.root)

            # Set point color by finger section
            if 1 < i < 5:
                material.setDiffuse(Qt.GlobalColor.cyan)
            elif 5 < i < 9:
                material.setDiffuse(Qt.GlobalColor.magenta)
            elif 9 < i < 13:
                material.setDiffuse(Qt.GlobalColor.blue)
            elif 13 < i < 17:
                material.setDiffuse(Qt.GlobalColor.green)
            elif 17 < i < 21:
                material.setDiffuse(Qt.GlobalColor.red)
            elif i == 0 or i == 1 or i == 5 or i == 8 or i == 12 or i == 16:
                material.setDiffuse(Qt.GlobalColor.gray)

            # Create the sphere mesh
            mesh = QSphereMesh()
            mesh.setRadius(self.sphere_radius)

            # Hide the point until data is received
            transform = QTransform()
            transform.setTranslation(QVector3D(9999, 9999, 9999))

            # Add sphere components
            entity.addComponent(mesh)
            entity.addComponent(transform)
            entity.addComponent(material)

            # Save the transform to update it later
            self.sphere_transforms.append(transform)

    def setup_bones(self):
        """
        Create the 3D cylinders used to connect hand points.
        """
        # Create every hand connection cylinder
        for _a, _b, _c in self.HAND_CONNECTIONS:
            entity = QEntity(self.root)
            material = QPhongMaterial(self.root)
            mesh = QCylinderMesh()
            mesh.setRadius(self.bone_radius)
            mesh.setLength(1.0)

            # Set bone color by connection group
            if _c == 1:
                material.setDiffuse(Qt.GlobalColor.cyan)
            elif _c == 2:
                material.setDiffuse(Qt.GlobalColor.magenta)
            elif _c == 3:
                material.setDiffuse(Qt.GlobalColor.blue)
            elif _c == 4:
                material.setDiffuse(Qt.GlobalColor.green)
            elif _c == 5:
                material.setDiffuse(Qt.GlobalColor.red)
            elif _c == 6:
                material.setDiffuse(Qt.GlobalColor.gray)

            # Hide the bone until data is received
            transform = QTransform()
            transform.setTranslation(QVector3D(9999, 9999, 9999))

            # Add bone components
            entity.addComponent(mesh)
            entity.addComponent(transform)
            entity.addComponent(material)

            # Save components to update them later
            self.bone_meshes.append(mesh)
            self.bone_transforms.append(transform)

    def connectAll(self):
        """
        Connect the key frame worker signals.
        """
        self.worker.pointsReady.connect(self.updatePoints)

    # ---------------------------------------------------------#
    # Updates from the worker
    # ---------------------------------------------------------#

    @pyqtSlot(object)
    def updatePoints(self, points):
        """
        Update the 3D hand points and bones.\n
        :param points: Array of 3D hand points.
        """
        # Guard clause for empty data
        if points is None:
            return

        # Guard clause for incomplete hand data
        if len(points) < 21:
            return

        vec_points = []

        # Update every point sphere
        for i in range(21):
            x, y, z = points[i] - points[0]

            p = QVector3D(
                float(x) * self.point_scale,
                -(float(y) * self.point_scale),
                -(float(z) * self.point_scale)
            )

            vec_points.append(p)
            self.sphere_transforms[i].setTranslation(p)

        # Update every bone
        for bone_index, (a_idx, b_idx, c) in enumerate(self.HAND_CONNECTIONS):
            self.updateBone(bone_index, vec_points[a_idx], vec_points[b_idx])

    def updateBone(self, bone_index: int, a: QVector3D, b: QVector3D):
        """
        Update one hand bone cylinder.\n
        :param `int` bone_index: Index of the bone to update.
        :param `QVector3D` a: First point of the bone.
        :param `QVector3D` b: Second point of the bone.
        """
        # Get direction and length between both points
        direction = b - a
        length = direction.length()

        # Guard clause for points that are too close
        if length <= 1e-6:
            self.bone_meshes[bone_index].setLength(0.001)
            self.bone_transforms[bone_index].setTranslation(a)
            return

        # Get the midpoint between the points
        midpoint = QVector3D(
            (a.x() + b.x()) / 2.0,
            (a.y() + b.y()) / 2.0,
            (a.z() + b.z()) / 2.0,
        )

        # Rotate the cylinder to align with the direction
        up = QVector3D(0.0, 1.0, 0.0)
        direction_normalized = direction.normalized()
        rotation = QQuaternion.rotationTo(up, direction_normalized)

        # Update bone mesh and transform
        self.bone_meshes[bone_index].setLength(length)
        self.bone_transforms[bone_index].setTranslation(midpoint)
        self.bone_transforms[bone_index].setRotation(rotation)

    def browseFile(self):
        """
        Open a file dialog and set the selected key frame file path.
        """
        # User chooses the key frame file
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select keyFrames file",
            "",
            "Array Files (*.npy *.csv *.mat);;All Files (*)"
        )

        # Set the path if a file was chosen
        if path:
            self.pathInput.setText(path)
