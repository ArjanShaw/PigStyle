from PIL import Image
import io

class ImageFormatter:
    """
    Handles resizing and compressing images for eBay upload
    to reduce memory usage while keeping quality usable.
    """
    def __init__(self, max_width=800, max_height=800, quality=85):
        self.max_width = max_width
        self.max_height = max_height
        self.quality = quality

    def format_image(self, image_path, save_path=None):
        """
        Resizes and compresses the image at image_path.
        If save_path is provided, saves the formatted image to that path.
        Returns a BytesIO buffer if save_path is None.
        """
        img = Image.open(image_path)
        img = img.convert("RGB")  # Ensure consistent format

        # Resize maintaining aspect ratio
        img.thumbnail((self.max_width, self.max_height))

        # Save to a BytesIO buffer to control compression
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=self.quality, optimize=True)
        buffer.seek(0)

        if save_path:
            with open(save_path, "wb") as f:
                f.write(buffer.read())
            return save_path
        else:
            return buffer
