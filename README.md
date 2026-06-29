# TexRex
Display a TX/RX indicator source in OBS with TrackAudio (for VATSIM ATC).

My own indicator images are included in `./img`, which you can add directly into OBS as Image Sources. Feel free to use your own instead; TexRex simply triggers a named source.

This was created by me for my Twitch streams. Have a look if you're so inclined; and all else that I make for the Internet can be found below:
- [BasicService on FlightSim.asia](https://flightsim.asia/u/basicservice)
- [flts.im/basicservice](https://flts.im/basicservice)
- [BasicService on Twitch](https://twitch.tv/basicservice)

If you end up using this for your streams/videos, I would love it if you included any of the above 3 links. Thank you! 💖 
This repo is made available under a GNU GPLv3 licence. See `LICENSE` for details.

## How To
Requirements:
1. Python
2. OBS with websocket server enabled. (In OBS, open Tools -> Websockets)
3. TrackAudio (necessary for the RX indicator to work. You may use TexRex with any other AFV client, but you will only have the TX/PTT indicator).

Steps:
1. Download the source / Clone this repo
2. In terminal, run `pip install websockets obsws-python pynput` to install the required Python libraries.
3. Configure `config.json` as required – see below.
4. In terminal, run `python main.py` and voila.


## Must Configure
You **must** configure these settings if you want the program to work.
* `obs_scene_name` This must be an exact match to the OBS Scene you want to manipulate. The default, 'EuroScope 1 ASD', is an illustrative example of my setup.
* `obs_tx_source` As above – The exact name of the OBS Source you want to be triggered by your PTT. __Must__ be within the `OBS_SCENE`.
* `obs_rx_source` As above – The exact name of the OBS Source you want to be triggered by TrackAudio RX. __Must__ be within the `OBS_SCENE`. 
* `ptt_key` Your TrackAudio PTT key. Default is `ctrl_l` (left control).

## The Rest
These settings can probably be left on default, unless you need to change them.
* `trackaudio_ws` Only change this if your TrackAudio isn't running on localhost, or is using a different port for some reason.
* `obs_host` If you're running OBS locally, leave as is; otherwise set the IP address here.
* `obs_port` OBS websocket port. Default is `4455`. If you don't know, leave as-is. You can check in OBS, Tools -> Websockets.
* `obs_password` If your OBS websocket server has auth enabled, paste the password in here.
* `obs_reconnect_interval` Interval for retrying a lost connection to OBS.

## Run On Startup
To have the script start automatically with Windows, create a `.bat` file containing:
```bat
pythonw "C:\path\to\main.py"
```
Then place a shortcut to that `.bat` file in your Windows Startup folder (`Win+R` -> `shell:startup`).

## What It Looks Like
```json
{
  "ptt_key": "ctrl_l",
  "obs_tx_source": "TX Indicator",
  "obs_rx_source": "RX Indicator",
  "obs_scene_name": "EuroScope 1 ASD",
  "obs_host": "localhost",
  "obs_port": 4455,
  "obs_password": "",
  "trackaudio_ws": "ws://127.0.0.1:49080/ws",
  "obs_reconnect_interval": 5
}

```
