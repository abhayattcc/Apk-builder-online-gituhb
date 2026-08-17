[app]
title = TG Video Downloader
package.name = tgdownloader
package.domain = org.tgdownloader
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 1.0.0

# Dependencies to bundle inside APK
requirements = python3,kivy,yt-dlp,requests,urllib3,certifi

# Permissions
android.permissions = INTERNET,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE

# Android architecture targets
android.archs = arm64-v8a, armeabi-v7a
android.api = 33
android.minapi = 21
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1
