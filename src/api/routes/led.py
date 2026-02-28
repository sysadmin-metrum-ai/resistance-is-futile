"""LED API endpoints.

Provides REST API for LED control on drones: set color, blink, and off.
"""

from fastapi import APIRouter, HTTPException, Depends, Header, status
from pydantic import BaseModel, Field

from src.core.config import Settings, get_settings
from src.services.led_controller import LEDController, LEDColor
from src.services.drone_manager import DroneManager


router = APIRouter()


# Pydantic models
class LEDSetRequest(BaseModel):
    """Request body for setting LED color."""

    color: str = Field(..., description="LED color: green, yellow, red")


class LEDBlinkRequest(BaseModel):
    """Request body for blinking LED."""

    color: str = Field(..., description="LED color: green, yellow, red")
    duration: float = Field(default=3.0, description="Blink duration in seconds")


class LEDResponse(BaseModel):
    """LED control response."""

    success: bool
    drone_id: int
    action: str
    message: str


# Dependencies
async def get_led_controller() -> LEDController:
    """Get LED controller instance."""
    return LEDController()


async def get_drone_manager() -> DroneManager:
    """Get drone manager instance."""
    return DroneManager()


def verify_api_key(x_api_key: str = Header(None, alias="X-API-Key")):
    """Verify API key from header."""
    settings = get_settings()
    if settings.api_key and x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key"
        )


# API endpoints
@router.post("/{drone_id}/set", response_model=LEDResponse)
async def set_led_color(
    drone_id: int,
    req: LEDSetRequest,
    led_controller: LEDController = Depends(get_led_controller),
    drone_manager: DroneManager = Depends(get_drone_manager),
    x_api_key: str = Header(None, alias="X-API-Key"),
):
    """
    Set LED to a solid color.

    Args:
        drone_id: Drone ID
        req: Request with color
    """
    verify_api_key(x_api_key)

    # Validate color
    try:
        color = LEDColor(req.color.lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid color: {req.color}. Must be green, yellow, or red."
        )

    # Get drone URI from PostgREST
    try:
        drone = await drone_manager.get_drone(drone_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Drone {drone_id} not found"
        )

    drone_uri = drone.get("uri")
    if not drone_uri:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Drone {drone_id} has no URI configured"
        )

    success = await led_controller.set_color(drone_uri, color)

    return LEDResponse(
        success=success,
        drone_id=drone_id,
        action="set_color",
        message=f"LED set to {color.value}" if success else "Failed to set LED"
    )


@router.post("/{drone_id}/blink", response_model=LEDResponse)
async def blink_led(
    drone_id: int,
    req: LEDBlinkRequest,
    led_controller: LEDController = Depends(get_led_controller),
    drone_manager: DroneManager = Depends(get_drone_manager),
    x_api_key: str = Header(None, alias="X-API-Key"),
):
    """
    Blink LED with a color for specified duration.

    Args:
        drone_id: Drone ID
        req: Request with color and duration
    """
    verify_api_key(x_api_key)

    # Validate color
    try:
        color = LEDColor(req.color.lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid color: {req.color}. Must be green, yellow, or red."
        )

    # Clamp duration
    duration = max(0.5, min(req.duration, 30.0))

    # Get drone URI from PostgREST
    try:
        drone = await drone_manager.get_drone(drone_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Drone {drone_id} not found"
        )

    drone_uri = drone.get("uri")
    if not drone_uri:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Drone {drone_id} has no URI configured"
        )

    success = await led_controller.blink(drone_uri, color, duration)

    return LEDResponse(
        success=success,
        drone_id=drone_id,
        action="blink",
        message=f"LED blinking {color.value} for {duration}s" if success else "Failed to blink LED"
    )


@router.post("/{drone_id}/off", response_model=LEDResponse)
async def turn_off_led(
    drone_id: int,
    led_controller: LEDController = Depends(get_led_controller),
    drone_manager: DroneManager = Depends(get_drone_manager),
    x_api_key: str = Header(None, alias="X-API-Key"),
):
    """
    Turn off LED.

    Args:
        drone_id: Drone ID
    """
    verify_api_key(x_api_key)

    # Get drone URI from PostgREST
    try:
        drone = await drone_manager.get_drone(drone_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Drone {drone_id} not found"
        )

    drone_uri = drone.get("uri")
    if not drone_uri:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Drone {drone_id} has no URI configured"
        )

    success = await led_controller.off(drone_uri)

    return LEDResponse(
        success=success,
        drone_id=drone_id,
        action="off",
        message="LED turned off" if success else "Failed to turn off LED"
    )
