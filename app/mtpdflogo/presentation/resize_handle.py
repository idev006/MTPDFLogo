"""Mouse resize affordance; commit the existing overlay size, never a second model."""

from math import hypot

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QBrush, QPen
from PySide6.QtWidgets import QApplication, QGraphicsItem, QGraphicsRectItem


class OverlayResizeHandle(QGraphicsRectItem):
    def __init__(self, graphic, overlay_id, owner):
        super().__init__(-6, -6, 12, 12, graphic)
        self.graphic = graphic
        self.overlay_id = overlay_id
        self.owner = owner
        self.factor = 1.0
        self.setPos(graphic.boundingRect().bottomRight())
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresParentOpacity)
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        self.setToolTip("ลากมุมนี้เพื่อปรับขนาด Text/Logo (รักษาสัดส่วน)")
        self.setBrush(QBrush(QApplication.palette().highlight()))
        self.setPen(QPen(QApplication.palette().highlightedText(), 1))
        self.setZValue(1000)

    def mousePressEvent(self, event):
        self.center = self.graphic.mapToScene(self.graphic.boundingRect().center())
        offset = event.scenePos() - self.center
        self.distance = max(1.0, hypot(offset.x(), offset.y()))
        self.factor = 1.0
        # Keep the original center fixed while scaling, including rotated items.
        event.accept()

    def mouseMoveEvent(self, event):
        offset = event.scenePos() - self.center
        factor = hypot(offset.x(), offset.y()) / self.distance
        self.factor = self.owner._bounded_resize_factor(self.overlay_id, factor)
        self.graphic.setScale(self.factor)
        current = self.graphic.mapToScene(self.graphic.boundingRect().center())
        self.graphic.setPos(self.graphic.pos() + self.center - current)
        event.accept()

    def mouseReleaseEvent(self, event):
        overlay_id, factor = self.overlay_id, self.factor
        # Commit after dispatch: refreshing the scene deletes this handle.
        QTimer.singleShot(0, lambda: self.owner._commit_overlay_resize(overlay_id, factor))
        event.accept()
