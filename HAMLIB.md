Installing Hamlib
Hamlib is the free library that lets this CAT bridge talk to your
radio - it covers almost every brand and model on the market (Icom, Yaesu, Kenwood, Elecraft,
Ten-Tec, Flex, Elad, ...). You only need to install it once on the computer connected to your
radio.
Windows
Go to the direct "latest release" link (this always points to the newest version, so you can't
accidentally pick an old one from the list):
github.com/Hamlib/Hamlib/releases/latest
Download the Windows build - look for a file whose name ends in something like
`w64-release.zip` (or `.exe` installer if one is offered). "w64" means 64-bit Windows, which is
what almost everyone has.
Extract the downloaded zip to `C:\\hamlib` (right-click the zip → Extract All..., and choose
`C:\\` as the destination so the folder ends up at `C:\\hamlib`). Extracting it there lets
PontCAT-OP0P find it automatically - no extra setup needed.
> \*\*Already have Hamlib installed and a radio model is missing from the list?\*\* You probably have
> an older version. Hamlib only adds support for brand-new radios in its newest releases (for
> example, the Yaesu FTX-1 only became supported starting with Hamlib 4.7.0). Re-download from the
> link above - PontCAT-OP0P's log window also shows which Hamlib version it detected, right under
> "modeles Hamlib charges".
Debian / Ubuntu Linux
```
sudo apt install libhamlib-utils
```
Fedora
```
sudo dnf install hamlib
```
macOS
```
brew install hamlib
```
Checking it worked (optional)
Open a terminal (or Command Prompt on Windows) and run:
```
rigctld --version
```
If a version number is printed, Hamlib is installed correctly and PontCAT-OP0P will find it.
---
Back to the main guide.
