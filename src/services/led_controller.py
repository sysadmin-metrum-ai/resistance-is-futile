"""LED controller service for drone state indication.

Provides LED control for Crazyflie drones: set color, blink, and off.
LED shows drone state: green (ready), yellow (busy), red (error).
"""

import asyncio
from enum import Enum
from typing import Optional
import logging

from src.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


class LEDColor(str, Enum):
    """LED colors for state indication."""
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


class LEDController:
    """Controls LED on Crazyflie drones for state indication.

    Maps drone states to LED colors:
    - idle -> green (ready)
    - busy -> yellow (processing mission)
    - offline -> blink green slowly
    - error -> red (error condition)
    """

    # LED blink rates in seconds
    BLINK_FAST = 0.2
    BLINK_SLOW = 1.0

    def __init__(self, settings: Optional[Settings] = None):
        """Initialize LED controller."""
        self.settings = settings or get_settings()
        self._drones = {}  # uri -> Crazyflie instance

    async def set_color(self, drone_uri: str, color: LEDColor) -> bool:
        """
        Set LED to a solid color.

        Args:
            drone_uri: Drone URI
            color: LED color (green, yellow, red)

        Returns:
            True if successful
        """
        logger.info(f"Setting LED color {color} for drone {drone_uri}")

        try:
            if drone_uri in self._drones:
                cf = self._drones[drone_uri]
                await self._set_led_color(cf, color)
            else:
                # No hardware connected - log only
                logger.debug(f"LED color {color} (no hardware) for {drone_uri}")

            return True
        except Exception as e:
            logger.error(f"Failed to set LED color for {drone_uri}: {e}")
            return False

    async def blink(self, drone_uri: str, color: LEDColor, duration: float = 3.0) -> bool:
        """
        Blink LED with a color for specified duration.

        Args:
            drone_uri: Drone URI
            color: LED color to blink
            duration: Blink duration in seconds

        Returns:
            True if successful
        """
        logger.info(f"Blinking LED {color} for {duration}s on drone {drone_uri}")

        try:
            if drone_uri in self._drones:
                cf = self._drones[drone_uri]
                await self._blink_led(cf, color, duration)
            else:
                # No hardware - simulate with sleep
                await asyncio.sleep(duration)

            return True
        except Exception as e:
            logger.error(f"Failed to blink LED for {drone_uri}: {e}")
            return False

    async def off(self, drone_uri: str) -> bool:
        """
        Turn off LED.

        Args:
            drone_uri: Drone URI

        Returns:
            True if successful
        """
        logger.info(f"Turning off LED for drone {drone_uri}")

        try:
            if drone_uri in self._drones:
                cf = self._drones[drone_uri]
                await self._set_led_color(cf, None)  # None = off
            return True
        except Exception as e:
            logger.error(f"Failed to turn off LED for {drone_uri}: {e}")
            return False

    async def set_state_color(self, drone_uri: str, state: str) -> bool:
        """
        Set LED color based on drone state.

        Args:
            drone_uri: Drone URI
            state: Drone state (idle, busy, offline, error)

        Returns:
            True if successful
        """
        # Map state to color
        state_to_color = {
            "idle": LEDColor.GREEN,
            "busy": LEDColor.YELLOW,
            "offline": None,  # Will blink green
            "error": LEDColor.RED,
        }

        color = state_to_color.get(state)

        if state == "offline":
            # Blink green slowly for offline
            return await self.blink(drone_uri, LEDColor.GREEN, duration=self.BLINK_SLOW)
        elif color:
            return await self.set_color(drone_uri, color)
        else:
            return await self.off(drone_uri)

    def register_drone(self, drone_uri: str) -> None:
        """Register a drone for LED control."""
        # Note: In a full implementation, this would store the Crazyflie instance
        # For now, we track URIs for logging purposes
        if drone_uri not in self._drones:
            logger.info(f"Registering drone {drone_uri} for LED control")

    def unregister_drone(self, drone_uri: str) -> None:
        """Unregister a drone from LED control."""
        if drone_uri in self._drones:
            del self._drones[drone_uri]
            logger.info(f"Unregistered drone {drone_uri} from LED control")

    async def _set_led_color(self, cf, color: Optional[LEDColor]) -> None:
        """Set LED color on actual Crazyflie hardware."""
        # Map color to LED parameter
        # Crazyflie has 4 LEDs: LED1-4. We'll use LED1 for status.
        color_map = {
            LEDColor.GREEN: 1,  # Green
            LEDColor.YELLOW: 3,  # Yellow (green + red)
            LEDColor.RED: 4,     # Red
            None: 0,             # Off
        }

        led_value = color_map.get(color, 0)

        # Set LED1 to the specified color
        # Note: This uses the LED ring parameter - actual implementation
        # may vary based on Crazyflie firmware version
        try:
            def _set_led():
                # LED ring mode: 0=off, 1=green, 2=red, 3=yellow, etc.
                cf.param.set_value("led_ring.enable", 1)
                cf.param.set_value("led_ring.mode", led_value)

            await asyncio.to_thread(_set_led)
        except Exception as e:
            logger.warning(f"Could not set LED on hardware: {e}")

    async def _blink_led(self, cf, color: LEDColor, duration: float) -> None:
        """Blink LED on actual Crazyflie hardware."""
        # Blink by toggling LED on/off
        color_on = color
        blink_rate = self.BLINK_FAST

        start_time = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start_time < duration:
            await self._set_led_color(cf, color_on)
            await asyncio.sleep(blink_rate)
            await self._set_led_color(cf, None)
            await asyncio.sleep(blink_rate)

        # Ensure LED is off at end
        await self._set_led_color(cf, None)


# Global LED controller instance
_led_controller: Optional[LEDController] = None


async def get_led_controller() -> LEDController:
    """Get global LED controller instance."""
    global _led_controller
    if _led_controller is None:
        _led_controller = LEDController()
    return _led_controller
