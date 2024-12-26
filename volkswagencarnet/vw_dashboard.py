"""Utilities for integration with Home Assistant."""

# Thanks to molobrakos

from datetime import datetime
import logging

from .vw_const import TEMP_CELSIUS, VWDeviceClass, VWStateClass
from .vw_utilities import camel2slug
from .vw_vehicle import Vehicle

_LOGGER = logging.getLogger(__name__)


class Instrument:
    """Base class for all components."""

    vehicle: Vehicle

    def __init__(
        self,
        component,
        attr: str,
        name: str,
        icon: str | None = None,
        entity_type: str | None = None,
        device_class: str | None = None,
        state_class: str | None = None,
    ) -> None:
        """Init."""
        self.attr = attr
        self.component = component
        self.name = name
        self.icon = icon
        self.entity_type = entity_type
        self.device_class = device_class
        self.state_class = state_class
        self.callback = None

    def __repr__(self) -> str:
        """Return string representation of class."""
        return self.full_name

    def configurate(self, **args):
        """Override in subclasses."""

    @property
    def slug_attr(self) -> str:
        """Return slugified attribute name."""
        return camel2slug(self.attr.replace(".", "_"))

    def setup(self, vehicle: Vehicle, **config) -> bool:
        """Set up entity if supported."""
        self.vehicle = vehicle
        if not self.is_supported:
            _LOGGER.debug(
                "%s (%s:%s) is not supported", self, type(self).__name__, self.attr
            )
            return False

        _LOGGER.debug("%s is supported", self)
        self.configurate(**config)
        return True

    @property
    def vehicle_name(self) -> str:
        """Return vehicle name."""
        return self.vehicle.vin

    @property
    def full_name(self) -> str:
        """Return full device name."""
        return f"{self.vehicle_name} {self.name}"

    @property
    def is_mutable(self) -> bool:
        """Override in subclasses."""
        raise NotImplementedError("Must be set")

    @property
    def str_state(self) -> str:
        """Return current state as string."""
        return self.state

    @property
    def state(self) -> object:
        """Return current state."""
        if hasattr(self.vehicle, self.attr):
            return getattr(self.vehicle, self.attr)
        _LOGGER.debug('Could not find attribute "%s"', self.attr)
        return self.vehicle.get_attr(self.attr)

    @property
    def attributes(self) -> dict:
        """Override in subclasses."""
        return {}

    @property
    def is_supported(self) -> bool:
        """Check entity support."""
        supported = "is_" + self.attr + "_supported"
        if hasattr(self.vehicle, supported):
            return getattr(self.vehicle, supported)
        return False

    @property
    def last_refresh(self) -> datetime | None:
        """Return last_updated attribute."""
        if hasattr(self.vehicle, self.attr + "_last_updated"):
            return getattr(self.vehicle, self.attr + "_last_updated")
        _LOGGER.warning(
            "Implement in subclasses. %s:%s_last_updated", self.__class__, self.attr
        )
        if self.state_class is not None:
            raise NotImplementedError(
                f"Implement in subclasses. {self.__class__}:{self.attr}_last_updated"
            )
        return None


class Sensor(Instrument):
    """Base class for sensor type entities."""

    def __init__(
        self,
        attr: str,
        name: str,
        icon: str | None,
        unit: str | None,
        entity_type: str | None = None,
        device_class: str | None = None,
        state_class: str | None = None,
    ) -> None:
        """Init."""
        super().__init__(
            component="sensor",
            attr=attr,
            name=name,
            icon=icon,
            entity_type=entity_type,
            device_class=device_class,
            state_class=state_class,
        )
        self.unit = unit
        self.convert = False

    def configurate(self, miles=False, scandinavian_miles=False, **config):
        """Configure unit conversion."""
        if self.unit and miles:
            if self.unit == "km":
                self.unit = "mi"
                self.convert = True
            elif self.unit == "km/h":
                self.unit = "mi/h"
                self.convert = True
            elif self.unit == "l/100 km":
                self.unit = "l/100 mi"
                self.convert = True
            elif self.unit == "kWh/100 km":
                self.unit = "mi/kWh"
                self.convert = True
        elif self.unit and scandinavian_miles:
            if self.unit == "km":
                self.unit = "mil"
            elif self.unit == "km/h":
                self.unit = "mil/h"
            elif self.unit == "l/100 km":
                self.unit = "l/100 mil"
            elif self.unit == "kWh/100 km":
                self.unit = "kWh/100 mil"

    @property
    def is_mutable(self):
        """Return boolean is_mutable."""
        return False

    @property
    def str_state(self):
        """Return current state as string."""
        if self.unit:
            return f"{self.state} {self.unit}"
        return f"{self.state}"

    @property
    def state(self):
        """Return current state."""
        # Base value
        val = super().state
        # If the base value is not valid or convert is not true, return the original value
        if not val or not self.convert:
            return val
        # Simplified condition checking
        if self.unit:
            if "mi" in self.unit:
                if self.unit in ["mi", "mi/h"]:
                    return round(int(val) * 0.6213712)
            if "gal/100 mi" in self.unit:
                return round(val * 0.4251438, 1)
            if "mi/kWh" in self.unit:
                return round((100 / val) * 0.6213712, 1)
            if "°F" in self.unit:
                return round((val * 9 / 5) + 32, 1)
            if self.unit in ["mil", "mil/h"]:
                return val / 10
        # Default case, return the unmodified value
        return val


