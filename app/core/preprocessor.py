from PIL import Image, ImageEnhance


def preprocess_image(image: Image.Image) -> Image.Image:
    """
    Performs a standardized sequence of image enhancements necessary for high-quality OCR input.

    The process involves three steps:
    1. Conversion to grayscale ('L' mode).
    2. Contrast enhancement (amplified by 1.5x).
    3. Resizing and resampling to a uniform dimension (2000x2000) using BICUBIC interpolation.

    Args:
        image: The input PIL Image object.

    Returns:
        The processed, standardized PIL Image object.
    """
    # Convert the image to grayscale mode ('L')
    gray = image.convert("L")
    
    # Enhance contrast using a factor of 1.5
    enhanced = ImageEnhance.Contrast(gray).enhance(1.5)
    
    # Resize the image to a fixed dimension (2000x2000) using high-quality cubic resampling
    return enhanced.resize((2000, 2000), Image.Resampling.BICUBIC)
