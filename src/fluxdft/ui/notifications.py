"""
Notification System for FluxDFT.

Provides desktop notifications for job events.
"""

import logging
from typing import Optional
from enum import Enum

from PyQt6.QtWidgets import QSystemTrayIcon, QMenu, QApplication
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QObject, pyqtSignal

logger = logging.getLogger(__name__)

# Try to import plyer for cross-platform notifications
try:
    from plyer import notification as plyer_notify
    HAS_PLYER = True
except ImportError:
    HAS_PLYER = False

try:
    import qtawesome as qta
    HAS_ICONS = True
except ImportError:
    HAS_ICONS = False


class NotificationType(Enum):
    """Types of notifications."""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


class NotificationManager(QObject):
    """
    Manages desktop notifications for FluxDFT.
    
    Singleton pattern - use NotificationManager.instance() to get the manager.
    """
    
    _instance = None
    notification_clicked = pyqtSignal(str)  # Emits notification ID
    
    @classmethod
    def instance(cls) -> "NotificationManager":
        """Get or create the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.enabled = True
        self._tray_icon: Optional[QSystemTrayIcon] = None
        self._setup_tray()
    
    def _setup_tray(self):
        """Setup system tray icon for notifications."""
        app = QApplication.instance()
        if not app:
            return
        
        self._tray_icon = QSystemTrayIcon(app)
        
        # Set icon
        if HAS_ICONS:
            try:
                icon = qta.icon('fa5s.atom', color='#3b82f6')
                self._tray_icon.setIcon(icon)
            except:
                pass
        
        # Create context menu
        menu = QMenu()
        menu.addAction("Show FluxDFT", self._on_show)
        menu.addSeparator()
        menu.addAction("Disable Notifications", self._toggle_notifications)
        self._tray_icon.setContextMenu(menu)
        
        # Connect click
        self._tray_icon.activated.connect(self._on_tray_activated)
        
        self._tray_icon.show()
    
    def _on_show(self):
        """Show main window."""
        app = QApplication.instance()
        if app:
            for widget in app.topLevelWidgets():
                if widget.windowTitle().startswith("FluxDFT"):
                    widget.show()
                    widget.raise_()
                    widget.activateWindow()
                    break
    
    def _toggle_notifications(self):
        """Toggle notifications on/off."""
        self.enabled = not self.enabled
        logger.info(f"Notifications {'enabled' if self.enabled else 'disabled'}")
    
    def _on_tray_activated(self, reason):
        """Handle tray icon click."""
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._on_show()
    
    def notify(
        self,
        title: str,
        message: str,
        notification_type: NotificationType = NotificationType.INFO,
        notification_id: str = "",
        timeout: int = 5000  # milliseconds
    ):
        """
        Send a desktop notification.
        
        Args:
            title: Notification title
            message: Notification body
            notification_type: Type (affects icon)
            notification_id: Optional ID for tracking
            timeout: Display time in ms (default 5 seconds)
        """
        if not self.enabled:
            return
        
        # Try Qt system tray notification first
        if self._tray_icon and self._tray_icon.isSystemTrayAvailable():
            icon_type = {
                NotificationType.INFO: QSystemTrayIcon.MessageIcon.Information,
                NotificationType.SUCCESS: QSystemTrayIcon.MessageIcon.Information,
                NotificationType.WARNING: QSystemTrayIcon.MessageIcon.Warning,
                NotificationType.ERROR: QSystemTrayIcon.MessageIcon.Critical,
            }.get(notification_type, QSystemTrayIcon.MessageIcon.Information)
            
            self._tray_icon.showMessage(title, message, icon_type, timeout)
            return
        
        # Fallback to plyer if available
        if HAS_PLYER:
            try:
                plyer_notify.notify(
                    title=title,
                    message=message,
                    app_name="FluxDFT",
                    timeout=timeout // 1000  # plyer uses seconds
                )
                return
            except Exception as e:
                logger.warning(f"Plyer notification failed: {e}")
        
        # Last resort: log it
        logger.info(f"[NOTIFICATION] {title}: {message}")
    
    def job_started(self, job_name: str):
        """Notify that a job has started."""
        self.notify(
            title="Job Started",
            message=f"{job_name} is now running",
            notification_type=NotificationType.INFO
        )
    
    def job_completed(self, job_name: str, duration: Optional[float] = None):
        """Notify that a job has completed successfully."""
        msg = f"{job_name} completed successfully"
        if duration:
            mins = int(duration // 60)
            secs = int(duration % 60)
            msg += f" ({mins}m {secs}s)"
        
        self.notify(
            title="Job Completed ✓",
            message=msg,
            notification_type=NotificationType.SUCCESS
        )
    
    def job_failed(self, job_name: str, error: str = ""):
        """Notify that a job has failed."""
        msg = f"{job_name} failed"
        if error:
            msg += f": {error[:100]}"
        
        self.notify(
            title="Job Failed ✗",
            message=msg,
            notification_type=NotificationType.ERROR
        )
    
    def convergence_warning(self, job_name: str, iteration: int):
        """Notify about possible convergence issues."""
        self.notify(
            title="Convergence Warning",
            message=f"{job_name}: Still running at iteration {iteration}",
            notification_type=NotificationType.WARNING
        )