class BinarySensor(Instrument):
    """BinarySensor instrument."""

    def __init__(
        self, attr, name, device_class, icon="", entity_type=None, reverse_state=False
    ) -> None:
        """Init."""
        super().__init__(
            component="binary_sensor",
            attr=attr,
            name=name,
            icon=icon,
            entity_type=entity_type,
        )
        self.device_class = device_class
        self.reverse_state = reverse_state

    @property
    def is_mutable(self):
        """Return boolean is_mutable."""
        return False

    @property
    def str_state(self):
        """Return current state as string."""
        if self.device_class in [VWDeviceClass.DOOR, VWDeviceClass.WINDOW]:
            return "Open" if self.state else "Closed"
        if self.device_class == VWDeviceClass.LOCK:
            return "Unlocked" if self.state else "Locked"
        if self.device_class == "safety":
            return "Warning!" if self.state else "OK"
        if self.device_class == VWDeviceClass.PLUG:
            return "Charging" if self.state else "Plug removed"
        if self.state is None:
            _LOGGER.error("Can not encode state %s:%s", self.attr, self.state)
            return "?"
        return "On" if self.state else "Off"

    @property
    def state(self):
        """Return current state."""
        val = super().state

        if isinstance(val, (bool, list)):
            if self.reverse_state:
                if bool(val):
                    return False
                return True
            return bool(val)
        if isinstance(val, str):
            return val != "Normal"
        return val

    @property
    def is_on(self):
        """Return state."""
        return self.state


class Switch(Instrument):
    """Switch instrument."""

    def __init__(self, attr, name, icon, entity_type=None) -> None:
        """Init."""
        super().__init__(
            component="switch", attr=attr, name=name, icon=icon, entity_type=entity_type
        )

    @property
    def is_mutable(self):
        """Return boolean is_mutable."""
        return True

    @property
    def str_state(self):
        """Return current state as string."""
        return "On" if self.state else "Off"

    def is_on(self):
        """Return state."""
        return self.state

    def turn_on(self):
        """Turn on."""

    def turn_off(self):
        """Turn off."""

    @property
    def assumed_state(self) -> bool:
        """Assume state."""
        return True


class Number(Instrument):
    """Number instrument."""

    def __init__(
        self,
        attr: str,
        name: str,
        icon: str | None,
        unit: str | None,
        entity_type: str | None = None,
        device_class: str | None = None,
        state_class: str | None = None,
    ) -> None:
        """Init."""
        super().__init__(
            component="number",
            attr=attr,
            name=name,
            icon=icon,
            entity_type=entity_type,
            device_class=device_class,
            state_class=state_class,
        )
        self.unit = unit

    @property
    def is_mutable(self):
        """Return boolean is_mutable."""
        return False

    @property
    def state(self):
        """Return current state."""
        raise NotImplementedError

    @property
    def min_value(self):
        """Return min value."""
        raise NotImplementedError

    @property
    def max_value(self):
        """Return max value."""
        raise NotImplementedError

    @property
    def native_step(self):
        """Return native step."""
        raise NotImplementedError


class Select(Instrument):
    """Select instrument."""

    def __init__(
        self,
        attr: str,
        name: str,
        icon: str | None,
        unit: str | None,
        entity_type: str | None = None,
        device_class: str | None = None,
        state_class: str | None = None,
    ) -> None:
        """Init."""
        super().__init__(
            component="select",
            attr=attr,
            name=name,
            icon=icon,
            entity_type=entity_type,
            device_class=device_class,
            state_class=state_class,
        )
        self.unit = unit

    @property
    def is_mutable(self):
        """Return boolean is_mutable."""
        return False

    @property
    def state(self):
        """Return current state."""
        raise NotImplementedError

    @property
    def current_option(self):
        """Return current option."""
        raise NotImplementedError

    @property
    def options(self):
        """Return options."""
        raise NotImplementedError


class Position(Instrument):
    """Position instrument."""

    def __init__(self) -> None:
        """Init."""
        super().__init__(component="device_tracker", attr="position", name="Position")

    @property
    def is_mutable(self):
        """Return boolean is_mutable."""
        return False

    @property
    def state(self):
        """Return current state."""
        state = super().state  # or {}
        return (
            state.get("lat", "?"),
            state.get("lng", "?"),
            state.get("timestamp", None),
        )

    @property
    def str_state(self):
        """Return current state as string."""
        state = super().state  # or {}
        ts = state.get("timestamp", None)
        return (
            state.get("lat", "?"),
            state.get("lng", "?"),
            str(ts.astimezone(tz=None)) if ts else None,
        )


class DoorLock(Instrument):
    """DoorLock instrument."""

    def __init__(self) -> None:
        """Init."""
        super().__init__(
            component=VWDeviceClass.LOCK, attr="door_locked", name="Door locked"
        )
        self.spin = ""

    def configurate(self, **config):
        """Configure spin."""
        self.spin = config.get("spin", "")

    @property
    def is_mutable(self):
        """Return boolean is_mutable."""
        return True

    @property
    def str_state(self):
        """Return current state as string."""
        return "Locked" if self.state else "Unlocked"

    @property
    def state(self):
        """Return current state."""
        return self.vehicle.door_locked

    @property
    def is_locked(self):
        """Return current state."""
        return self.state

    async def lock(self):
        """Trigger Lock."""
        try:
            response = await self.vehicle.set_lock(VWDeviceClass.LOCK, self.spin)
            await self.vehicle.update()
            if self.callback is not None:
                self.callback()
        except Exception as e:  # pylint: disable=broad-exception-caught
            _LOGGER.error("Lock failed: %s", e.args[0])
            return False
        else:
            return response

    async def unlock(self):
        """Trigger Unlock."""
        try:
            response = await self.vehicle.set_lock("unlock", self.spin)
            await self.vehicle.update()
            if self.callback is not None:
                self.callback()
        except Exception as e:  # pylint: disable=broad-exception-caught
            _LOGGER.error("Unlock failed: %s", e.args[0])
            return False
        else:
            return response

    @property
    def attributes(self) -> dict:
        """Return attributes."""
        return {"last_result": self.vehicle.lock_action_status}


