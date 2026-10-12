"""WiFi Fall Guard: camera-free fall detection from WiFi CSI (ESP32-S3)."""

__version__ = "0.1.0"

# Activity classes used across the whole project. The order defines the
# integer label used by datasets and models, so only append to this list.
CLASSES = ["empty", "still", "walk", "sit", "lie", "fall"]
CLASS_TO_ID = {name: i for i, name in enumerate(CLASSES)}
FALL_ID = CLASS_TO_ID["fall"]
