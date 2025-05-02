from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QCheckBox, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QSizePolicy, QVBoxLayout,
    QWidget)

class Ui_LoginWindow(object):
    def setupUi(self, LoginWindow):
        if not LoginWindow.objectName():
            LoginWindow.setObjectName(u"LoginWindow")
        LoginWindow.resize(600, 400)
        self.centralwidget = QWidget(LoginWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.verticalLayout = QVBoxLayout(self.centralwidget)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(50, 50, 50, 50)
        self.verticalLayout.setSpacing(20)

        self.title_label = QLabel(self.centralwidget)
        self.title_label.setObjectName(u"title_label")
        self.title_label.setStyleSheet(u"font-size: 24pt; font-weight: bold;")
        self.verticalLayout.addWidget(self.title_label)

        self.username_input = QLineEdit(self.centralwidget)
        self.username_input.setObjectName(u"username_input")
        self.username_input.setPlaceholderText("Benutzername")
        self.username_input.setFixedHeight(40)
        self.verticalLayout.addWidget(self.username_input)

        self.password_input = QLineEdit(self.centralwidget)
        self.password_input.setObjectName(u"password_input")
        self.password_input.setPlaceholderText("Passwort")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setFixedHeight(40)
        self.verticalLayout.addWidget(self.password_input)

        self.login_button = QPushButton(self.centralwidget)
        self.login_button.setObjectName(u"login_button")
        self.login_button.setFixedHeight(40)
        self.verticalLayout.addWidget(self.login_button)

        self.remember_cb = QCheckBox(self.centralwidget)
        self.remember_cb.setObjectName(u"remember_cb")
        self.verticalLayout.addWidget(self.remember_cb)

        self.register_button = QPushButton(self.centralwidget)
        self.register_button.setObjectName(u"register_button")
        self.register_button.setFixedHeight(40)
        self.verticalLayout.addWidget(self.register_button)

        LoginWindow.setCentralWidget(self.centralwidget)

        self.retranslateUi(LoginWindow)

        QMetaObject.connectSlotsByName(LoginWindow)

    def retranslateUi(self, LoginWindow):
        LoginWindow.setWindowTitle(QCoreApplication.translate("LoginWindow", u"Login", None))
        self.title_label.setText(QCoreApplication.translate("LoginWindow", u"Willkommen zur FinanzApp", None))
        self.login_button.setText(QCoreApplication.translate("LoginWindow", u"Login", None))
        self.remember_cb.setText(QCoreApplication.translate("LoginWindow", u"Daten merken", None))
        self.register_button.setText(QCoreApplication.translate("LoginWindow", u"Registrieren", None))