class TrunkLock(Instrument):
    """TrunkLock instrument."""

    def __init__(self) -> None:
        """Init."""
        super().__init__(
            component=VWDeviceClass.LOCK, attr="trunk_locked", name="Trunk locked"
        )

    @property
    def is_mutable(self):
        """Return boolean is_mutable."""
        return True

    @property
    def str_state(self):
        """Return current state as string."""
        return "Locked" if self.state else "Unlocked"

    @property
    def state(self):
        """Return current state."""
        return self.vehicle.trunk_locked

    @property
    def is_locked(self):
        """Return current state."""
        return self.state

    async def lock(self):
        """Trigger lock."""
        return None

    async def unlock(self):
        """Trigger unlock."""
        return None


# Numbers


class AuxiliaryDuration(Number):
    """Currently disabled due to the lack of auxiliary settings API."""

    def __init__(self) -> None:
        """Init."""
        super().__init__(
            attr="auxiliary_duration",
            name="Auxiliary duration",
            icon="mdi:timer",
            unit="min",
            entity_type="config",
        )
        self.spin = ""

    def configurate(self, **config):
        """Configure spin."""
        self.spin = config.get("spin", "")

    @property
    def state(self):
        """Return current state."""
        return self.vehicle.auxiliary_duration

    async def set_value(self, minutes: int):
        """Set value."""
        await self.vehicle.set_auxiliary_duration(minutes, self.spin)
        await self.vehicle.update()

    @property
    def min_value(self):
        """Return min value."""
        return 5

    @property
    def max_value(self):
        """Return max value."""
        return 30

    @property
    def native_step(self):
        """Return native step."""
        return 5

    @property
    def attributes(self) -> dict:
        """Return attributes."""
        return {"last_result": self.vehicle.climater_action_status}


class BatteryTargetSOC(Number):
    """Battery target charge level."""

    def __init__(self) -> None:
        """Init."""
        super().__init__(
            attr="battery_target_charge_level",
            name="Battery target charge level",
            icon="mdi:battery-arrow-up",
            unit="%",
            entity_type="config",
        )

    @property
    def state(self):
        """Return current state."""
        return self.vehicle.battery_target_charge_level

    async def set_value(self, value: int):
        """Set value."""
        await self.vehicle.set_charging_settings(
            setting="battery_target_charge_level", value=value
        )
        await self.vehicle.update()

    @property
    def min_value(self):
        """Return min value."""
        return 50

    @property
    def max_value(self):
        """Return max value."""
        return 100

    @property
    def native_step(self):
        """Return native step."""
        return 10

    @property
    def attributes(self) -> dict:
        """Return attributes."""
        return {"last_result": self.vehicle.charger_action_status}


class ClimatisationTargetTemperature(Number):
    """Climatisation target temperature."""

    def __init__(self) -> None:
        """Init."""
        super().__init__(
            attr="climatisation_target_temperature",
            name="Climatisation target temperature",
            icon="mdi:thermometer",
            device_class=VWDeviceClass.TEMPERATURE,
            unit=TEMP_CELSIUS,
        )

    @property
    def state(self):
        """Return current state."""
        return self.vehicle.climatisation_target_temperature

    async def set_value(self, value: float):
        """Set value."""
        await self.vehicle.set_climatisation_settings(
            setting="climatisation_target_temperature", value=value
        )
        await self.vehicle.update()

    @property
    def min_value(self):
        """Return min value."""
        return 15.5

    @property
    def max_value(self):
        """Return max value."""
        return 30

    @property
    def native_step(self):
        """Return native step."""
        return 0.5

    @property
    def attributes(self) -> dict:
        """Return attributes."""
        return {"last_result": self.vehicle.climater_action_status}


# Select


class ChargeMaxACAmpere(Select):
    """Maximum charge ampere."""

    def __init__(self) -> None:
        """Init."""
        super().__init__(
            attr="charge_max_ac_ampere",
            name="Charger max AC ampere",
            icon="mdi:flash-auto",
            unit="A",
            entity_type="config",
        )

    @property
    def state(self):
        """Return current state."""
        return self.vehicle.charge_max_ac_ampere

    @property
    def current_option(self):
        """Return current option."""
        return str(self.vehicle.charge_max_ac_ampere)

    @property
    def options(self) -> dict:
        """Return options."""
        return ["5", "10", "13", "32"]

    async def set_value(self, ampere: str):
        """Set value."""
        await self.vehicle.set_charging_settings(
            setting="max_charge_amperage", value=ampere
        )
        await self.vehicle.update()


# Switches


class RequestUpdate(Switch):
    """Force data refresh."""

    def __init__(self) -> None:
        """Init."""
        super().__init__(
            attr="refresh_data", name="Force data refresh", icon="mdi:car-connected"
        )

    @property
    def state(self):
        """Return current state."""
        return self.vehicle.refresh_data

    async def turn_on(self):
        """Turn on."""
        await self.vehicle.set_refresh()
        await self.vehicle.update()
        if self.callback is not None:
            self.callback()

    async def turn_off(self):
        """Turn off."""

    @property
    def assumed_state(self) -> bool:
        """Don't assume state."""
        return False

    @property
    def attributes(self) -> dict:
        """Return attributes."""
        return {"last_result": self.vehicle.refresh_action_status}


