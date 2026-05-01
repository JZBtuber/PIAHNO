from src.gui.Core import basicWindowWidget, basicWorker

from PyQt6.Qt3DExtras import Qt3DWindow, QOrbitCameraController, QSphereMesh, QPhongMaterial, QCylinderMesh
from PyQt6.QtGui import QVector3D, QQuaternion
from PyQt6.QtWidgets import QWidget, QFileDialog
from PyQt6.Qt3DCore import QEntity, QTransform
from PyQt6.QtCore import Qt, QThread, pyqtSignal, pyqtSlot

import numpy as np
import scipy.io

class KeyWorker(basicWorker):
    pointsReady = pyqtSignal(object)

    def __init__(self, path, isLive):
        super().__init__(path, isLive)

        self.rows = None
        self.frames = []
        self.frame_index = 0


    #---------------------------------------------------------#
    # Workers's life time
    #---------------------------------------------------------#
    def beforeLoop(self):
        
        if self.path[-4:] == ".npy":
            self.rows = np.load(self.path, allow_pickle=True)
        elif self.path[-4:] == ".csv":
            self.rows = np.loadtxt(self.path, delimiter=',')
        elif self.path[-4:] == ".mat":
            mat = scipy.io.loadmat(self.path)
            self.rows= mat["array"]

        if self.rows.ndim != 2 or self.rows.shape[1] < 6:
            raise ValueError("KeyFrame file has incorrect format.")

        # Format:
        # col 0 = frame index
        # col 1 = timestamp in ms
        # col 2 = point id
        # col 3 = x
        # col 4 = y
        # col 5 = z

        frame_ids = np.unique(self.rows[:, 0]).astype(int)

        self.frames = []

        for frame_id in frame_ids:
            frame_rows = self.rows[self.rows[:, 0] == frame_id]

            if len(frame_rows) == 0:
                continue

            timestamp_ms = int(frame_rows[0, 1])

            # Sort by point id so point 0 always updates sphere 0, etc.
            frame_rows = frame_rows[np.argsort(frame_rows[:, 2])]

            points = frame_rows[:, 3:6].astype(float)

            self.frames.append((timestamp_ms, points))

        self.frame_index = 0


    def loop(self):
        if self.frame_index >= len(self.frames):
            self.running = False
            return

        now_ms = self.getMasterTimeMs()

        while self.frame_index < len(self.frames):
            timestamp_ms, points = self.frames[self.frame_index]

            if timestamp_ms > now_ms:
                break

            self.pointsReady.emit(points)
            self.frame_index += 1

        QThread.msleep(1)

    def afterLoop(self):
        self.rows = None
        self.frames = []


