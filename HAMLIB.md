# Installing Hamlib

[Hamlib](https://hamlib.github.io/) is the free library that lets this CAT bridge talk to your
radio - it covers almost every brand and model on the market (Icom, Yaesu, Kenwood, Elecraft,
Ten-Tec, Flex, Elad, ...). You only need to install it **once** on the computer connected to your
radio.

## Windows

1. Go to the official Hamlib releases page:
   [github.com/Hamlib/Hamlib/releases](https://github.com/Hamlib/Hamlib/releases)
2. Download the most recent release built for Windows - look for a file whose name ends in
   something like `w64-release.zip` (or `.exe` installer if one is offered). "w64" means 64-bit
   Windows, which is what almost everyone has.
3. Extract the downloaded zip to `C:\hamlib` (right-click the zip → **Extract All...**, and choose
   `C:\` as the destination so the folder ends up at `C:\hamlib`). Extracting it there lets
   PontCAT-OP0P find it automatically - no extra setup needed.

## Debian / Ubuntu Linux

```
sudo apt install libhamlib-utils
```

## Fedora

```
sudo dnf install hamlib
```

## macOS

```
brew install hamlib
```

## Checking it worked (optional)

Open a terminal (or Command Prompt on Windows) and run:

```
rigctld --version
```

If a version number is printed, Hamlib is installed correctly and PontCAT-OP0P will find it.

---

Back to the [main guide](README.md).
