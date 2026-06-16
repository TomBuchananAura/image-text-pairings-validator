import warnings
# Suppress common runtime warnings related to memory pinning/accelerators
warnings.filterwarnings("ignore", message="pin_memory.*no accelerator is found")

import torch
from PIL import Image
import easyocr
import numpy as np
from typing import List


# Check and log PyTorch CUDA availability for environment diagnostics
try:
    import torch
    print(f"PyTorch CUDA available: {torch.cuda.is_available()}")
except ImportError:
    # Handle case where torch might not be installed
    pass


# Global variable to store the OCR reader instance, managing initialization state.
_ocr_reader = None

# Configuration flag: Should the system force CPU usage regardless of hardware?
# Set this to True to disable GPU acceleration intentionally.
OCR_FORCE_CPU = False


def _get_reader() -> easyocr.Reader:
    """
    Initializes and retrieves the singleton instance of the OCR reader.
    Determines whether to use GPU or CPU based on configuration flags.
    """
    global _ocr_reader
    if _ocr_reader is None:
        gpu_available = torch.cuda.is_available()
        # Use GPU only if explicitly allowed AND CUDA is available
        use_gpu = not OCR_FORCE_CPU and gpu_available

        print(f"Initializing OCR reader using GPU acceleration: {use_gpu}")

        # Initialize the easyocr Reader for English language, suppressing detailed logging.
        # type: ignore[arg-type] # Necessary due to internal typing complexities of quickstart libraries
        _ocr_reader = easyocr.Reader(['en'], gpu=use_gpu, verbose=False) 
    return _ocr_reader


def extract_text(image: Image.Image) -> str:
    """
    Performs Optical Character Recognition (OCR) on a PIL image object.

    Args:
        image: The input image loaded via PIL (Pillow).

    Returns:
        A single string containing all extracted and concatenated text, or an empty string if none is found.
    """
    np_img = np.array(image)
    # Pass the NumPy array representation of the image to the OCR reader
    raw_results = _get_reader().readtext(np_img, detail=0)

    if not raw_results:
        return ""

    # Concatenate all extracted text lines into a single clean string
    text_list: List[str] = [str(line) for line in raw_results]
    return " ".join(text_list).strip()