"""Native progress painting without allocating a widget for every queue row."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionProgressBar,
    QStyleOptionViewItem,
)


class ProgressDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        style = option.widget.style() if option.widget else QApplication.style()
        background = QStyleOptionViewItem(option)
        self.initStyleOption(background, index)
        background.text = ""
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, background, painter, option.widget)
        bar = QStyleOptionProgressBar()
        bar.rect = option.rect.adjusted(3, 3, -3, -3)
        bar.state = option.state | QStyle.StateFlag.State_Horizontal
        bar.palette = option.palette
        bar.minimum = 0
        bar.maximum = 100
        bar.progress = max(0, min(100, int(index.data(Qt.ItemDataRole.UserRole) or 0)))
        bar.text = index.data(Qt.ItemDataRole.DisplayRole) or "0%"
        bar.textVisible = True
        bar.textAlignment = Qt.AlignmentFlag.AlignCenter
        style.drawControl(QStyle.ControlElement.CE_ProgressBar, bar, painter, option.widget)
