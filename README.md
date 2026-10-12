# ipbtools/homebrew-ipb

Homebrew tap for [ipb](https://github.com/ipbtools/ipb), the iOS Physical-device Bridge: drive a physical iPhone from a Mac the way `adb` drives an Android phone.

```sh
brew tap ipbtools/ipb
brew trust ipbtools/ipb      # Homebrew requires this for third-party taps
brew install --HEAD ipb
ipb doctor
```

Requirements: an arm64 Mac running macOS 27 with Xcode 27 selected for builds, and an iOS 27+ device paired over USB. See the ipb README for details.

## Preparing a versioned formula

After the matching `ipb` release-candidate has passed the device gate and is
published as a standard (non-prerelease) GitHub release, a tap maintainer can run **Actions → Prepare stable Homebrew
formula → Run workflow** with its exact `vX.Y.Z` tag. The workflow checks the
published release state, tag and mainline commit, build metadata, every packaged
file hash, the archive checksum, and the versioned formula URL and checksum. It
then installs and tests that formula on a disposable macOS 27 arm64 runner.

On success it pushes only `Formula/ipb.rb` to a new
`codex/release-vX.Y.Z` branch and prints a compare link. Review and merge that
change manually. The workflow does not create a pull request or update `main`;
stable installs continue to use the tap's default branch, and
`brew install --HEAD ipb` remains available during candidate validation.

The workflow needs only this repository's `GITHUB_TOKEN` with `contents: write`.
It never creates or approves pull requests, and it fails rather than replacing
an existing version branch.
