# ipbtools/homebrew-ipb

Homebrew tap for [ipb](https://github.com/ipbtools/ipb), the iOS Physical-device Bridge: drive a physical iPhone from a Mac the way `adb` drives an Android phone.

```sh
brew tap ipbtools/ipb
brew trust ipbtools/ipb      # Homebrew requires this for third-party taps
brew install --HEAD ipb
ipb doctor
```

Requirements: macOS 27 (or macOS 26.4+) with Xcode 27 beta installed and selected for the build; an iOS 27 or iOS 26.6+ device paired over USB. See the ipb README for details.