class ElectricClimatisation(Switch):
    """Electric Climatisation."""

    def __init__(self) -> None:
        """Init."""
        super().__init__(
            attr="electric_climatisation",
            name="Electric Climatisation",
            icon="mdi:air-conditioner",
        )

    @property
    def state(self):
        """Return current state."""
        return self.vehicle.electric_climatisation

    async def turn_on(self):
        """Turn on."""
        await self.vehicle.set_climatisation("start")
        await self.vehicle.update()

    async def turn_off(self):
        """Turn off."""
        await self.vehicle.set_climatisation("stop")
        await self.vehicle.update()

    @property
    def assumed_state(self) -> bool:
        """Don't assume state."""
        return False

    @property
    def attributes(self) -> dict:
        """Return attributes."""
        return {"last_result": self.vehicle.climater_action_status}


class AuxiliaryClimatisation(Switch):
    """Auxiliary Climatisation."""

    def __init__(self) -> None:
        """Init."""
        super().__init__(
            attr="auxiliary_climatisation",
            name="Auxiliary Climatisation",
            icon="mdi:radiator",
        )
        self.spin = ""

    def configurate(self, **config):
        """Configure spin."""
        self.spin = config.get("spin", "")

    @property
    def state(self):
        """Return current state."""
        return self.vehicle.auxiliary_climatisation

    async def turn_on(self):
        """Turn on."""
        await self.vehicle.set_auxiliary_climatisation("start", self.spin)
        await self.vehicle.update()

    async def turn_off(self):
        """Turn off."""
        await self.vehicle.set_auxiliary_climatisation("stop", self.spin)
        await self.vehicle.update()

    @property
    def assumed_state(self) -> bool:
        """Don't assume state."""
        return False

    @property
    def attributes(self) -> dict:
        """Return attributes."""
        return {"last_result": self.vehicle.climater_action_status}


class Charging(Switch):
    """Charging."""

    def __init__(self) -> None:
        """Init."""
        super().__init__(attr="charging", name="Charging", icon="mdi:battery")

    @property
    def state(self):
        """Return current state."""
        return self.vehicle.charging

    async def turn_on(self):
        """Turn on."""
        await self.vehicle.set_charger("start")
        await self.vehicle.update()

    async def turn_off(self):
        """Turn off."""
        await self.vehicle.set_charger("stop")
        await self.vehicle.update()

    @property
    def assumed_state(self) -> bool:
        """Don't assume state."""
        return False

    @property
    def attributes(self) -> dict:
        """Return attributes."""
        return {"last_result": self.vehicle.charger_action_status}


class ReducedACCharging(Switch):
    """Reduced AC Charging."""

    def __init__(self) -> None:
        """Init."""
        super().__init__(
            attr="reduced_ac_charging",
            name="Reduced AC Charging",
            icon="mdi:ev-station",
            entity_type="config",
        )

    @property
    def state(self):
        """Return current state."""
        return self.vehicle.reduced_ac_charging

    async def turn_on(self):
        """Turn on."""
        await self.vehicle.set_charging_settings(
            setting="reduced_ac_charging", value="reduced"
        )
        await self.vehicle.update()

    async def turn_off(self):
        """Turn off."""
        await self.vehicle.set_charging_settings(
            setting="reduced_ac_charging", value="maximum"
        )
        await self.vehicle.update()

    @property
    def assumed_state(self) -> bool:
        """Don't assume state."""
        return False

    @property
    def attributes(self) -> dict:
        """Return attributes."""
        return {"last_result": self.vehicle.charger_action_status}


class AutoReleaseACConnector(Switch):
    """Auto-release AC connector."""

    def __init__(self) -> None:
        """Init."""
        super().__init__(
            attr="auto_release_ac_connector",
            name="Auto-release AC connector",
            icon="mdi:ev-plug-type2",
            entity_type="config",
        )

    @property
    def state(self):
        """Return current state."""
        return self.vehicle.auto_release_ac_connector

    async def turn_on(self):
        """Turn on."""
        await self.vehicle.set_charging_settings(
            setting="auto_release_ac_connector", value="permanent"
        )
        await self.vehicle.update()

    async def turn_off(self):
        """Turn off."""
        await self.vehicle.set_charging_settings(
            setting="auto_release_ac_connector", value="off"
        )
        await self.vehicle.update()

    @property
    def assumed_state(self) -> bool:
        """Don't assume state."""
        return False


class BatteryCareMode(Switch):
    """Battery care mode."""

    def __init__(self) -> None:
        """Init."""
        super().__init__(
            attr="battery_care_mode",
            name="Battery care mode",
            icon="mdi:battery-heart-variant",
            entity_type="config",
        )

    @property
    def state(self):
        """Return current state."""
        return self.vehicle.battery_care_mode

    async def turn_on(self):
        """Turn on."""
        await self.vehicle.set_charging_care_settings(value="activated")
        await self.vehicle.update()

    async def turn_off(self):
        """Turn off."""
        await self.vehicle.set_charging_care_settings(value="deactivated")
        await self.vehicle.update()

    @property
    def assumed_state(self) -> bool:
        """Don't assume state."""
        return False

    @property
    def attributes(self) -> dict:
        """Return attributes."""
        return {"last_result": self.vehicle.charger_action_status}


class OptimisedBatteryUse(Switch):
    """Optimised battery use."""

    def __init__(self) -> None:
        """Init."""
        super().__init__(
            attr="optimised_battery_use",
            name="Optimised battery use",
            icon="mdi:battery-check",
            entity_type="config",
        )

    @property
    def state(self):
        """Return current state."""
        return self.vehicle.optimised_battery_use

    async def turn_on(self):
        """Turn on."""
        await self.vehicle.set_readiness_battery_support(value=True)
        await self.vehicle.update()

    async def turn_off(self):
        """Turn off."""
        await self.vehicle.set_readiness_battery_support(value=False)
        await self.vehicle.update()

    @property
    def assumed_state(self) -> bool:
        """Don't assume state."""
        return False

    @property
    def attributes(self) -> dict:
        """Return attributes."""
        return {"last_result": self.vehicle.charger_action_status}


