# Pixels Dice Home Assistant Integration

This custom component integrates Pixels Dice with Home Assistant, allowing you to monitor their roll states and manage their connection.

## Features

*   **Sensor Entity:** Provides a sensor that updates with the current roll state of your Pixels Dice (e.g., "Landed: 1", "Rolling", "Handling").
*   **Presence Binary Sensor:** Indicates when the dice is advertising over Bluetooth. It turns `on` when detected nearby and `off` when out of range.
*   **Autoconnect Switch:** A switch entity that allows you to control whether Home Assistant should automatically connect to the die when it's detected.
*   **Connect/Disconnect Services:** Offers Home Assistant services to manually connect to and disconnect from your Pixels Dice, helping to conserve battery life.

## Installation (HACS)

To install this integration via HACS (Home Assistant Community Store), follow these steps:

1.  **Add this repository to HACS:**
    Open HACS in your Home Assistant instance, go to "Integrations", click on the three dots in the top right corner, and select "Custom repositories".
    *   **Repository URL:** `https://github.com/jaxzin/gamewithpixels-ha`
    *   **Category:** `Integration`

2.  **Install the integration:**
    Once the repository is added, search for "Pixels Dice" in HACS and install it.

3.  **Restart Home Assistant.**

Alternatively, you can use the HACS button below:

[![Open your Home Assistant instance and open a repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=jaxzin&repository=gamewithpixels-ha&category=integration)

## Manual Installation

1.  Copy the `pixels_dice` folder from this repository into your Home Assistant's `custom_components` directory.

    ```bash
    # Example: If your Home Assistant config directory is /config
    cp -r custom_components/pixels_dice /config/custom_components/
    ```

2.  Restart Home Assistant.

## Configuration

Add the following to your `configuration.yaml` file:

```yaml
pixels_dice:
  name: "Brian PD6" # Replace with the actual name of your Pixels die
```

## Autoconnect Switch

This integration creates a switch entity for each Pixels die, named something like `switch.brian_pd6_autoconnect`. This switch controls whether Home Assistant will automatically connect to the die when it comes into Bluetooth range.

When **Autoconnect** is turned **on**:
- Home Assistant will actively listen for the die's Bluetooth advertisements.
- As soon as the die is detected, Home Assistant will establish a connection.
- This is useful for instantly capturing roll data but may consume more battery.

When **Autoconnect** is turned **off**:
- Home Assistant will still detect the die's presence, but it will not automatically connect.
- You can still manually connect to the die using the `pixels_dice.connect` service.
- This is the recommended mode for conserving the die's battery life.

## Services

This integration provides the following services:

### `pixels_dice.connect`

Connects to the specified Pixels Dice.

**Service Data (YAML):**

```yaml
entity_id: sensor.pixels_dice_brian_pd6 # Replace with your sensor's entity ID
```

## Presence Sensor

The integration creates a binary sensor named after your die, such as `Brian PD6 Presence`.
The sensor is `on` while Bluetooth advertisements from the die are detected and
turns `off` once those advertisements stop.

### `pixels_dice.disconnect`

Disconnects from the specified Pixels Dice.

**Service Data (YAML):**

```yaml
entity_id: sensor.pixels_dice_brian_pd6 # Replace with your sensor's entity ID
```
