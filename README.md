# OP0P DXCluster_catbridge

Local CAT bridge for the [cluster.op0p.be](https://cluster.op0p.be) DX cluster
(OP0P CC-Cluster): lets you click a frequency on the cluster - from a PC
browser, or from a phone/tablet on the same WiFi network - and have your
transceiver tune to it automatically, via Hamlib/rigctld.

## User guide

📘 Printable step-by-step guide (PDF), for anyone with no IT background:
[Guide_Tune_your_radio_with_one_click.pdf](Guide_Tune_your_radio_with_one_click.pdf)

## Downloads

See [cluster.op0p.be/releases](https://cluster.op0p.be/releases) for ready-to-use
downloads (Windows standalone `.exe`, Windows `.pyw`, or the plain `.py` script
for Linux/macOS), and [cluster.op0p.be/cat.html](https://cluster.op0p.be/cat.html)
for full setup instructions (choosing your radio model and serial port).

## Controlling the radio from a phone or tablet (same WiFi network)

By default the bridge only answers on the computer it runs on (`127.0.0.1`).
To be able to click a frequency from your phone, you first set this up once
on the computer connected to the radio:

1. Launch the bridge on that computer (the `.exe`, `.pyw`, or `.py` - see
   Downloads above) and pick your radio's brand/model and serial port, as
   usual.
2. Before clicking **Start**, tick **"Accessible from the local network
   (phone, tablet...)"** and enter a short **PIN code**.
3. Click **Start**. A popup window appears on the computer showing an
   address such as:

   ```
   http://192.168.1.XX:5005/?pin=1234
   ```

Then, on the phone or tablet:

1. Connect it to the **same WiFi network** as the computer running the
   bridge. This is required - Bluetooth does not work for this (it provides
   no IP network between the two devices), and mobile data will not reach
   the computer either.
2. Open that address in the phone's browser, **once**. A cookie then
   remembers the authorization on that device, so the PIN does not need to
   be typed again afterwards (until browser cookies are cleared).
3. From then on, the cluster page on the phone works exactly like on the
   PC: tapping a spot's frequency tunes the radio.

Without a PIN, any device on the same WiFi/home network could control the
radio through the bridge - only skip the PIN if you trust everything
connected to that network.

## Building the Windows .exe (for maintainers)

Pushing an updated `op0p_catbridge.py` to the `main` branch triggers the
GitHub Actions workflow in `.github/workflows/build.yml`, which builds
`PontCAT-OP0P.exe` on a Windows runner with PyInstaller and publishes it as
a GitHub Release. The stable download link (always the latest build) is:

```
https://github.com/<user>/<this-repo>/releases/latest/download/PontCAT-OP0P.exe
```
