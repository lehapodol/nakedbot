import aiohttp
import asyncio
import logging
import io
from typing import Optional, Tuple
from PIL import Image, ImageFilter
from config import (
    UNDRESS_API_KEY, UNDRESS_API_URL, UNDRESS_CHECK_URL,
    UNDRESS_PROMPT, UNDRESS_AI_MODEL, UNDRESS_NUM_IMAGES
)

logger = logging.getLogger(__name__)


async def blur_image_from_url(image_url: str, blur_radius: int = 10) -> Optional[io.BytesIO]:
    """
    Download image from URL and apply blur effect
    
    Args:
        image_url: URL of the image to blur
        blur_radius: Blur intensity (default 30)
    
    Returns:
        BytesIO object with blurred image or None on error
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status != 200:
                    return None
                
                image_data = await response.read()
        
        # Open image with Pillow
        image = Image.open(io.BytesIO(image_data))
        
        # Apply gaussian blur
        blurred = image.filter(ImageFilter.GaussianBlur(radius=blur_radius))
        
        # Save to BytesIO
        output = io.BytesIO()
        blurred.save(output, format='JPEG', quality=85)
        output.seek(0)
        
        return output
    
    except Exception as e:
        logger.error(f"[BLUR] Error: {e}")
        return None


async def process_image(file_url: str, width: int = 512, height: int = 512) -> Tuple[bool, Optional[str]]:
    """
    Process image through UndressWith.AI API
    
    Args:
        file_url: URL of the image to process
        width: Image width (max 1024)
        height: Image height (max 1024)
    
    Returns:
        Tuple of (success: bool, result_url or error_message: str)
    """
    headers = {
        'Content-Type': 'application/json; charset=UTF-8',
        'Accept': 'application/json; charset=UTF-8',
        'X-Api-Key': UNDRESS_API_KEY
    }
    
    # Limit dimensions
    width = min(width, 1024)
    height = min(height, 1024)
    
    params = {
        "file_url": file_url,
        "prompt": UNDRESS_PROMPT,
        "num_images": UNDRESS_NUM_IMAGES,
        "ai_model_type": UNDRESS_AI_MODEL,
        "width": width,
        "height": height
    }
    
    try:
        logger.info(f"[UNDRESS] Starting process_image: url={file_url}, size={width}x{height}")
        logger.info(f"[UNDRESS] Params: {params}")
        
        async with aiohttp.ClientSession() as session:
            # Create task
            async with session.post(
                UNDRESS_API_URL, 
                json=params, 
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                response_text = await response.text()
                logger.info(f"[UNDRESS] Create task response ({response.status}): {response_text}")
                
                if response.status != 200:
                    return False, f"API error: {response.status}"
                
                data = await response.json()
                
                if data.get("code") != 1:
                    logger.error(f"[UNDRESS] API returned error: {data}")
                    return False, data.get("message", "Unknown error")
                
                uid = data.get("data", {}).get("uid")
                estimated_time = data.get("data", {}).get("estimated_time", 20)
                
                logger.info(f"[UNDRESS] Task created: uid={uid}, estimated_time={estimated_time}")
                
                if not uid:
                    return False, "No task ID returned"
            
            # Wait initial estimated time (but not more than 5 seconds for first check)
            await asyncio.sleep(min(estimated_time, 5))
            
            # Poll for result using check_item endpoint
            max_attempts = 30
            for attempt in range(max_attempts):
                logger.info(f"[UNDRESS] Checking status, attempt {attempt+1}/{max_attempts}")
                result = await check_item(session, headers, uid)
                
                if result[0] is True:
                    # Success - got result URL
                    logger.info(f"[UNDRESS] Success! Result: {result[1]}")
                    return result
                elif result[0] is False and result[1] != "processing":
                    # Error occurred
                    logger.error(f"[UNDRESS] Error: {result[1]}")
                    return result
                
                # Still processing (status=1), wait and retry
                await asyncio.sleep(2)
            
            logger.error("[UNDRESS] Timeout waiting for result")
            return False, "Timeout waiting for result"
    
    except asyncio.TimeoutError:
        logger.error("[UNDRESS] Request timeout")
        return False, "Request timeout"
    except aiohttp.ClientError as e:
        logger.error(f"[UNDRESS] Connection error: {e}")
        return False, f"Connection error: {str(e)}"
    except Exception as e:
        logger.error(f"[UNDRESS] Exception: {e}")
        return False, f"Error: {str(e)}"


async def check_item(
    session: aiohttp.ClientSession, 
    headers: dict, 
    uid: str
) -> Tuple[bool, str]:
    """
    Check processing status by task UID using POST request
    
    Status codes:
        1 - processing
        2 - completed
    
    Returns:
        Tuple of (success: bool, result_url or status: str)
    """
    try:
        params = {"uid": uid}
        
        async with session.post(
            UNDRESS_CHECK_URL,
            json=params,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=30)
        ) as response:
            response_text = await response.text()
            logger.info(f"[UNDRESS] Check status response ({response.status}): {response_text[:500]}")
            
            if response.status != 200:
                return False, f"API error: {response.status}"
            
            data = await response.json()
            
            if data.get("code") != 1:
                logger.error(f"[UNDRESS] Check returned error: {data}")
                return False, data.get("message", "Unknown error")
            
            result_data = data.get("data", {})
            status = result_data.get("status")
            
            logger.info(f"[UNDRESS] Status: {status}")
            
            # Status 2 = completed
            if status == 2:
                results = result_data.get("results", [])
                if results:
                    return True, results[0]  # Return first result image URL
                return False, "No images in result"
            
            # Status 1 = processing
            elif status == 1:
                return False, "processing"
            
            else:
                # Unknown status, treat as still processing
                return False, "processing"
    
    except Exception as e:
        logger.error(f"[UNDRESS] Check exception: {e}")
        return False, f"Error checking result: {str(e)}"


async def upload_to_telegraph(bot, file_id: str) -> Optional[str]:
    """
    Get file URL from Telegram
    
    Args:
        bot: Telegram Bot instance
        file_id: Telegram file ID
    
    Returns:
        File URL or None
    """
    try:
        file = await bot.get_file(file_id)
        file_url = f"https://api.telegram.org/file/bot{bot.token}/{file.file_path}"
        return file_url
    except Exception:
        return None