class DepartureTimer(Switch):
    """Departure timers."""

    def __init__(self, id: str | int) -> None:
        """Init."""
        self._id = id
        super().__init__(
            attr=f"departure_timer{id}",
            name=f"Departure Timer {id}",
            icon="mdi:car-clock",
            entity_type="config",
        )
        self.spin = ""

    def configurate(self, **config):
        """Configure spin."""
        self.spin = config.get("spin", "")

    @property
    def state(self):
        """Return switch state."""
        return self.vehicle.departure_timer_enabled(self._id)

    async def turn_on(self):
        """Enable timer."""
        await self.vehicle.set_departure_timer(
            timer_id=self._id, spin=self.spin, enable=True
        )
        await self.vehicle.update()

    async def turn_off(self):
        """Disable timer."""
        await self.vehicle.set_departure_timer(
            timer_id=self._id, spin=self.spin, enable=False
        )
        await self.vehicle.update()

    @property
    def assumed_state(self):
        """Don't assume state info."""
        return False

    @property
    def attributes(self):
        """Timer attributes."""
        data = self.vehicle.timer_attributes(self._id)
        return dict(data)


class ACDepartureTimer(Switch):
    """Air conditioning departure timers."""

    def __init__(self, id: str | int) -> None:
        """Init."""
        self._id = id
        super().__init__(
            attr=f"ac_departure_timer{id}",
            name=f"AC Departure Timer {id}",
            icon="mdi:fan-clock",
            entity_type="config",
        )

    @property
    def state(self):
        """Return current state."""
        return self.vehicle.ac_departure_timer_enabled(self._id)

    async def turn_on(self):
        """Enable timer."""
        await self.vehicle.set_ac_departure_timer(timer_id=self._id, enable=True)
        await self.vehicle.update()

    async def turn_off(self):
        """Disable timer."""
        await self.vehicle.set_ac_departure_timer(timer_id=self._id, enable=False)
        await self.vehicle.update()

    @property
    def assumed_state(self):
        """Don't assume state info."""
        return False

    @property
    def attributes(self):
        """Timer attributes."""
        data = self.vehicle.ac_timer_attributes(self._id)
        return dict(data)


class WindowHeater(Switch):
    """Window Heater."""

    def __init__(self) -> None:
        """Init."""
        super().__init__(
            attr="window_heater", name="Window Heater", icon="mdi:car-defrost-rear"
        )

    @property
    def state(self):
        """Return current state."""
        return self.vehicle.window_heater

    async def turn_on(self):
        """Turn on."""
        await self.vehicle.set_window_heating("start")
        await self.vehicle.update()

    async def turn_off(self):
        """Turn off."""
        await self.vehicle.set_window_heating("stop")
        await self.vehicle.update()

    @property
    def assumed_state(self) -> bool:
        """Don't assume state."""
        return False

    @property
    def attributes(self) -> dict:
        """Return attributes."""
        return {"last_result": self.vehicle.climater_action_status}


class BatteryClimatisation(Switch):
    """Climatisation from battery."""

    def __init__(self) -> None:
        """Init."""
        super().__init__(
            attr="climatisation_without_external_power",
            name="Climatisation from battery",
            icon="mdi:power-plug",
            entity_type="config",
        )

    @property
    def state(self):
        """Return current state."""
        return self.vehicle.climatisation_without_external_power

    async def turn_on(self):
        """Turn on."""
        await self.vehicle.set_climatisation_settings(
            setting="climatisation_without_external_power", value=True
        )
        await self.vehicle.update()

    async def turn_off(self):
        """Turn off."""
        await self.vehicle.set_climatisation_settings(
            setting="climatisation_without_external_power", value=False
        )
        await self.vehicle.update()

    @property
    def assumed_state(self) -> bool:
        """Don't assume state."""
        return False

    @property
    def attributes(self) -> dict:
        """Return attributes."""
        return {"last_result": self.vehicle.climater_action_status}


class AuxiliaryAC(Switch):
    """Auxiliary air conditioning."""

    def __init__(self) -> None:
        """Init."""
        super().__init__(
            attr="auxiliary_air_conditioning",
            name="Auxiliary air conditioning",
            icon="mdi:air-filter",
            entity_type="config",
        )

    @property
    def state(self):
        """Return current state."""
        return self.vehicle.auxiliary_air_conditioning

    async def turn_on(self):
        """Turn on."""
        await self.vehicle.set_climatisation_settings(
            setting="auxiliary_air_conditioning", value=True
        )
        await self.vehicle.update()

    async def turn_off(self):
        """Turn off."""
        await self.vehicle.set_climatisation_settings(
            setting="auxiliary_air_conditioning", value=False
        )
        await self.vehicle.update()

    @property
    def assumed_state(self) -> bool:
        """Don't assume state."""
        return False

    @property
    def attributes(self) -> dict:
        """Return attributes."""
        return {"last_result": self.vehicle.climater_action_status}


class AutomaticWindowHeating(Switch):
    """Automatic window heating."""

    def __init__(self) -> None:
        """Init."""
        super().__init__(
            attr="automatic_window_heating",
            name="Automatic window heating",
            icon="mdi:car-defrost-rear",
            entity_type="config",
        )

    @property
    def state(self):
        """Return current state."""
        return self.vehicle.automatic_window_heating

    async def turn_on(self):
        """Turn on."""
        await self.vehicle.set_climatisation_settings(
            setting="automatic_window_heating", value=True
        )
        await self.vehicle.update()

    async def turn_off(self):
        """Turn off."""
        await self.vehicle.set_climatisation_settings(
            setting="automatic_window_heating", value=False
        )
        await self.vehicle.update()

    @property
    def assumed_state(self) -> bool:
        """Don't assume state."""
        return False

    @property
    def attributes(self) -> dict:
        """Return attributes."""
        return {"last_result": self.vehicle.climater_action_status}


