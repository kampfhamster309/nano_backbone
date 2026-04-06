"""
MQTT client wrapper with Home Assistant MQTT Discovery support.

Required library in /lib/: adafruit_minimqtt/

Topic scheme:
  Discovery : homeassistant/sensor/<device_id>/<measurement>/config
  State     : homeassistant/sensor/<device_id>/<measurement>/state

All state messages are published with retain=True so Home Assistant shows
the last known value immediately after a broker restart.

Both sensor entities are grouped under a single HA device entry identified
by device_id, so the device registry shows one device with two sensors.
"""

import json
import adafruit_minimqtt.adafruit_minimqtt as mqtt

HA_DISCOVERY_PREFIX = "homeassistant"
MQTT_KEEPALIVE = 60  # seconds


def _state_topic(device_id, measurement):
    return f"{HA_DISCOVERY_PREFIX}/sensor/{device_id}/{measurement}/state"


def _config_topic(device_id, measurement):
    return f"{HA_DISCOVERY_PREFIX}/sensor/{device_id}/{measurement}/config"


def setup(pool, broker, port, user=None, password=None, device_id=None):
    """Connect to the MQTT broker and return the client.

    Parameters
    ----------
    pool : adafruit_esp32spi_socketpool.SocketPool
        Socket pool backed by the Nina W102.
    broker : str
        Hostname or IP address of the MQTT broker.
    port : int
        Broker port (typically 1883).
    user : str or None
        Optional username; pass None or empty string for anonymous access.
    password : str or None
        Optional password; ignored when *user* is absent.
    device_id : str or None
        Used as the MQTT client_id for a stable, unique connection identity.

    Returns
    -------
    adafruit_minimqtt.adafruit_minimqtt.MQTT
        Connected MQTT client; pass to publish_discovery() and
        publish_readings() on every poll cycle.
    """
    client = mqtt.MQTT(
        broker=broker,
        port=port,
        username=user or None,
        password=password or None,
        client_id=device_id,
        socket_pool=pool,
        keep_alive=MQTT_KEEPALIVE,
    )
    client.connect()
    return client


def publish_discovery(client, device_id, device_name):
    """Publish HA MQTT Discovery config payloads for temperature and humidity.

    Call once per boot, after connecting to the broker. Home Assistant will
    automatically create two sensor entities grouped under a single device
    labelled *device_name*.

    Parameters
    ----------
    client : adafruit_minimqtt.adafruit_minimqtt.MQTT
        Connected MQTT client returned by setup().
    device_id : str
        Hardware-derived unique identifier (hex of microcontroller.cpu.uid).
        Used as the MQTT topic component and HA unique_id.
    device_name : str
        Human-readable label shown in the Home Assistant UI.
    """
    device_block = {"identifiers": [device_id], "name": device_name}

    sensors = (
        {
            "measurement": "temperature",
            "name": f"{device_name} Temperature",
            "unit": "°C",
            "device_class": "temperature",
        },
        {
            "measurement": "humidity",
            "name": f"{device_name} Humidity",
            "unit": "%",
            "device_class": "humidity",
        },
    )

    for s in sensors:
        payload = json.dumps({
            "name": s["name"],
            "unique_id": f"{device_id}_{s['measurement']}",
            "state_topic": _state_topic(device_id, s["measurement"]),
            "unit_of_measurement": s["unit"],
            "device_class": s["device_class"],
            "device": device_block,
        })
        client.publish(
            _config_topic(device_id, s["measurement"]),
            payload,
            retain=True,
        )
        print(f"[mqtt] Discovery published: {s['measurement']}")


def publish_readings(client, device_id, temp, humidity):
    """Publish current temperature and humidity to their state topics.

    Reconnects automatically if the broker connection was lost.
    Never raises — a publish failure must not crash the sensor loop.

    Parameters
    ----------
    client : adafruit_minimqtt.adafruit_minimqtt.MQTT
        Connected MQTT client returned by setup().
    device_id : str
        Hardware-derived unique identifier used in topic construction.
    temp : float
        Temperature in degrees Celsius.
    humidity : float
        Relative humidity in percent.
    """
    try:
        if not client.is_connected():
            print("[mqtt] Reconnecting...")
            client.reconnect()
        client.publish(_state_topic(device_id, "temperature"), f"{temp:.1f}", retain=True)
        client.publish(_state_topic(device_id, "humidity"), f"{humidity:.1f}", retain=True)
        print(f"[mqtt] Published: T={temp:.1f} H={humidity:.1f}")
    except Exception as e:
        print("[mqtt] Publish error:", e)
