# libbox Artifacts

The Android app can run without a bundled runtime and will fall back to `MissingSingBoxRunner`.
To enable the real VPN runtime, place a pinned GPL-compatible libbox artifact here:

```text
apps/android/app/libs/libbox.aar
```

Do not commit the AAR. It is intentionally ignored because binary runtime provenance must be handled explicitly per release.

## Official Android Build

Upstream source: `https://github.com/SagerNet/sing-box`

The official sing-box Makefile exposes:

```bash
make lib_install
make lib_android
```

As of the checked upstream `testing` branch, `make lib_android` runs:

```bash
go run ./cmd/internal/build_libbox -target android
```

That builder produces:

```text
libbox.aar
libbox-legacy.aar
```

For this app, use the main `libbox.aar` and copy it to `apps/android/app/libs/libbox.aar`.

Verified local build environment:

```text
Go bootstrap: go1.22.2 with automatic go1.24.7/go1.25.11 toolchain downloads
Java: OpenJDK 17 via JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
Android SDK: /usr/lib/android-sdk
Android NDK: ndk;28.0.13004108
gomobile/gobind: github.com/sagernet/gomobile v0.1.13
```

The command used for the local verification build was:

```bash
JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64 \
ANDROID_HOME=/usr/lib/android-sdk \
PATH=/root/go/bin:$PATH \
make lib_android
```

The verified `testing` branch build at upstream commit `17852ccaaa494f664cbe90e59e2d1558c7f1db34` produced:

```text
libbox.aar        95 MB  sha256 0f8d36047b2b953eecc16b73c6e7370c393d8a53e0ebe1104c0f1e4311d956cf
libbox-legacy.aar 76 MB  sha256 8fef30c0695c47994949fd2c69d1f91130932683cfa757cddd00f8fbeadc4384
```

## Validation

From the repository root:

```bash
make libbox-android-check
python3 tools/check_libbox_artifacts.py --android --require
make android-debug
```

`make libbox-android-check` prints the SHA-256 hash when the AAR is present.
Record the selected upstream commit/tag and SHA-256 in release notes before distributing builds.

The validation checks:

- the AAR is a valid zip;
- `classes.jar` exists;
- `jni/armeabi-v7a/libbox.so`, `jni/arm64-v8a/libbox.so`, `jni/x86/libbox.so`, and `jni/x86_64/libbox.so` exist.

`apps/android/app/libs/libbox.aar` is ignored by git. Keep it local or attach it to release artifacts only after the license/distribution decision is explicit for that release.