class ZoneFrontLeft(Switch):
    """Zone Front Left."""

    def __init__(self) -> None:
        """Init."""
        super().__init__(
            attr="zone_front_left",
            name="Zone Front Left",
            icon="mdi:account-arrow-left",
            entity_type="config",
        )

    @property
    def state(self):
        """Return current state."""
        return self.vehicle.zone_front_left

    async def turn_on(self):
        """Turn on."""
        await self.vehicle.set_climatisation_settings(
            setting="zone_front_left", value=True
        )
        await self.vehicle.update()

    async def turn_off(self):
        """Turn off."""
        await self.vehicle.set_climatisation_settings(
            setting="zone_front_left", value=False
        )
        await self.vehicle.update()

    @property
    def assumed_state(self) -> bool:
        """Don't assume state."""
        return False

    @property
    def attributes(self) -> dict:
        """Return attributes."""
        return {"last_result": self.vehicle.climater_action_status}


class ZoneFrontRight(Switch):
    """Zone Front Right."""

    def __init__(self) -> None:
        """Init."""
        super().__init__(
            attr="zone_front_right",
            name="Zone Front Right",
            icon="mdi:account-arrow-right",
            entity_type="config",
        )

    @property
    def state(self):
        """Return current state."""
        return self.vehicle.zone_front_right

    async def turn_on(self):
        """Turn on."""
        await self.vehicle.set_climatisation_settings(
            setting="zone_front_right", value=True
        )
        await self.vehicle.update()

    async def turn_off(self):
        """Turn off."""
        await self.vehicle.set_climatisation_settings(
            setting="zone_front_right", value=False
        )
        await self.vehicle.update()

    @property
    def assumed_state(self) -> bool:
        """Don't assume state."""
        return False

    @property
    def attributes(self) -> dict:
        """Return attributes."""
        return {"last_result": self.vehicle.climater_action_status}


class RequestResults(Sensor):
    """Request results sensor class."""

    def __init__(self) -> None:
        """Init."""
        super().__init__(
            attr="request_results",
            name="Request results",
            icon="mdi:chat-alert",
            unit="",
            entity_type="diag",
        )

    @property
    def state(self) -> object:
        """Return current state."""
        if self.vehicle.request_results.get("state", False):
            return self.vehicle.request_results.get("state")
        return "Unknown"

    @property
    def assumed_state(self) -> bool:
        """Don't assume state."""
        return False

    @property
    def attributes(self) -> dict:
        """Return attributes."""
        return dict(self.vehicle.request_results)