class KeyFeed(basicWindowWidget):
    def __init__(self, ID: int, workingDir: str):
        super().__init__(KeyWorker, ID, workingDir=workingDir)

        self.inputType = "keyFrame"
        self.isLiveFeed = False

        self.HAND_CONNECTIONS = [
            (0, 1), (1, 2), (2, 3), (3, 4),         # thumb
            (0, 5), (5, 6), (6, 7), (7, 8),         # index
            (5, 9), (9, 10), (10, 11), (11, 12),    # middle
            (9, 13), (13, 14), (14, 15), (15, 16),  # ring
            (13, 17), (17, 18), (18, 19), (19, 20), # pinky
            (0, 17),                                 # palm edge
        ]

        self.view = Qt3DWindow()
        self.container = QWidget.createWindowContainer(self.view)

        self.root = QEntity()
        self.view.setRootEntity(self.root)

        self.view.defaultFrameGraph().setClearColor(Qt.GlobalColor.black)

        self.sphere_entities = []
        self.sphere_transforms = []

        self.bone_transforms = []
        self.bone_meshes = []

        self.point_scale = 100 * 0.25
        self.sphere_radius = 0.3 * 0.25
        self.bone_radius = 0.1 * 0.25

        self.setup_camera()
        self.setup_orbit_controller()
        self.setup_point_spheres(21)
        self.setup_bones()

        self.mainWidget = self.container

        

        self.makeBasicWidget()


    #---------------------------------------------------------#
    # Setup of the widget's basics
    #---------------------------------------------------------#
    def setup_camera(self):
        self.camera = self.view.camera()

        self.camera.lens().setPerspectiveProjection(
            45.0,
            16 / 9,
            0.1,
            1000.0
        )

        self.camera.setPosition(QVector3D(0, 3, 8))
        self.camera.setViewCenter(QVector3D(0, 0, 0))
        self.camera.setUpVector(QVector3D(0, 1, 0))

    def setup_orbit_controller(self):
        self.controller = QOrbitCameraController(self.root)
        self.controller.setCamera(self.camera)

        self.controller.setLinearSpeed(20.0)
        self.controller.setLookSpeed(90.0)

    def setup_point_spheres(self, count: int):
        material = QPhongMaterial(self.root)
        material.setDiffuse(Qt.GlobalColor.green)

        for _ in range(count):
            entity = QEntity(self.root)

            mesh = QSphereMesh()
            mesh.setRadius(self.sphere_radius)

            transform = QTransform()
            transform.setTranslation(QVector3D(9999, 9999, 9999))

            entity.addComponent(mesh)
            entity.addComponent(transform)
            entity.addComponent(material)

            self.sphere_transforms.append(transform)


    def setup_bones(self):
        material = QPhongMaterial(self.root)
        material.setDiffuse(Qt.GlobalColor.green)

        for _a, _b in self.HAND_CONNECTIONS:
            entity = QEntity(self.root)

            mesh = QCylinderMesh()
            mesh.setRadius(self.bone_radius)
            mesh.setLength(1.0)

            transform = QTransform()
            transform.setTranslation(QVector3D(9999, 9999, 9999))

            entity.addComponent(mesh)
            entity.addComponent(transform)
            entity.addComponent(material)

            self.bone_meshes.append(mesh)
            self.bone_transforms.append(transform)


    def connectAll(self):
        self.worker.pointsReady.connect(self.updatePoints)
    
    
    #---------------------------------------------------------#
    # Updates from the worker
    #---------------------------------------------------------#
    @pyqtSlot(object)
    def updatePoints(self, points):
        if points is None:
            return

        if len(points) < 21:
            return

        vec_points = []

        for i in range(21):
            x, y, z = points[i]

            p = QVector3D(
                float(x) * self.point_scale,
                -(float(y) * self.point_scale) -3,
                -(float(z) * self.point_scale)
            )

            vec_points.append(p)
            self.sphere_transforms[i].setTranslation(p)

        for bone_index, (a_idx, b_idx) in enumerate(self.HAND_CONNECTIONS):
            self.updateBone(bone_index, vec_points[a_idx], vec_points[b_idx])
        

    def updateBone(self, bone_index: int, a: QVector3D, b: QVector3D):
        direction = b - a
        length = direction.length()

        if length <= 1e-6:
            self.bone_meshes[bone_index].setLength(0.001)
            self.bone_transforms[bone_index].setTranslation(a)
            return

        midpoint = QVector3D(
            (a.x() + b.x()) / 2.0,
            (a.y() + b.y()) / 2.0,
            (a.z() + b.z()) / 2.0,
        )

        up = QVector3D(0.0, 1.0, 0.0)
        direction_normalized = direction.normalized()
        rotation = QQuaternion.rotationTo(up, direction_normalized)

        self.bone_meshes[bone_index].setLength(length)
        self.bone_transforms[bone_index].setTranslation(midpoint)
        self.bone_transforms[bone_index].setRotation(rotation)


    def browseFile(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select keyFrames file",
            "",
            "Array Files (*.npy *.csv *.mat);;All Files (*)"
        )

        if path:
            self.pathInput.setText(path)