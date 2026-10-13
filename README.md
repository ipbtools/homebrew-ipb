# ipbtools/homebrew-ipb

Homebrew tap for [ipb](https://github.com/ipbtools/ipb), the iOS Physical-device Bridge: drive a physical iPhone from a Mac the way `adb` drives an Android phone.

```sh
brew update
brew install ipbtools/ipb/ipb
ipb doctor
```

Stable installs use the pinned [v0.2.0 prebuilt archive](https://github.com/ipbtools/ipb/releases/tag/v0.2.0). Requirements: an arm64 Mac running macOS 27, compatible Xcode 27/CoreDevice development components at runtime, and an iOS 27+ device paired over USB with Developer Mode enabled. The optional `ipb ui` Python dependency is installed separately. See the ipb README for setup and verification limits.

Update a stable install with `ipb update` or `brew upgrade ipbtools/ipb/ipb`.
`brew install --HEAD ipbtools/ipb/ipb` continues to build current main from source and requires Xcode 27 for building.
To switch an existing HEAD install to stable, run `brew update`, `brew uninstall ipbtools/ipb/ipb`, then `brew install ipbtools/ipb/ipb`; `brew reinstall` retains the original install options.

## Preparing a versioned formula

After the matching `ipb` package has been reviewed with its recorded verification scope and is
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
