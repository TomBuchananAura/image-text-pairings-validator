import os
from PIL import Image, ImageEnhance
# Attempt to import torch; if not available, handle the error gracefully
try:
    import torch
except ImportError:
    print("WARNING: PyTorch (torch) not found. CUDA detection will be disabled.")
    torch = None

from typing import Tuple

Resolution = Tuple[int, int]

def determine_target_resolution() -> Resolution:
    """
    Determines the optimal resizing resolution based on environment variables 
    and detected hardware resources (GPU/CPU).
    """
    
    # --- PRIORITY 1: Server Deployment Environment Variable ---
    # We assume if this variable is set, we are in a controlled deployment context.
    if os.getenv('DEPLOYMENT_ENV') == 'server':
        print("--- Context: Detected Server Deployment Mode (High Priority) ---")
        env_resolution = os.getenv('RESCALING_RESOLUTION')

        if env_resolution:
            try:
                width_str, height_str = env_resolution.split('x')
                return (int(width_str), int(height_str))
            except ValueError:
                print("WARNING: Invalid RESCALING_RESOLUTION format in server mode. Falling back to default.")
        
        # If deployed but no specific resolution variable is provided, 
        # we must fall back to a safe default (e.g., the old standard).
        return (480, 480)


    # --- PRIORITY 2: Local Machine Resource Detection ---
    print("--- Context: Detected Local Development Mode ---")

    if torch is None:
        print("ERROR: PyTorch not found. Cannot perform hardware check. Defaulting to safe fallback (480x480).")
        return (480, 480)


    # Check for CUDA/GPU availability
    cuda_available = torch.cuda.is_available()

    if cuda_available:
        print("INFO: PyTorch detected CUDA (GPU) available.")
        return (2000, 2000) # Target resolution for GPU local run
    else:
        # Local, but no GPU/CUDA found
        print("INFO: PyTorch running on CPU only.")
        return (480, 480) # Target resolution for CPU local run


def preprocess_image(image: Image.Image) -> Image.Image:
    """
    Performs standardized image enhancements using dynamically determined target size.
    """
    
    # Determine the required target size first
    target_size = determine_target_resolution()

    print("-" * 50)
    print(f"Processing image... Target Resolution Set To: {target_size}")
    
    # Core processing logic remains the same
    
    # 1. Convert to grayscale mode ('L')
    gray = image.convert("L")
    
    # 2. Enhance contrast using a factor of 1.5
    enhanced = ImageEnhance.Contrast(gray).enhance(1.5)
    
    # 3. Resize using the determined target_size
    return enhanced.resize(target_size, Image.Resampling.BICUBIC)