def create_instruments():
    """Return list of all entities."""
    return [
        Position(),
        # AuxiliaryDuration(),
        BatteryTargetSOC(),
        ClimatisationTargetTemperature(),
        DoorLock(),
        TrunkLock(),
        ChargeMaxACAmpere(),
        RequestUpdate(),
        WindowHeater(),
        BatteryClimatisation(),
        AuxiliaryAC(),
        AutomaticWindowHeating(),
        ZoneFrontLeft(),
        ZoneFrontRight(),
        ElectricClimatisation(),
        AuxiliaryClimatisation(),
        Charging(),
        ReducedACCharging(),
        AutoReleaseACConnector(),
        BatteryCareMode(),
        OptimisedBatteryUse(),
        DepartureTimer(1),
        DepartureTimer(2),
        DepartureTimer(3),
        ACDepartureTimer(1),
        ACDepartureTimer(2),
        RequestResults(),
        Sensor(
            attr="distance",
            name="Odometer",
            icon="mdi:speedometer",
            unit="km",
            state_class=VWStateClass.TOTAL_INCREASING,
        ),
        Sensor(
            attr="battery_level",
            name="Battery level",
            icon="mdi:battery",
            unit="%",
            device_class=VWDeviceClass.BATTERY,
            state_class=VWStateClass.MEASUREMENT,
        ),
        Sensor(
            attr="battery_target_charge_level",
            name="Battery target charge level",
            icon="mdi:battery-arrow-up",
            unit="%",
        ),
        Sensor(
            attr="hv_battery_min_temperature",
            name="HV battery min temperature",
            icon="mdi:thermometer-chevron-down",
            unit=TEMP_CELSIUS,
        ),
        Sensor(
            attr="hv_battery_max_temperature",
            name="HV battery max temperature",
            icon="mdi:thermometer-chevron-up",
            unit=TEMP_CELSIUS,
        ),
        Sensor(
            attr="adblue_level",
            name="Adblue level",
            icon="mdi:fuel",
            unit="km",
            state_class=VWStateClass.MEASUREMENT,
        ),
        Sensor(
            attr="fuel_level",
            name="Fuel level",
            icon="mdi:fuel",
            unit="%",
            state_class=VWStateClass.MEASUREMENT,
        ),
        Sensor(
            attr="gas_level",
            name="Gas level",
            icon="mdi:gas-cylinder",
            unit="%",
            state_class=VWStateClass.MEASUREMENT,
        ),
        Sensor(
            attr="service_inspection",
            name="Service inspection days",
            icon="mdi:garage",
            unit="days",
        ),
        Sensor(
            attr="service_inspection_distance",
            name="Service inspection distance",
            icon="mdi:garage",
            unit="km",
        ),
        Sensor(
            attr="oil_inspection",
            name="Oil inspection days",
            icon="mdi:oil",
            unit="days",
        ),
        Sensor(
            attr="oil_inspection_distance",
            name="Oil inspection distance",
            icon="mdi:oil",
            unit="km",
        ),
        Sensor(
            attr="last_connected",
            name="Last connected",
            icon="mdi:clock",
            unit="",
            device_class=VWDeviceClass.TIMESTAMP,
            entity_type="diag",
        ),
        Sensor(
            attr="parking_time",
            name="Parking time",
            icon="mdi:clock",
            unit="",
            device_class=VWDeviceClass.TIMESTAMP,
        ),
        Sensor(
            attr="charging_time_left",
            name="Charging time left",
            icon="mdi:battery-charging-100",
            unit="min",
            state_class=VWStateClass.MEASUREMENT,
        ),
        Sensor(
            attr="electric_range",
            name="Electric range",
            icon="mdi:car-electric",
            unit="km",
        ),
        Sensor(
            attr="combustion_range",
            name="Combustion range",
            icon="mdi:car",
            unit="km",
        ),
        Sensor(
            attr="fuel_range",
            name="Fuel range",
            icon="mdi:car",
            unit="km",
        ),
        Sensor(
            attr="gas_range",
            name="Gas range",
            icon="mdi:car",
            unit="km",
        ),
        Sensor(
            attr="combined_range",
            name="Combined range",
            icon="mdi:car",
            unit="km",
        ),
        Sensor(
            attr="battery_cruising_range",
            name="Battery cruising range",
            icon="mdi:car-settings",
            unit="km",
        ),
        Sensor(
            attr="charge_max_ac_setting",
            name="Charger max AC setting",
            icon="mdi:flash",
            unit="",
        ),
        Sensor(
            attr="charge_max_ac_ampere",
            name="Charger max AC ampere",
            icon="mdi:flash-auto",
            unit="A",
        ),
        Sensor(
            attr="charging_power",
            name="Charging Power",
            icon="mdi:transmission-tower",
            unit="kW",
        ),
        Sensor(
            attr="charging_rate",
            name="Charging Rate",
            icon="mdi:ev-station",
            unit="km/h",
        ),
        Sensor(
            attr="charger_type",
            name="Charger Type",
            icon="mdi:ev-plug-type1",
            unit="",
        ),
        Sensor(
            attr="climatisation_target_temperature",
            name="Climatisation target temperature",
            icon="mdi:thermometer",
            unit=TEMP_CELSIUS,
            device_class=VWDeviceClass.TEMPERATURE,
            state_class=VWStateClass.MEASUREMENT,
        ),
        Sensor(
            attr="trip_last_average_speed",
            name="Last trip average speed",
            icon="mdi:speedometer",
            unit="km/h",
            state_class=VWStateClass.MEASUREMENT,
        ),
        Sensor(
            attr="trip_last_average_electric_engine_consumption",
            name="Last trip average electric engine consumption",
            icon="mdi:car-battery",
            unit="kWh/100 km",
            state_class=VWStateClass.MEASUREMENT,
        ),
        Sensor(
            attr="trip_last_average_fuel_consumption",
            name="Last trip average fuel consumption",
            icon="mdi:fuel",
            unit="l/100 km",
            state_class=VWStateClass.MEASUREMENT,
        ),
        Sensor(
            attr="trip_last_average_gas_consumption",
            name="Last trip average gas consumption",
            icon="mdi:gas-cylinder",
            unit="m3/100km",
            state_class=VWStateClass.MEASUREMENT,
        ),
        Sensor(
            attr="trip_last_duration",
            name="Last trip duration",
            icon="mdi:clock",
            unit="min",
            state_class=VWStateClass.MEASUREMENT,
        ),
        Sensor(
            attr="trip_last_length",
            name="Last trip length",
            icon="mdi:map-marker-distance",
            unit="km",
            state_class=VWStateClass.MEASUREMENT,
        ),
        Sensor(
            attr="trip_last_recuperation",
            name="Last trip recuperation",
            icon="mdi:battery-plus",
            unit="kWh/100 km",
            state_class=VWStateClass.MEASUREMENT,
        ),
        Sensor(
            attr="trip_last_average_recuperation",
            name="Last trip average recuperation",
            icon="mdi:battery-plus",
            unit="kWh/100 km",
            state_class=VWStateClass.MEASUREMENT,
        ),
        Sensor(
            attr="trip_last_average_auxillary_consumption",
            name="Last trip average auxillary consumption",
            icon="mdi:flash",
            unit="kWh/100 km",
            state_class=VWStateClass.MEASUREMENT,
        ),
        Sensor(
            attr="trip_last_average_aux_consumer_consumption",
            name="Last trip average auxillary consumer consumption",
            icon="mdi:flash",
            unit="kWh/100 km",
            state_class=VWStateClass.MEASUREMENT,
        ),
        Sensor(
            attr="trip_last_total_electric_consumption",
            name="Last trip total electric consumption",
            icon="mdi:car-battery",
            unit="kWh/100 km",
            state_class=VWStateClass.MEASUREMENT,
        ),
        Sensor(
            attr="auxiliary_duration",
            name="Auxiliary Heater heating/ventilation duration",
            icon="mdi:timer",
            unit="minutes",
        ),
        Sensor(
            attr="auxiliary_remaining_climatisation_time",
            name="Auxiliary remaining climatisation time",
            icon="mdi:fan-clock",
            unit="minutes",
        ),
        Sensor(
            attr="electric_remaining_climatisation_time",
            name="Electric remaining climatisation time",
            icon="mdi:fan-clock",
            unit="minutes",
        ),
        Sensor(
            attr="car_type",
            name="Car Type",
            icon="mdi:car-select",
            unit="",
        ),
        Sensor(
            attr="api_vehicles_status",
            name="API vehicles",
            icon="mdi:api",
            unit="",
            entity_type="diag",
        ),
        Sensor(
            attr="api_capabilities_status",
            name="API capabilities",
            icon="mdi:api",
            unit="",
            entity_type="diag",
        ),
        Sensor(
            attr="api_trips_status",
            name="API trips",
            icon="mdi:api",
            unit="",
            entity_type="diag",
        ),
        Sensor(
            attr="api_selectivestatus_status",
            name="API selectivestatus",
            icon="mdi:api",
            unit="",
            entity_type="diag",
        ),
        Sensor(
            attr="api_parkingposition_status",
            name="API parkingposition",
            icon="mdi:api",
            unit="",
            entity_type="diag",
        ),
        Sensor(
            attr="api_token_status",
            name="API token",
            icon="mdi:api",
            unit="",
            entity_type="diag",
        ),
        Sensor(
            attr="last_data_refresh",
            name="Last data refresh",
            icon="mdi:clock",
            unit="",
            device_class=VWDeviceClass.TIMESTAMP,
            entity_type="diag",
        ),
        BinarySensor(
            attr="external_power",
            name="External power",
            device_class=VWDeviceClass.POWER,
        ),
        BinarySensor(
            attr="energy_flow", name="Energy flow", device_class=VWDeviceClass.POWER
        ),
        BinarySensor(
            attr="parking_light",
            name="Parking light",
            device_class=VWDeviceClass.LIGHT,
            icon="mdi:car-parking-lights",
        ),
        BinarySensor(
            attr="door_locked",
            name="Doors locked",
            device_class=VWDeviceClass.LOCK,
            reverse_state=True,
        ),
        BinarySensor(
            attr="door_locked_sensor",
            name="Doors locked",
            device_class=VWDeviceClass.LOCK,
            reverse_state=True,
        ),
        BinarySensor(
            attr="door_closed_left_front",
            name="Door closed left front",
            device_class=VWDeviceClass.DOOR,
            reverse_state=True,
            icon="mdi:car-door",
        ),
        BinarySensor(
            attr="door_closed_right_front",
            name="Door closed right front",
            device_class=VWDeviceClass.DOOR,
            reverse_state=True,
            icon="mdi:car-door",
        ),
        BinarySensor(
            attr="door_closed_left_back",
            name="Door closed left back",
            device_class=VWDeviceClass.DOOR,
            reverse_state=True,
            icon="mdi:car-door",
        ),
        BinarySensor(
            attr="door_closed_right_back",
            name="Door closed right back",
            device_class=VWDeviceClass.DOOR,
            reverse_state=True,
            icon="mdi:car-door",
        ),
        BinarySensor(
            attr="trunk_locked",
            name="Trunk locked",
            device_class=VWDeviceClass.LOCK,
            reverse_state=True,
        ),
        BinarySensor(
            attr="trunk_locked_sensor",
            name="Trunk locked",
            device_class=VWDeviceClass.LOCK,
            reverse_state=True,
        ),
        BinarySensor(
            attr="trunk_closed",
            name="Trunk closed",
            device_class=VWDeviceClass.DOOR,
            reverse_state=True,
        ),
        BinarySensor(
            attr="hood_closed",
            name="Hood closed",
            device_class=VWDeviceClass.DOOR,
            reverse_state=True,
        ),
        BinarySensor(
            attr="charging_cable_connected",
            name="Charging cable connected",
            device_class=VWDeviceClass.PLUG,
            reverse_state=False,
        ),
        BinarySensor(
            attr="charging_cable_locked",
            name="Charging cable locked",
            device_class=VWDeviceClass.LOCK,
            reverse_state=True,
        ),
        BinarySensor(
            attr="sunroof_closed",
            name="Sunroof closed",
            device_class=VWDeviceClass.WINDOW,
            reverse_state=True,
        ),
        BinarySensor(
            attr="sunroof_rear_closed",
            name="Sunroof Rear closed",
            device_class=VWDeviceClass.WINDOW,
            reverse_state=True,
        ),
        BinarySensor(
            attr="roof_cover_closed",
            name="Roof cover closed",
            device_class=VWDeviceClass.WINDOW,
            reverse_state=True,
        ),
        BinarySensor(
            attr="windows_closed",
            name="Windows closed",
            device_class=VWDeviceClass.WINDOW,
            reverse_state=True,
        ),
        BinarySensor(
            attr="window_closed_left_front",
            name="Window closed left front",
            device_class=VWDeviceClass.WINDOW,
            reverse_state=True,
        ),
        BinarySensor(
            attr="window_closed_left_back",
            name="Window closed left back",
            device_class=VWDeviceClass.WINDOW,
            reverse_state=True,
        ),
        BinarySensor(
            attr="window_closed_right_front",
            name="Window closed right front",
            device_class=VWDeviceClass.WINDOW,
            reverse_state=True,
        ),
        BinarySensor(
            attr="window_closed_right_back",
            name="Window closed right back",
            device_class=VWDeviceClass.WINDOW,
            reverse_state=True,
        ),
        BinarySensor(
            attr="vehicle_moving",
            name="Vehicle Moving",
            device_class=VWDeviceClass.MOVING,
        ),
        BinarySensor(
            attr="request_in_progress",
            name="Request in progress",
            device_class=VWDeviceClass.CONNECTIVITY,
            entity_type="diag",
        ),
    ]


class Dashboard:
    """Helper for accessing the instruments."""

    def __init__(self, vehicle, **config) -> None:
        """Initialize instruments."""
        _LOGGER.debug("Setting up dashboard with config :%s", config)
        self.instruments = [
            instrument
            for instrument in create_instruments()
            if instrument.setup(vehicle, **config)
        ]
