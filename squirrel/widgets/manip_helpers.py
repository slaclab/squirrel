"""
Widget manipulation helper functions
"""

from typing import Optional

from qtpy import QtCore, QtGui, QtWidgets


class FrameOnEditFilter(QtCore.QObject):
    """
    A QLineEdit event filter for editing vs not editing style handling.

    This will make the QLineEdit look like a QLabel when the user is
    not editing it.
    """
    def eventFilter(self, object: QtWidgets.QLineEdit, event: QtCore.QEvent) -> bool:
        # Even if we install only on line edits, this can be passed a generic
        # QWidget when we remove and clean up the line edit widget.
        if not isinstance(object, QtWidgets.QLineEdit):
            return False
        if event.type() == QtCore.QEvent.FocusIn:
            self.set_edit_style(object)
            return True
        if event.type() == QtCore.QEvent.FocusOut:
            self.set_no_edit_style(object)
            return True
        return False

    @staticmethod
    def set_edit_style(object: QtWidgets.QLineEdit):
        """
        Set a QLineEdit to the look and feel we want for editing.

        Parameters
        ----------
        object : QLineEdit
            Any line edit widget.
        """
        object.setFrame(True)
        color = object.palette().color(QtGui.QPalette.ColorRole.Base)
        object.setStyleSheet(
            f"QLineEdit {{ background: rgba({color.red()},"
            f"{color.green()}, {color.blue()}, {color.alpha()})}}"
        )
        object.setReadOnly(False)

    @staticmethod
    def set_no_edit_style(object: QtWidgets.QLineEdit):
        """
        Set a QLineEdit to the look and feel we want for not editing.

        Parameters
        ----------
        object : QLineEdit
            Any line edit widget.
        """
        if object.text():
            object.setFrame(False)
            object.setStyleSheet(
                "QLineEdit { background: transparent }"
            )
        object.setReadOnly(True)


def match_line_edit_text_width(
    line_edit: QtWidgets.QLineEdit,
    text: Optional[str] = None,
    minimum: int = 40,
    buffer: int = 10,
) -> None:
    """
    Set the width of a line edit to match the text length.

    You can use this in a slot and connect it to the line edit's
    "textChanged" signal. This creates an effect where the line
    edit will get longer when the user types text into it and
    shorter when the user deletes text from it.

    Parameters
    ----------
    line_edit : QLineEdit
        The line edit whose width you'd like to adjust.
    text : str, optional
        The text to use as the basis for our size metrics.
        In a slot you could pass in the text we get from the
        signal update. If omitted, we'll use the current text
        in the widget.
    minimum : int, optional
        The minimum width of the line edit, even when we have no
        text. If omitted, we'll use a default value.
    buffer : int, optional
        The buffer we have on the right side of the rightmost
        character in the line_edit before the edge of the widget.
        If omitted, we'll use a default value.
    """
    font_metrics = line_edit.fontMetrics()
    if text is None:
        text = line_edit.text()
    width = font_metrics.boundingRect(text).width()
    line_edit.setFixedWidth(max(width + buffer, minimum))


def insert_widget(widget: QtWidgets.QWidget, placeholder: QtWidgets.QWidget) -> None:
    """
    Helper function for slotting e.g. data widgets into placeholders.
    """
    if placeholder.layout() is None:
        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        placeholder.setLayout(layout)
    else:
        old_widget = placeholder.layout().takeAt(0).widget()
        if old_widget is not None:
            # old_widget.setParent(None)
            old_widget.deleteLater()
    placeholder.layout().addWidget(widget)
