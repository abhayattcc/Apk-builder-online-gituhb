#!/usr/bin/env bash
# One-click: creates the Android project, pushes to GitHub, builds the APK with GitHub Actions, downloads it.
# Needs: git + GitHub CLI (gh).  Usage: bash create-video-editor.sh [repo-name]
set -euo pipefail
REPO="${1:-video-editor-app}"

command -v git >/dev/null || { echo "Install git first"; exit 1; }
command -v gh  >/dev/null || { echo "Install GitHub CLI first: https://cli.github.com"; exit 1; }
gh auth status >/dev/null 2>&1 || gh auth login -w -p https

mkdir -p "$REPO" && cd "$REPO"
mkdir -p app/src/main/java/com/example/videoeditor app/src/main/res/layout .github/workflows

cat > settings.gradle <<'EOF'
pluginManagement {
    repositories { google(); mavenCentral(); gradlePluginPortal() }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories { google(); mavenCentral() }
}
rootProject.name = "VideoEditor"
include ':app'
EOF

cat > build.gradle <<'EOF'
plugins {
    id 'com.android.application' version '8.7.3' apply false
}
EOF

cat > gradle.properties <<'EOF'
org.gradle.jvmargs=-Xmx3g -Dfile.encoding=UTF-8
android.useAndroidX=true
android.nonTransitiveRClass=true
EOF

cat > app/build.gradle <<'EOF'
plugins { id 'com.android.application' }

android {
    namespace 'com.example.videoeditor'
    compileSdk 35
    defaultConfig {
        applicationId 'com.example.videoeditor'
        minSdk 29
        targetSdk 35
        versionCode 1
        versionName '1.0'
    }
    compileOptions {
        sourceCompatibility JavaVersion.VERSION_17
        targetCompatibility JavaVersion.VERSION_17
    }
    lint { abortOnError false; disable += 'UnsafeOptInUsageError' }
}

dependencies {
    def media3 = '1.5.1'
    implementation "androidx.media3:media3-common:$media3"
    implementation "androidx.media3:media3-exoplayer:$media3"
    implementation "androidx.media3:media3-transformer:$media3"
    implementation "androidx.media3:media3-effect:$media3"
}
EOF

cat > app/src/main/AndroidManifest.xml <<'EOF'
<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <application
        android:label="Video Editor"
        android:largeHeap="true"
        android:theme="@android:style/Theme.DeviceDefault.NoActionBar">
        <activity
            android:name=".MainActivity"
            android:exported="true"
            android:configChanges="orientation|screenSize|keyboardHidden"
            android:screenOrientation="portrait">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>
</manifest>
EOF

cat > .github/workflows/build.yml <<'EOF'
name: Build APK
on:
  push:
    branches: [ main ]
  workflow_dispatch:
permissions:
  contents: write
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-java@v4
        with:
          distribution: temurin
          java-version: 17
      - uses: gradle/actions/setup-gradle@v4
        with:
          gradle-version: 8.9
      - name: Build debug APK
        run: gradle assembleDebug --no-daemon --stacktrace
      - name: Rename APK
        run: cp app/build/outputs/apk/debug/app-debug.apk VideoEditor.apk
      - uses: actions/upload-artifact@v4
        with:
          name: VideoEditor-apk
          path: VideoEditor.apk
      - name: Publish release
        uses: softprops/action-gh-release@v2
        with:
          tag_name: build-${{ github.run_number }}
          name: Video Editor build ${{ github.run_number }}
          files: VideoEditor.apk
EOF

cat > .gitignore <<'EOF'
.gradle/
build/
local.properties
.idea/
*.iml
EOF

cat > app/src/main/res/layout/main.xml <<'EOF_MAIN_XML'
<?xml version="1.0" encoding="utf-8"?>
<!-- res/layout/main.xml -->
<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="match_parent"
    android:layout_height="match_parent"
    android:background="#121212"
    android:fitsSystemWindows="true"
    android:orientation="vertical">

    <!-- ===== TOP BAR ===== -->
    <LinearLayout
        android:layout_width="match_parent"
        android:layout_height="48dp"
        android:gravity="center_vertical"
        android:orientation="horizontal"
        android:paddingStart="6dp"
        android:paddingEnd="6dp">

        <Button
            android:id="@+id/btnUndo"
            style="?android:attr/buttonBarButtonStyle"
            android:layout_width="40dp"
            android:layout_height="wrap_content"
            android:minWidth="0dp"
            android:text="↶"
            android:textColor="#FFFFFF"
            android:textSize="20sp" />

        <Button
            android:id="@+id/btnRedo"
            style="?android:attr/buttonBarButtonStyle"
            android:layout_width="40dp"
            android:layout_height="wrap_content"
            android:minWidth="0dp"
            android:text="↷"
            android:textColor="#FFFFFF"
            android:textSize="20sp" />

        <Spinner
            android:id="@+id/spinRatio"
            android:layout_width="0dp"
            android:layout_height="wrap_content"
            android:layout_weight="1" />

        <Switch
            android:id="@+id/swFill"
            android:layout_width="wrap_content"
            android:layout_height="wrap_content"
            android:text="Fill "
            android:textColor="#CCCCCC"
            android:textSize="12sp" />

        <Button
            android:id="@+id/btnExport"
            android:layout_width="wrap_content"
            android:layout_height="40dp"
            android:layout_marginStart="8dp"
            android:backgroundTint="#3D5AFE"
            android:text="Export"
            android:textColor="#FFFFFF" />
    </LinearLayout>

    <!-- ===== PREVIEW ===== -->
    <FrameLayout
        android:id="@+id/previewFrame"
        android:layout_width="match_parent"
        android:layout_height="0dp"
        android:layout_weight="3"
        android:background="#000000">

        <SurfaceView
            android:id="@+id/previewSurface"
            android:layout_width="match_parent"
            android:layout_height="match_parent"
            android:layout_gravity="center" />

        <TextView
            android:id="@+id/txtEmpty"
            android:layout_width="wrap_content"
            android:layout_height="wrap_content"
            android:layout_gravity="center"
            android:gravity="center"
            android:text="Tap “🎬 Video” to add your first clip"
            android:textColor="#888888"
            android:textSize="14sp" />
    </FrameLayout>

    <!-- ===== PLAYBACK BAR ===== -->
    <LinearLayout
        android:layout_width="match_parent"
        android:layout_height="40dp"
        android:gravity="center_vertical"
        android:orientation="horizontal"
        android:paddingStart="6dp"
        android:paddingEnd="10dp">

        <Button
            android:id="@+id/btnPlay"
            style="?android:attr/buttonBarButtonStyle"
            android:layout_width="44dp"
            android:layout_height="wrap_content"
            android:minWidth="0dp"
            android:text="▶"
            android:textColor="#FFFFFF"
            android:textSize="18sp" />

        <SeekBar
            android:id="@+id/seekPlay"
            android:layout_width="0dp"
            android:layout_height="wrap_content"
            android:layout_weight="1"
            android:max="1000" />

        <TextView
            android:id="@+id/txtTime"
            android:layout_width="wrap_content"
            android:layout_height="wrap_content"
            android:layout_marginStart="6dp"
            android:text="00:00.0 / 00:00.0"
            android:textColor="#CCCCCC"
            android:textSize="11sp" />
    </LinearLayout>

    <!-- ===== TIMELINE (4 tracks) ===== -->
    <ScrollView
        android:layout_width="match_parent"
        android:layout_height="132dp"
        android:background="#1B1B1B">

        <LinearLayout
            android:layout_width="match_parent"
            android:layout_height="wrap_content"
            android:orientation="vertical">

            <LinearLayout
                android:layout_width="match_parent"
                android:layout_height="52dp"
                android:orientation="horizontal">

                <TextView
                    android:layout_width="44dp"
                    android:layout_height="match_parent"
                    android:gravity="center"
                    android:text="VIDEO"
                    android:textColor="#888888"
                    android:textSize="9sp" />

                <HorizontalScrollView
                    android:layout_width="match_parent"
                    android:layout_height="match_parent"
                    android:scrollbars="none">

                    <LinearLayout
                        android:id="@+id/trackMain"
                        android:layout_width="wrap_content"
                        android:layout_height="match_parent"
                        android:orientation="horizontal" />
                </HorizontalScrollView>
            </LinearLayout>

            <LinearLayout
                android:layout_width="match_parent"
                android:layout_height="52dp"
                android:orientation="horizontal">

                <TextView
                    android:layout_width="44dp"
                    android:layout_height="match_parent"
                    android:gravity="center"
                    android:text="LAYERS"
                    android:textColor="#888888"
                    android:textSize="9sp" />

                <HorizontalScrollView
                    android:layout_width="match_parent"
                    android:layout_height="match_parent"
                    android:scrollbars="none">

                    <LinearLayout
                        android:id="@+id/trackOver"
                        android:layout_width="wrap_content"
                        android:layout_height="match_parent"
                        android:orientation="horizontal" />
                </HorizontalScrollView>
            </LinearLayout>

            <LinearLayout
                android:layout_width="match_parent"
                android:layout_height="52dp"
                android:orientation="horizontal">

                <TextView
                    android:layout_width="44dp"
                    android:layout_height="match_parent"
                    android:gravity="center"
                    android:text="TEXT"
                    android:textColor="#888888"
                    android:textSize="9sp" />

                <HorizontalScrollView
                    android:layout_width="match_parent"
                    android:layout_height="match_parent"
                    android:scrollbars="none">

                    <LinearLayout
                        android:id="@+id/trackText"
                        android:layout_width="wrap_content"
                        android:layout_height="match_parent"
                        android:orientation="horizontal" />
                </HorizontalScrollView>
            </LinearLayout>

            <LinearLayout
                android:layout_width="match_parent"
                android:layout_height="52dp"
                android:orientation="horizontal">

                <TextView
                    android:layout_width="44dp"
                    android:layout_height="match_parent"
                    android:gravity="center"
                    android:text="AUDIO"
                    android:textColor="#888888"
                    android:textSize="9sp" />

                <HorizontalScrollView
                    android:layout_width="match_parent"
                    android:layout_height="match_parent"
                    android:scrollbars="none">

                    <LinearLayout
                        android:id="@+id/trackAudio"
                        android:layout_width="wrap_content"
                        android:layout_height="match_parent"
                        android:orientation="horizontal" />
                </HorizontalScrollView>
            </LinearLayout>
        </LinearLayout>
    </ScrollView>

    <!-- ===== ACTION BAR ===== -->
    <HorizontalScrollView
        android:layout_width="match_parent"
        android:layout_height="44dp"
        android:background="#222222"
        android:scrollbars="none">

        <LinearLayout
            android:layout_width="wrap_content"
            android:layout_height="match_parent"
            android:orientation="horizontal">

            <Button android:id="@+id/btnAddVideo" style="?android:attr/buttonBarButtonStyle" android:layout_width="wrap_content" android:layout_height="match_parent" android:minWidth="0dp" android:text="🎬 Video" android:textColor="#FFFFFF" android:textSize="12sp" />
            <Button android:id="@+id/btnAddOverlay" style="?android:attr/buttonBarButtonStyle" android:layout_width="wrap_content" android:layout_height="match_parent" android:minWidth="0dp" android:text="🖼 Layer" android:textColor="#FFFFFF" android:textSize="12sp" />
            <Button android:id="@+id/btnAddAudio" style="?android:attr/buttonBarButtonStyle" android:layout_width="wrap_content" android:layout_height="match_parent" android:minWidth="0dp" android:text="🎵 Audio" android:textColor="#FFFFFF" android:textSize="12sp" />
            <Button android:id="@+id/btnAddText" style="?android:attr/buttonBarButtonStyle" android:layout_width="wrap_content" android:layout_height="match_parent" android:minWidth="0dp" android:text="🅣 Text" android:textColor="#FFFFFF" android:textSize="12sp" />
            <Button android:id="@+id/btnSplit" style="?android:attr/buttonBarButtonStyle" android:layout_width="wrap_content" android:layout_height="match_parent" android:minWidth="0dp" android:text="✂ Split" android:textColor="#FFFFFF" android:textSize="12sp" />
            <Button android:id="@+id/btnDuplicate" style="?android:attr/buttonBarButtonStyle" android:layout_width="wrap_content" android:layout_height="match_parent" android:minWidth="0dp" android:text="⧉ Copy" android:textColor="#FFFFFF" android:textSize="12sp" />
            <Button android:id="@+id/btnMoveLeft" style="?android:attr/buttonBarButtonStyle" android:layout_width="wrap_content" android:layout_height="match_parent" android:minWidth="0dp" android:text="◀" android:textColor="#FFFFFF" android:textSize="12sp" />
            <Button android:id="@+id/btnMoveRight" style="?android:attr/buttonBarButtonStyle" android:layout_width="wrap_content" android:layout_height="match_parent" android:minWidth="0dp" android:text="▶" android:textColor="#FFFFFF" android:textSize="12sp" />
            <Button android:id="@+id/btnDelete" style="?android:attr/buttonBarButtonStyle" android:layout_width="wrap_content" android:layout_height="match_parent" android:minWidth="0dp" android:text="🗑 Delete" android:textColor="#FF6E6E" android:textSize="12sp" />
        </LinearLayout>
    </HorizontalScrollView>

    <!-- ===== TOOLS PANEL ===== -->
    <ScrollView
        android:layout_width="match_parent"
        android:layout_height="0dp"
        android:layout_weight="2.2"
        android:background="#181818">

        <LinearLayout
            android:layout_width="match_parent"
            android:layout_height="wrap_content"
            android:orientation="vertical"
            android:padding="10dp">

            <TextView
                android:id="@+id/txtSelected"
                android:layout_width="match_parent"
                android:layout_height="wrap_content"
                android:text="Select a clip on the timeline to edit it"
                android:textColor="#FFFFFF"
                android:textSize="13sp"
                android:textStyle="bold" />

            <!-- TRIM -->
            <LinearLayout android:id="@+id/secTrim" android:layout_width="match_parent" android:layout_height="wrap_content" android:orientation="vertical" android:visibility="gone">
                <TextView android:id="@+id/txtTrim" android:layout_width="match_parent" android:layout_height="wrap_content" android:layout_marginTop="8dp" android:text="Trim" android:textColor="#BBBBBB" android:textSize="12sp" />
                <SeekBar android:id="@+id/seekTrimStart" android:layout_width="match_parent" android:layout_height="wrap_content" android:max="1000" />
                <SeekBar android:id="@+id/seekTrimEnd" android:layout_width="match_parent" android:layout_height="wrap_content" android:max="1000" />
            </LinearLayout>

            <!-- DURATION (image/text) -->
            <LinearLayout android:id="@+id/secDuration" android:layout_width="match_parent" android:layout_height="wrap_content" android:orientation="vertical" android:visibility="gone">
                <TextView android:id="@+id/txtDuration" android:layout_width="match_parent" android:layout_height="wrap_content" android:layout_marginTop="8dp" android:text="Duration" android:textColor="#BBBBBB" android:textSize="12sp" />
                <SeekBar android:id="@+id/seekDuration" android:layout_width="match_parent" android:layout_height="wrap_content" android:max="300" />
            </LinearLayout>

            <!-- START OFFSET -->
            <LinearLayout android:id="@+id/secOffset" android:layout_width="match_parent" android:layout_height="wrap_content" android:orientation="vertical" android:visibility="gone">
                <TextView android:id="@+id/txtOffset" android:layout_width="match_parent" android:layout_height="wrap_content" android:layout_marginTop="8dp" android:text="Starts at" android:textColor="#BBBBBB" android:textSize="12sp" />
                <SeekBar android:id="@+id/seekOffset" android:layout_width="match_parent" android:layout_height="wrap_content" android:max="1800" />
            </LinearLayout>

            <!-- SPEED -->
            <LinearLayout android:id="@+id/secSpeed" android:layout_width="match_parent" android:layout_height="wrap_content" android:orientation="vertical" android:visibility="gone">
                <TextView android:id="@+id/txtSpeed" android:layout_width="match_parent" android:layout_height="wrap_content" android:layout_marginTop="8dp" android:text="Speed 1.0x" android:textColor="#BBBBBB" android:textSize="12sp" />
                <SeekBar android:id="@+id/seekSpeed" android:layout_width="match_parent" android:layout_height="wrap_content" android:max="75" />
            </LinearLayout>

            <!-- VOLUME -->
            <LinearLayout android:id="@+id/secVolume" android:layout_width="match_parent" android:layout_height="wrap_content" android:orientation="vertical" android:visibility="gone">
                <TextView android:id="@+id/txtVolume" android:layout_width="match_parent" android:layout_height="wrap_content" android:layout_marginTop="8dp" android:text="Volume 100%" android:textColor="#BBBBBB" android:textSize="12sp" />
                <SeekBar android:id="@+id/seekVolume" android:layout_width="match_parent" android:layout_height="wrap_content" android:max="200" />
            </LinearLayout>

            <!-- ROTATE / FLIP -->
            <LinearLayout android:id="@+id/secRotate" android:layout_width="match_parent" android:layout_height="wrap_content" android:orientation="horizontal" android:layout_marginTop="8dp" android:visibility="gone">
                <Button android:id="@+id/btnRotate" android:layout_width="0dp" android:layout_height="wrap_content" android:layout_weight="1" android:text="⟳ Rotate 90°" android:textSize="12sp" />
                <Button android:id="@+id/btnFlipH" android:layout_width="0dp" android:layout_height="wrap_content" android:layout_weight="1" android:text="⇋ Flip H" android:textSize="12sp" />
                <Button android:id="@+id/btnFlipV" android:layout_width="0dp" android:layout_height="wrap_content" android:layout_weight="1" android:text="⇅ Flip V" android:textSize="12sp" />
            </LinearLayout>

            <!-- LAYER TRANSFORM -->
            <LinearLayout android:id="@+id/secTransform" android:layout_width="match_parent" android:layout_height="wrap_content" android:orientation="vertical" android:visibility="gone">
                <TextView android:id="@+id/txtScale" android:layout_width="match_parent" android:layout_height="wrap_content" android:layout_marginTop="8dp" android:text="Layer size 100%" android:textColor="#BBBBBB" android:textSize="12sp" />
                <SeekBar android:id="@+id/seekScale" android:layout_width="match_parent" android:layout_height="wrap_content" android:max="300" />
                <TextView android:layout_width="match_parent" android:layout_height="wrap_content" android:text="Position X" android:textColor="#BBBBBB" android:textSize="12sp" />
                <SeekBar android:id="@+id/seekPosX" android:layout_width="match_parent" android:layout_height="wrap_content" android:max="200" />
                <TextView android:layout_width="match_parent" android:layout_height="wrap_content" android:text="Position Y" android:textColor="#BBBBBB" android:textSize="12sp" />
                <SeekBar android:id="@+id/seekPosY" android:layout_width="match_parent" android:layout_height="wrap_content" android:max="200" />
                <TextView android:id="@+id/txtOpacity" android:layout_width="match_parent" android:layout_height="wrap_content" android:text="Opacity 100%" android:textColor="#BBBBBB" android:textSize="12sp" />
                <SeekBar android:id="@+id/seekOpacity" android:layout_width="match_parent" android:layout_height="wrap_content" android:max="100" />
            </LinearLayout>

            <!-- COLOR ADJUST + FILTER -->
            <LinearLayout android:id="@+id/secAdjust" android:layout_width="match_parent" android:layout_height="wrap_content" android:orientation="vertical" android:visibility="gone">
                <TextView android:layout_width="match_parent" android:layout_height="wrap_content" android:layout_marginTop="8dp" android:text="Filter" android:textColor="#BBBBBB" android:textSize="12sp" />
                <Spinner android:id="@+id/spinFilter" android:layout_width="match_parent" android:layout_height="wrap_content" />
                <TextView android:layout_width="match_parent" android:layout_height="wrap_content" android:text="Brightness" android:textColor="#BBBBBB" android:textSize="12sp" />
                <SeekBar android:id="@+id/seekBright" android:layout_width="match_parent" android:layout_height="wrap_content" android:max="200" />
                <TextView android:layout_width="match_parent" android:layout_height="wrap_content" android:text="Contrast" android:textColor="#BBBBBB" android:textSize="12sp" />
                <SeekBar android:id="@+id/seekContrast" android:layout_width="match_parent" android:layout_height="wrap_content" android:max="200" />
                <TextView android:layout_width="match_parent" android:layout_height="wrap_content" android:text="Saturation" android:textColor="#BBBBBB" android:textSize="12sp" />
                <SeekBar android:id="@+id/seekSat" android:layout_width="match_parent" android:layout_height="wrap_content" android:max="200" />
            </LinearLayout>

            <!-- CHROMA KEY -->
            <LinearLayout android:id="@+id/secChroma" android:layout_width="match_parent" android:layout_height="wrap_content" android:orientation="vertical" android:visibility="gone">
                <Switch android:id="@+id/swChroma" android:layout_width="match_parent" android:layout_height="wrap_content" android:layout_marginTop="10dp" android:text="Chroma key (green / blue screen)" android:textColor="#FFFFFF" android:textSize="13sp" />
                <LinearLayout android:layout_width="match_parent" android:layout_height="wrap_content" android:gravity="center_vertical" android:orientation="horizontal">
                    <View android:id="@+id/viewKey" android:layout_width="28dp" android:layout_height="28dp" android:layout_marginEnd="8dp" android:background="#00B140" />
                    <Button android:id="@+id/btnKeyGreen" android:layout_width="0dp" android:layout_height="wrap_content" android:layout_weight="1" android:text="Green" android:textSize="12sp" />
                    <Button android:id="@+id/btnKeyBlue" android:layout_width="0dp" android:layout_height="wrap_content" android:layout_weight="1" android:text="Blue" android:textSize="12sp" />
                    <Button android:id="@+id/btnEyedrop" android:layout_width="0dp" android:layout_height="wrap_content" android:layout_weight="1.3" android:text="💧 Pick" android:textSize="12sp" />
                </LinearLayout>
                <TextView android:id="@+id/txtSim" android:layout_width="match_parent" android:layout_height="wrap_content" android:text="Similarity" android:textColor="#BBBBBB" android:textSize="12sp" />
                <SeekBar android:id="@+id/seekSim" android:layout_width="match_parent" android:layout_height="wrap_content" android:max="100" />
                <TextView android:id="@+id/txtSmooth" android:layout_width="match_parent" android:layout_height="wrap_content" android:text="Edge smoothness" android:textColor="#BBBBBB" android:textSize="12sp" />
                <SeekBar android:id="@+id/seekSmooth" android:layout_width="match_parent" android:layout_height="wrap_content" android:max="100" />
                <TextView android:id="@+id/txtSpill" android:layout_width="match_parent" android:layout_height="wrap_content" android:text="Spill suppression" android:textColor="#BBBBBB" android:textSize="12sp" />
                <SeekBar android:id="@+id/seekSpill" android:layout_width="match_parent" android:layout_height="wrap_content" android:max="100" />
            </LinearLayout>

            <!-- TEXT -->
            <LinearLayout android:id="@+id/secText" android:layout_width="match_parent" android:layout_height="wrap_content" android:orientation="vertical" android:visibility="gone">
                <EditText android:id="@+id/edtText" android:layout_width="match_parent" android:layout_height="wrap_content" android:layout_marginTop="8dp" android:hint="Type your text" android:inputType="textMultiLine" android:textColor="#FFFFFF" android:textColorHint="#777777" />
                <Button android:id="@+id/btnTextColor" android:layout_width="match_parent" android:layout_height="wrap_content" android:text="Change text colour" android:textSize="12sp" />
                <TextView android:layout_width="match_parent" android:layout_height="wrap_content" android:text="Text size" android:textColor="#BBBBBB" android:textSize="12sp" />
                <SeekBar android:id="@+id/seekTextSize" android:layout_width="match_parent" android:layout_height="wrap_content" android:max="200" />
            </LinearLayout>
        </LinearLayout>
    </ScrollView>

    <!-- ===== EXPORT PANEL (hidden until Export is tapped) ===== -->
    <LinearLayout
        android:id="@+id/panelExport"
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:background="#262626"
        android:orientation="vertical"
        android:padding="10dp"
        android:visibility="gone">

        <TextView android:layout_width="match_parent" android:layout_height="wrap_content" android:text="Export settings" android:textColor="#FFFFFF" android:textSize="14sp" android:textStyle="bold" />

        <LinearLayout android:layout_width="match_parent" android:layout_height="wrap_content" android:orientation="horizontal">
            <Spinner android:id="@+id/spinRes" android:layout_width="0dp" android:layout_height="wrap_content" android:layout_weight="1" />
            <Spinner android:id="@+id/spinFps" android:layout_width="0dp" android:layout_height="wrap_content" android:layout_weight="1" />
        </LinearLayout>
        <LinearLayout android:layout_width="match_parent" android:layout_height="wrap_content" android:orientation="horizontal">
            <Spinner android:id="@+id/spinCodec" android:layout_width="0dp" android:layout_height="wrap_content" android:layout_weight="1" />
            <Spinner android:id="@+id/spinQuality" android:layout_width="0dp" android:layout_height="wrap_content" android:layout_weight="1" />
        </LinearLayout>

        <ProgressBar
            android:id="@+id/progressExport"
            style="?android:attr/progressBarStyleHorizontal"
            android:layout_width="match_parent"
            android:layout_height="wrap_content"
            android:max="100"
            android:visibility="gone" />

        <TextView android:id="@+id/txtExportStatus" android:layout_width="match_parent" android:layout_height="wrap_content" android:textColor="#BBBBBB" android:textSize="12sp" />

        <LinearLayout android:layout_width="match_parent" android:layout_height="wrap_content" android:orientation="horizontal">
            <Button android:id="@+id/btnStartExport" android:layout_width="0dp" android:layout_height="wrap_content" android:layout_weight="1" android:backgroundTint="#3D5AFE" android:text="Start export" android:textColor="#FFFFFF" />
            <Button android:id="@+id/btnCancelExport" android:layout_width="0dp" android:layout_height="wrap_content" android:layout_weight="1" android:text="Cancel / Close" />
        </LinearLayout>
    </LinearLayout>
</LinearLayout>
EOF_MAIN_XML

cat > app/src/main/java/com/example/videoeditor/MainActivity.java <<'EOF_MAIN_JAVA'
package com.example.videoeditor;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.ContentValues;
import android.content.Intent;
import android.database.Cursor;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Rect;
import android.graphics.Typeface;
import android.media.MediaCodecInfo;
import android.media.MediaCodecList;
import android.media.MediaMetadataRetriever;
import android.net.Uri;
import android.opengl.GLES20;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.provider.MediaStore;
import android.provider.OpenableColumns;
import android.text.Layout;
import android.text.StaticLayout;
import android.text.TextPaint;
import android.view.Gravity;
import android.view.MotionEvent;
import android.view.SurfaceHolder;
import android.view.SurfaceView;
import android.view.View;
import android.view.PixelCopy;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.widget.ArrayAdapter;
import android.widget.AdapterView;
import android.widget.Button;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.SeekBar;
import android.widget.Spinner;
import android.widget.Switch;
import android.widget.TextView;
import android.widget.Toast;

import androidx.annotation.OptIn;
import androidx.media3.common.C;
import androidx.media3.common.Effect;
import androidx.media3.common.MediaItem;
import androidx.media3.common.MimeTypes;
import androidx.media3.common.PlaybackException;
import androidx.media3.common.Player;
import androidx.media3.common.VideoCompositorSettings;
import androidx.media3.common.VideoFrameProcessingException;
import androidx.media3.common.audio.AudioProcessor;
import androidx.media3.common.audio.ChannelMixingAudioProcessor;
import androidx.media3.common.audio.ChannelMixingMatrix;
import androidx.media3.common.audio.SonicAudioProcessor;
import androidx.media3.common.util.GlProgram;
import androidx.media3.common.util.GlUtil;
import androidx.media3.common.util.Size;
import androidx.media3.common.util.UnstableApi;
import androidx.media3.effect.BaseGlShaderProgram;
import androidx.media3.effect.BitmapOverlay;
import androidx.media3.effect.Brightness;
import androidx.media3.effect.Contrast;
import androidx.media3.effect.FrameDropEffect;
import androidx.media3.effect.GlEffect;
import androidx.media3.effect.GlShaderProgram;
import androidx.media3.effect.HslAdjustment;
import androidx.media3.effect.OverlayEffect;
import androidx.media3.effect.OverlaySettings;
import androidx.media3.effect.Presentation;
import androidx.media3.effect.RgbMatrix;
import androidx.media3.effect.ScaleAndRotateTransformation;
import androidx.media3.effect.SpeedChangeEffect;
import androidx.media3.effect.TextureOverlay;
import androidx.media3.transformer.Composition;
import androidx.media3.transformer.CompositionPlayer;
import androidx.media3.transformer.DefaultEncoderFactory;
import androidx.media3.transformer.EditedMediaItem;
import androidx.media3.transformer.EditedMediaItemSequence;
import androidx.media3.transformer.Effects;
import androidx.media3.transformer.ExportException;
import androidx.media3.transformer.ExportResult;
import androidx.media3.transformer.ProgressHolder;
import androidx.media3.transformer.Transformer;
import androidx.media3.transformer.VideoEncoderSettings;

import com.google.common.collect.ImmutableList;

import java.io.File;
import java.io.InputStream;
import java.io.OutputStream;
import java.io.FileInputStream;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Complete single-activity video editor (framework Activity, Java only).
 *
 * Features: multi-clip main track, unlimited overlay layers (video / photo) with position,
 * size, opacity, start time; chroma key (green / blue / eyedropper) with similarity, smoothness
 * and spill control; text overlays with timing; background audio tracks; trim, split, duplicate,
 * reorder, delete; speed 0.25x-4x (pitch preserved); volume; rotate / flip; brightness, contrast,
 * saturation; colour filters; canvas ratios; undo / redo; live preview; export up to 4K (H.264 / H.265)
 * saved to Movies/VideoEditor; hardware 4K encoder check.
 *
 * Built on AndroidX Media3 1.5.x (Transformer + CompositionPlayer + effects).
 */
@OptIn(markerClass = UnstableApi.class)
public class MainActivity extends Activity {

    // ------------------------------------------------------------------ constants
    private static final int T_VIDEO = 0, T_IMAGE = 1, T_AUDIO = 2, T_TEXT = 3;
    private static final int TR_MAIN = 0, TR_OVER = 1, TR_AUDIO = 2, TR_TEXT = 3;
    private static final int REQ_VIDEO = 11, REQ_OVERLAY = 12, REQ_AUDIO = 13;
    private static final int PREVIEW_SHORT_SIDE = 540;

    private static final String[] RATIO_NAMES = {"16:9", "9:16", "1:1", "4:5", "4:3"};
    private static final float[][] RATIOS = {{16, 9}, {9, 16}, {1, 1}, {4, 5}, {4, 3}};
    private static final String[] FILTERS = {"None", "Grayscale", "Sepia", "Warm", "Cool", "Vintage", "Noir"};
    private static final String[] RES_NAMES = {"720p HD", "1080p Full HD", "1440p 2K", "2160p 4K"};
    private static final int[] RES_VALUES = {720, 1080, 1440, 2160};
    private static final String[] FPS_NAMES = {"Source fps", "30 fps", "24 fps"};
    private static final String[] CODEC_NAMES = {"H.264 (compatible)", "H.265 / HEVC (smaller)"};
    private static final String[] QUALITY_NAMES = {"Standard", "High", "Maximum"};
    private static final float[] QUALITY_MULT = {0.6f, 1f, 1.5f};
    private static final float[] BASE_MBPS = {6f, 12f, 24f, 45f};
    private static final int[] TEXT_COLORS = {Color.WHITE, Color.YELLOW, Color.RED, Color.CYAN, Color.GREEN, Color.BLACK};

    // ------------------------------------------------------------------ model
    static class Clip implements Cloneable {
        int id, type, track;
        Uri uri;
        String name = "";
        long srcDurMs, trimStart, trimEnd, durMs = 4000, offsetMs;
        float speed = 1f, volume = 1f;
        int rotation;
        boolean flipH, flipV;
        float brightness, contrast, saturation = 1f;
        int filter;
        boolean chroma;
        int keyColor = 0xFF00B140;
        float sim = 0.25f, smooth = 0.10f, spill = 0.10f;
        float scale = 1f, posX, posY, opacity = 1f;
        String text = "Your text";
        int textColor = Color.WHITE, textSize = 60;
        Bitmap thumb;

        Clip copy() {
            try {
                return (Clip) super.clone();
            } catch (CloneNotSupportedException e) {
                throw new RuntimeException(e);
            }
        }
    }

    private final List<Clip> clips = new ArrayList<>();
    private final ArrayDeque<List<Clip>> undoStack = new ArrayDeque<>();
    private final ArrayDeque<List<Clip>> redoStack = new ArrayDeque<>();
    private int nextId = 1, selectedId = -1, ratioIdx = 0;
    private boolean binding = false, fillMode = false, eyedrop = false, surfaceReady = false;

    // ------------------------------------------------------------------ views / engines
    private final Handler ui = new Handler(Looper.getMainLooper());
    private final ExecutorService exec = Executors.newSingleThreadExecutor();
    private SurfaceView surface;
    private FrameLayout previewFrame;
    private TextView txtEmpty, txtTime, txtSelected, txtExportStatus;
    private SeekBar seekPlay;
    private Button btnPlay;
    private LinearLayout trackMain, trackOver, trackAudio, trackText;
    private View panelExport;
    private ProgressBar progressExport;
    private CompositionPlayer player;
    private Transformer transformer;
    private boolean exporting = false, userSeeking = false;

    // ================================================================== lifecycle
    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        setContentView(R.layout.main);

        surface = findViewById(R.id.previewSurface);
        previewFrame = findViewById(R.id.previewFrame);
        txtEmpty = findViewById(R.id.txtEmpty);
        txtTime = findViewById(R.id.txtTime);
        txtSelected = findViewById(R.id.txtSelected);
        txtExportStatus = findViewById(R.id.txtExportStatus);
        seekPlay = findViewById(R.id.seekPlay);
        btnPlay = findViewById(R.id.btnPlay);
        trackMain = findViewById(R.id.trackMain);
        trackOver = findViewById(R.id.trackOver);
        trackAudio = findViewById(R.id.trackAudio);
        trackText = findViewById(R.id.trackText);
        panelExport = findViewById(R.id.panelExport);
        progressExport = findViewById(R.id.progressExport);

        setupSurface();
        setupTopBar();
        setupPlayback();
        setupActionBar();
        setupToolControls();
        setupExportPanel();
        renderTimeline();
        bindSelectionToUi();
        ui.post(progressTicker);
    }

    @Override
    protected void onPause() {
        super.onPause();
        if (player != null) player.pause();
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        ui.removeCallbacksAndMessages(null);
        releasePlayer();
        if (transformer != null && exporting) transformer.cancel();
        exec.shutdownNow();
    }

    // ================================================================== setup: surface / top bar
    private void setupSurface() {
        surface.getHolder().addCallback(new SurfaceHolder.Callback() {
            @Override public void surfaceCreated(SurfaceHolder h) { surfaceReady = true; scheduleRefresh(); }
            @Override public void surfaceChanged(SurfaceHolder h, int f, int w, int hh) { }
            @Override public void surfaceDestroyed(SurfaceHolder h) { surfaceReady = false; releasePlayer(); }
        });
        previewFrame.addOnLayoutChangeListener((v, l, t, r, bt, ol, ot, or, ob) -> fitPreview());
        surface.setOnTouchListener((v, ev) -> {
            if (eyedrop && ev.getAction() == MotionEvent.ACTION_UP) {
                sampleColor((int) ev.getX(), (int) ev.getY());
                return true;
            }
            return eyedrop;
        });
    }

    /** Resize the SurfaceView to the canvas aspect ratio, centred in the preview area. */
    private void fitPreview() {
        int fw = previewFrame.getWidth(), fh = previewFrame.getHeight();
        if (fw == 0 || fh == 0) return;
        float ar = RATIOS[ratioIdx][0] / RATIOS[ratioIdx][1];
        int w = fw, h = Math.round(fw / ar);
        if (h > fh) { h = fh; w = Math.round(fh * ar); }
        FrameLayout.LayoutParams lp = new FrameLayout.LayoutParams(w, h, Gravity.CENTER);
        if (surface.getLayoutParams().width != w || surface.getLayoutParams().height != h) surface.setLayoutParams(lp);
    }

    private void setupTopBar() {
        findViewById(R.id.btnUndo).setOnClickListener(v -> undo());
        findViewById(R.id.btnRedo).setOnClickListener(v -> redo());
        Spinner sr = findViewById(R.id.spinRatio);
        sr.setAdapter(new ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item, RATIO_NAMES));
        sr.setOnItemSelectedListener(new SimpleSel() {
            @Override void sel(int pos) {
                if (pos != ratioIdx) { ratioIdx = pos; fitPreview(); scheduleRefresh(); }
            }
        });
        Switch fill = findViewById(R.id.swFill);
        fill.setOnCheckedChangeListener((cb, on) -> { fillMode = on; scheduleRefresh(); });
        findViewById(R.id.btnExport).setOnClickListener(v -> {
            panelExport.setVisibility(panelExport.getVisibility() == View.VISIBLE ? View.GONE : View.VISIBLE);
        });
    }

    // ================================================================== setup: playback
    private void setupPlayback() {
        btnPlay.setOnClickListener(v -> {
            if (player == null) { scheduleRefresh(); return; }
            if (player.isPlaying()) player.pause(); else player.play();
        });
        seekPlay.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
            @Override public void onProgressChanged(SeekBar s, int p, boolean fromUser) {
                if (fromUser && player != null) player.seekTo(totalMs() * p / 1000L);
            }
            @Override public void onStartTrackingTouch(SeekBar s) { userSeeking = true; }
            @Override public void onStopTrackingTouch(SeekBar s) { userSeeking = false; }
        });
    }

    private final Runnable progressTicker = new Runnable() {
        @Override public void run() {
            long total = Math.max(1, totalMs());
            if (player != null && !userSeeking) {
                long pos = Math.min(player.getCurrentPosition(), total);
                seekPlay.setProgress((int) (pos * 1000 / total));
                txtTime.setText(fmt(pos) + " / " + fmt(total));
            } else if (player == null) {
                txtTime.setText(fmt(0) + " / " + fmt(totalMs()));
            }
            if (exporting && transformer != null) {
                ProgressHolder ph = new ProgressHolder();
                int st = transformer.getProgress(ph);
                if (st != Transformer.PROGRESS_STATE_NOT_STARTED) {
                    progressExport.setProgress(ph.progress);
                    txtExportStatus.setText("Exporting… " + ph.progress + "%");
                }
            }
            ui.postDelayed(this, 250);
        }
    };

    private long playhead() { return player != null ? player.getCurrentPosition() : 0; }

    // ================================================================== setup: add / edit buttons
    private void setupActionBar() {
        findViewById(R.id.btnAddVideo).setOnClickListener(v -> pick(REQ_VIDEO, new String[]{"video/*", "image/*"}, true));
        findViewById(R.id.btnAddOverlay).setOnClickListener(v -> {
            if (!hasMain()) { toast("Add a main video first"); return; }
            pick(REQ_OVERLAY, new String[]{"video/*", "image/*"}, true);
        });
        findViewById(R.id.btnAddAudio).setOnClickListener(v -> pick(REQ_AUDIO, new String[]{"audio/*"}, true));
        findViewById(R.id.btnAddText).setOnClickListener(v -> {
            if (!hasMain()) { toast("Add a main video first"); return; }
            pushUndo();
            Clip c = new Clip();
            c.id = nextId++; c.type = T_TEXT; c.track = TR_TEXT; c.name = "Text";
            c.offsetMs = Math.min(playhead(), Math.max(0, totalMs() - 1000));
            c.durMs = 3000;
            clips.add(c);
            select(c.id);
            scheduleRefresh();
        });
        findViewById(R.id.btnSplit).setOnClickListener(v -> splitAtPlayhead());
        findViewById(R.id.btnDuplicate).setOnClickListener(v -> {
            Clip c = selected();
            if (c == null) return;
            pushUndo();
            Clip d = c.copy();
            d.id = nextId++;
            if (c.track != TR_MAIN) d.offsetMs += 500;
            clips.add(clips.indexOf(c) + 1, d);
            select(d.id);
            scheduleRefresh();
        });
        findViewById(R.id.btnDelete).setOnClickListener(v -> {
            Clip c = selected();
            if (c == null) return;
            pushUndo();
            clips.remove(c);
            selectedId = -1;
            renderTimeline(); bindSelectionToUi(); scheduleRefresh();
        });
        findViewById(R.id.btnMoveLeft).setOnClickListener(v -> moveSelected(-1));
        findViewById(R.id.btnMoveRight).setOnClickListener(v -> moveSelected(1));
    }

    private void pick(int req, String[] mimes, boolean multi) {
        Intent i = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        i.addCategory(Intent.CATEGORY_OPENABLE);
        i.setType("*/*");
        i.putExtra(Intent.EXTRA_MIME_TYPES, mimes);
        i.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, multi);
        startActivityForResult(i, req);
    }

    @Override
    protected void onActivityResult(int req, int res, Intent data) {
        super.onActivityResult(req, res, data);
        if (res != RESULT_OK || data == null) return;
        List<Uri> uris = new ArrayList<>();
        if (data.getClipData() != null) {
            for (int i = 0; i < data.getClipData().getItemCount(); i++) uris.add(data.getClipData().getItemAt(i).getUri());
        } else if (data.getData() != null) uris.add(data.getData());
        int track = req == REQ_VIDEO ? TR_MAIN : req == REQ_OVERLAY ? TR_OVER : TR_AUDIO;
        for (Uri u : uris) {
            try { getContentResolver().takePersistableUriPermission(u, Intent.FLAG_GRANT_READ_URI_PERMISSION); } catch (Exception ignored) { }
            importUri(u, track);
        }
    }

    private void importUri(Uri uri, int track) {
        exec.execute(() -> {
            Clip c = new Clip();
            c.uri = uri; c.track = track; c.name = queryName(uri);
            String mime = getContentResolver().getType(uri);
            try {
                if (mime != null && mime.startsWith("image/")) {
                    c.type = T_IMAGE; c.durMs = 4000;
                    c.thumb = decodeThumb(uri);
                } else {
                    MediaMetadataRetriever r = new MediaMetadataRetriever();
                    r.setDataSource(this, uri);
                    String d = r.extractMetadata(MediaMetadataRetriever.METADATA_KEY_DURATION);
                    c.srcDurMs = d == null ? 5000 : Long.parseLong(d);
                    boolean isAudio = (mime != null && mime.startsWith("audio/"))
                            || "yes".equals(r.extractMetadata(MediaMetadataRetriever.METADATA_KEY_HAS_AUDIO)) && r.extractMetadata(MediaMetadataRetriever.METADATA_KEY_HAS_VIDEO) == null;
                    c.type = isAudio ? T_AUDIO : T_VIDEO;
                    if (!isAudio) c.thumb = r.getScaledFrameAtTime(0, MediaMetadataRetriever.OPTION_CLOSEST_SYNC, 160, 160);
                    c.trimStart = 0; c.trimEnd = c.srcDurMs;
                    r.release();
                }
            } catch (Exception e) {
                ui.post(() -> toast("Cannot read file: " + e.getMessage()));
                return;
            }
            if (c.type == T_AUDIO) c.track = TR_AUDIO;
            else if (track == TR_AUDIO) { ui.post(() -> toast("Pick an audio file")); return; }
            ui.post(() -> {
                pushUndo();
                c.id = nextId++;
                clips.add(c);
                select(c.id);
                scheduleRefresh();
            });
        });
    }

    private Bitmap decodeThumb(Uri uri) throws Exception {
        BitmapFactory.Options o = new BitmapFactory.Options();
        o.inSampleSize = 8;
        try (InputStream in = getContentResolver().openInputStream(uri)) {
            return BitmapFactory.decodeStream(in, null, o);
        }
    }

    private String queryName(Uri uri) {
        try (Cursor c = getContentResolver().query(uri, null, null, null, null)) {
            if (c != null && c.moveToFirst()) {
                int i = c.getColumnIndex(OpenableColumns.DISPLAY_NAME);
                if (i >= 0) return c.getString(i);
            }
        } catch (Exception ignored) { }
        return "clip";
    }

    private void splitAtPlayhead() {
        long ph = playhead();
        Clip c = selected();
        if (c == null || (c.type != T_VIDEO && c.type != T_AUDIO)) {
            c = null;
            long acc = 0;
            for (Clip m : clips) {
                if (m.track != TR_MAIN) continue;
                long e = effMs(m);
                if (m.type == T_VIDEO && ph > acc && ph < acc + e) { c = m; break; }
                acc += e;
            }
        }
        if (c == null) { toast("Move the playhead over a video/audio clip"); return; }
        long start = clipStart(c), eff = effMs(c);
        if (ph <= start + 100 || ph >= start + eff - 100) { toast("Playhead must be inside the clip"); return; }
        pushUndo();
        long local = c.trimStart + Math.round((ph - start) * c.speed);
        Clip second = c.copy();
        second.id = nextId++;
        second.trimStart = local;
        if (c.track != TR_MAIN) second.offsetMs = ph;
        c.trimEnd = local;
        clips.add(clips.indexOf(c) + 1, second);
        select(second.id);
        scheduleRefresh();
    }

    private void moveSelected(int dir) {
        Clip c = selected();
        if (c == null) return;
        int idx = clips.indexOf(c);
        for (int i = idx + dir; i >= 0 && i < clips.size(); i += dir) {
            if (clips.get(i).track == c.track) {
                pushUndo();
                clips.remove(idx);
                clips.add(i, c);
                renderTimeline(); scheduleRefresh();
                return;
            }
        }
    }

    // ================================================================== undo / redo
    private List<Clip> snapshot() {
        List<Clip> s = new ArrayList<>();
        for (Clip c : clips) s.add(c.copy());
        return s;
    }

    private void pushUndo() {
        undoStack.push(snapshot());
        if (undoStack.size() > 60) undoStack.removeLast();
        redoStack.clear();
    }

    private void undo() {
        if (undoStack.isEmpty()) return;
        redoStack.push(snapshot());
        restore(undoStack.pop());
    }

    private void redo() {
        if (redoStack.isEmpty()) return;
        undoStack.push(snapshot());
        restore(redoStack.pop());
    }

    private void restore(List<Clip> s) {
        clips.clear();
        clips.addAll(s);
        if (selected() == null) selectedId = -1;
        renderTimeline(); bindSelectionToUi(); scheduleRefresh();
    }

    // ================================================================== selection / timeline UI
    private Clip selected() {
        for (Clip c : clips) if (c.id == selectedId) return c;
        return null;
    }

    private void select(int id) {
        selectedId = id;
        renderTimeline();
        bindSelectionToUi();
    }

    private boolean hasMain() {
        for (Clip c : clips) if (c.track == TR_MAIN) return true;
        return false;
    }

    private long effMs(Clip c) {
        if (c.type == T_VIDEO || c.type == T_AUDIO) return Math.max(1, Math.round((c.trimEnd - c.trimStart) / c.speed));
        return c.durMs;
    }

    private long clipStart(Clip c) {
        if (c.track != TR_MAIN) return c.offsetMs;
        long acc = 0;
        for (Clip m : clips) {
            if (m == c) break;
            if (m.track == TR_MAIN) acc += effMs(m);
        }
        return acc;
    }

    private long totalMs() {
        long mainSum = 0, max = 0;
        for (Clip c : clips) {
            if (c.track == TR_MAIN) mainSum += effMs(c);
            else max = Math.max(max, c.offsetMs + effMs(c));
        }
        return Math.max(mainSum, max);
    }

    private void renderTimeline() {
        trackMain.removeAllViews(); trackOver.removeAllViews();
        trackAudio.removeAllViews(); trackText.removeAllViews();
        for (Clip c : clips) {
            LinearLayout parent = c.track == TR_MAIN ? trackMain : c.track == TR_OVER ? trackOver
                    : c.track == TR_AUDIO ? trackAudio : trackText;
            parent.addView(makeChip(c));
        }
    }

    private View makeChip(Clip c) {
        LinearLayout l = new LinearLayout(this);
        l.setOrientation(LinearLayout.HORIZONTAL);
        l.setGravity(Gravity.CENTER_VERTICAL);
        l.setPadding(dp(3), dp(3), dp(3), dp(3));
        l.setBackgroundColor(c.id == selectedId ? 0xFF3D5AFE : (c.track == TR_AUDIO ? 0xFF1B5E20 : c.track == TR_TEXT ? 0xFF6A1B9A : 0xFF333333));
        int w = dp(Math.max(84, Math.min(300, (int) (effMs(c) / 1000f * 14))));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(w, ViewGroup.LayoutParams.MATCH_PARENT);
        lp.setMargins(dp(2), dp(2), dp(2), dp(2));
        l.setLayoutParams(lp);
        ImageView iv = new ImageView(this);
        iv.setLayoutParams(new LinearLayout.LayoutParams(dp(38), dp(38)));
        iv.setScaleType(ImageView.ScaleType.CENTER_CROP);
        if (c.thumb != null) iv.setImageBitmap(c.thumb);
        else iv.setBackgroundColor(0x33FFFFFF);
        l.addView(iv);
        TextView tv = new TextView(this);
        tv.setTextColor(Color.WHITE);
        tv.setTextSize(10);
        tv.setMaxLines(2);
        tv.setPadding(dp(4), 0, 0, 0);
        String icon = c.type == T_AUDIO ? "♪ " : c.type == T_TEXT ? "T " : c.chroma ? "◈ " : "";
        tv.setText(icon + (c.type == T_TEXT ? c.text : c.name) + "\n" + fmt(effMs(c)));
        l.addView(tv);
        l.setOnClickListener(v -> select(c.id));
        return l;
    }

    // ================================================================== tool panel binding
    private interface SeekCb { void on(Clip c, int p); }

    private void bindSeek(int id, SeekCb cb) {
        SeekBar s = findViewById(id);
        s.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
            @Override public void onProgressChanged(SeekBar sb, int p, boolean fromUser) {
                if (binding || !fromUser) return;
                Clip c = selected();
                if (c == null) return;
                cb.on(c, p);
                updateLabels(c);
                renderTimeline();
            }
            @Override public void onStartTrackingTouch(SeekBar sb) { pushUndo(); }
            @Override public void onStopTrackingTouch(SeekBar sb) { scheduleRefresh(); }
        });
    }

    private void setupToolControls() {
        bindSeek(R.id.seekTrimStart, (c, p) -> {
            c.trimStart = Math.min(c.srcDurMs * p / 1000L, c.trimEnd - 200);
        });
        bindSeek(R.id.seekTrimEnd, (c, p) -> {
            c.trimEnd = Math.max(c.srcDurMs * p / 1000L, c.trimStart + 200);
        });
        bindSeek(R.id.seekDuration, (c, p) -> c.durMs = 500 + p * 100L);
        bindSeek(R.id.seekOffset, (c, p) -> c.offsetMs = p * 100L);
        bindSeek(R.id.seekSpeed, (c, p) -> c.speed = 0.25f + p * 0.05f);
        bindSeek(R.id.seekVolume, (c, p) -> c.volume = p / 100f);
        bindSeek(R.id.seekScale, (c, p) -> c.scale = Math.max(0.05f, p / 100f));
        bindSeek(R.id.seekPosX, (c, p) -> c.posX = (p - 100) / 100f);
        bindSeek(R.id.seekPosY, (c, p) -> c.posY = (p - 100) / 100f);
        bindSeek(R.id.seekOpacity, (c, p) -> c.opacity = p / 100f);
        bindSeek(R.id.seekBright, (c, p) -> c.brightness = (p - 100) / 200f);
        bindSeek(R.id.seekContrast, (c, p) -> c.contrast = (p - 100) / 100f);
        bindSeek(R.id.seekSat, (c, p) -> c.saturation = p / 100f);
        bindSeek(R.id.seekSim, (c, p) -> c.sim = p / 200f);
        bindSeek(R.id.seekSmooth, (c, p) -> c.smooth = p / 400f);
        bindSeek(R.id.seekSpill, (c, p) -> c.spill = p / 400f);
        bindSeek(R.id.seekTextSize, (c, p) -> c.textSize = Math.max(10, p));

        Spinner sf = findViewById(R.id.spinFilter);
        sf.setAdapter(new ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item, FILTERS));
        sf.setOnItemSelectedListener(new SimpleSel() {
            @Override void sel(int pos) {
                Clip c = selected();
                if (binding || c == null || c.filter == pos) return;
                pushUndo(); c.filter = pos; scheduleRefresh();
            }
        });

        findViewById(R.id.btnRotate).setOnClickListener(v -> edit(c -> c.rotation = (c.rotation + 90) % 360));
        findViewById(R.id.btnFlipH).setOnClickListener(v -> edit(c -> c.flipH = !c.flipH));
        findViewById(R.id.btnFlipV).setOnClickListener(v -> edit(c -> c.flipV = !c.flipV));

        ((Switch) findViewById(R.id.swChroma)).setOnCheckedChangeListener((cb, on) -> {
            Clip c = selected();
            if (binding || c == null) return;
            pushUndo(); c.chroma = on; renderTimeline(); scheduleRefresh();
        });
        findViewById(R.id.btnKeyGreen).setOnClickListener(v -> edit(c -> { c.keyColor = 0xFF00B140; c.chroma = true; }));
        findViewById(R.id.btnKeyBlue).setOnClickListener(v -> edit(c -> { c.keyColor = 0xFF0047BB; c.chroma = true; }));
        findViewById(R.id.btnEyedrop).setOnClickListener(v -> {
            eyedrop = true;
            toast("Tap the background colour in the preview (do this before enabling the key)");
        });

        EditText et = findViewById(R.id.edtText);
        et.addTextChangedListener(new android.text.TextWatcher() {
            @Override public void beforeTextChanged(CharSequence s, int a, int b, int c) { }
            @Override public void onTextChanged(CharSequence s, int a, int b, int c) { }
            @Override public void afterTextChanged(android.text.Editable e) {
                Clip c = selected();
                if (binding || c == null || c.type != T_TEXT) return;
                c.text = e.toString();
                renderTimeline();
                scheduleRefresh();
            }
        });
        findViewById(R.id.btnTextColor).setOnClickListener(v -> edit(c -> {
            int i = 0;
            for (int k = 0; k < TEXT_COLORS.length; k++) if (TEXT_COLORS[k] == c.textColor) i = k;
            c.textColor = TEXT_COLORS[(i + 1) % TEXT_COLORS.length];
        }));
    }

    private interface Edit { void apply(Clip c); }

    private void edit(Edit e) {
        Clip c = selected();
        if (c == null) { toast("Select a clip first"); return; }
        pushUndo();
        e.apply(c);
        bindSelectionToUi();
        renderTimeline();
        scheduleRefresh();
    }

    private void bindSelectionToUi() {
        Clip c = selected();
        binding = true;
        boolean has = c != null;
        boolean media = has && (c.type == T_VIDEO || c.type == T_AUDIO);
        boolean visual = has && (c.type == T_VIDEO || c.type == T_IMAGE);
        vis(R.id.secTrim, media);
        vis(R.id.secDuration, has && (c.type == T_IMAGE || c.type == T_TEXT));
        vis(R.id.secOffset, has && c.track != TR_MAIN);
        vis(R.id.secSpeed, media);
        vis(R.id.secVolume, media);
        vis(R.id.secRotate, visual);
        vis(R.id.secTransform, has && (c.track == TR_OVER || c.track == TR_TEXT));
        vis(R.id.secAdjust, visual);
        vis(R.id.secChroma, visual);
        vis(R.id.secText, has && c.type == T_TEXT);
        if (!has) {
            txtSelected.setText("Select a clip on the timeline to edit it");
        } else {
            txtSelected.setText((c.track == TR_MAIN ? "Main · " : c.track == TR_OVER ? "Layer · " : c.track == TR_AUDIO ? "Audio · " : "Text · ")
                    + (c.type == T_TEXT ? "Text" : c.name));
            if (c.srcDurMs > 0) {
                setSeek(R.id.seekTrimStart, (int) (c.trimStart * 1000 / c.srcDurMs));
                setSeek(R.id.seekTrimEnd, (int) (c.trimEnd * 1000 / c.srcDurMs));
            }
            setSeek(R.id.seekDuration, (int) ((c.durMs - 500) / 100));
            setSeek(R.id.seekOffset, (int) (c.offsetMs / 100));
            setSeek(R.id.seekSpeed, Math.round((c.speed - 0.25f) / 0.05f));
            setSeek(R.id.seekVolume, Math.round(c.volume * 100));
            setSeek(R.id.seekScale, Math.round(c.scale * 100));
            setSeek(R.id.seekPosX, Math.round(c.posX * 100 + 100));
            setSeek(R.id.seekPosY, Math.round(c.posY * 100 + 100));
            setSeek(R.id.seekOpacity, Math.round(c.opacity * 100));
            setSeek(R.id.seekBright, Math.round(c.brightness * 200 + 100));
            setSeek(R.id.seekContrast, Math.round(c.contrast * 100 + 100));
            setSeek(R.id.seekSat, Math.round(c.saturation * 100));
            setSeek(R.id.seekSim, Math.round(c.sim * 200));
            setSeek(R.id.seekSmooth, Math.round(c.smooth * 400));
            setSeek(R.id.seekSpill, Math.round(c.spill * 400));
            setSeek(R.id.seekTextSize, c.textSize);
            ((Spinner) findViewById(R.id.spinFilter)).setSelection(c.filter);
            ((Switch) findViewById(R.id.swChroma)).setChecked(c.chroma);
            findViewById(R.id.viewKey).setBackgroundColor(c.keyColor);
            EditText et = findViewById(R.id.edtText);
            if (c.type == T_TEXT && !et.getText().toString().equals(c.text)) et.setText(c.text);
            updateLabels(c);
        }
        binding = false;
    }

    private void updateLabels(Clip c) {
        ((TextView) findViewById(R.id.txtTrim)).setText("Trim  " + fmt(c.trimStart) + " → " + fmt(c.trimEnd) + "  (" + fmt(effMs(c)) + ")");
        ((TextView) findViewById(R.id.txtDuration)).setText("Duration  " + fmt(c.durMs));
        ((TextView) findViewById(R.id.txtOffset)).setText("Starts at  " + fmt(c.offsetMs));
        ((TextView) findViewById(R.id.txtSpeed)).setText(String.format(Locale.US, "Speed  %.2fx", c.speed));
        ((TextView) findViewById(R.id.txtVolume)).setText("Volume  " + Math.round(c.volume * 100) + "%");
        ((TextView) findViewById(R.id.txtScale)).setText("Layer size  " + Math.round(c.scale * 100) + "%");
        ((TextView) findViewById(R.id.txtOpacity)).setText("Opacity  " + Math.round(c.opacity * 100) + "%");
        ((TextView) findViewById(R.id.txtSim)).setText("Similarity  " + Math.round(c.sim * 200));
        ((TextView) findViewById(R.id.txtSmooth)).setText("Edge smoothness  " + Math.round(c.smooth * 400));
        ((TextView) findViewById(R.id.txtSpill)).setText("Spill suppression  " + Math.round(c.spill * 400));
    }

    private void setSeek(int id, int p) { ((SeekBar) findViewById(id)).setProgress(Math.max(0, p)); }
    private void vis(int id, boolean on) { findViewById(id).setVisibility(on ? View.VISIBLE : View.GONE); }

    /** Eyedropper: read one pixel from the preview surface. */
    private void sampleColor(int x, int y) {
        eyedrop = false;
        Clip c = selected();
        if (c == null) return;
        try {
            final Bitmap bmp = Bitmap.createBitmap(1, 1, Bitmap.Config.ARGB_8888);
            int sx = Math.max(0, Math.min(surface.getWidth() - 1, x));
            int sy = Math.max(0, Math.min(surface.getHeight() - 1, y));
            PixelCopy.request(surface, new Rect(sx, sy, sx + 1, sy + 1), bmp, result -> {
                if (result == PixelCopy.SUCCESS) {
                    int col = bmp.getPixel(0, 0) | 0xFF000000;
                    pushUndo();
                    c.keyColor = col; c.chroma = true;
                    bindSelectionToUi(); renderTimeline(); scheduleRefresh();
                } else toast("Could not read colour");
            }, ui);
        } catch (Exception e) { toast("Eyedropper failed: " + e.getMessage()); }
    }

    // ================================================================== composition builder
    private int[] canvas(int shortSide) {
        float rw = RATIOS[ratioIdx][0], rh = RATIOS[ratioIdx][1];
        int w, h;
        if (rw >= rh) { h = shortSide; w = Math.round(shortSide * rw / rh); }
        else { w = shortSide; h = Math.round(shortSide * rh / rw); }
        return new int[]{w & ~1, h & ~1};
    }

    private float[] filterMatrix(int f) {
        float[] r;
        switch (f) {
            case 1: r = new float[]{.299f, .587f, .114f, .299f, .587f, .114f, .299f, .587f, .114f}; break;
            case 2: r = new float[]{.393f, .769f, .189f, .349f, .686f, .168f, .272f, .534f, .131f}; break;
            case 3: r = new float[]{1.12f, 0, 0, 0, 1.0f, 0, 0, 0, 0.85f}; break;
            case 4: r = new float[]{0.88f, 0, 0, 0, 1.0f, 0, 0, 0, 1.15f}; break;
            case 5: r = new float[]{.62f, .38f, .0f, .2f, .75f, .05f, .12f, .25f, .6f}; break;
            case 6: r = new float[]{.45f, .45f, .1f, .45f, .45f, .1f, .45f, .45f, .1f}; break; // noir (flat grey; add contrast on top)
            default: return null;
        }
        // row-major 3x3 -> column-major 4x4
        return new float[]{r[0], r[3], r[6], 0, r[1], r[4], r[7], 0, r[2], r[5], r[8], 0, 0, 0, 0, 1};
    }

    private List<Effect> videoEffects(Clip c, int W, int H, boolean main) {
        List<Effect> fx = new ArrayList<>();
        if (c.rotation != 0 || c.flipH || c.flipV) {
            fx.add(new ScaleAndRotateTransformation.Builder()
                    .setScale(c.flipH ? -1f : 1f, c.flipV ? -1f : 1f)
                    .setRotationDegrees(c.rotation).build());
        }
        if (c.brightness != 0f) fx.add(new Brightness(c.brightness));
        if (c.contrast != 0f) fx.add(new Contrast(c.contrast));
        if (c.saturation != 1f) fx.add(new HslAdjustment.Builder().adjustSaturation((c.saturation - 1f) * 100f).build());
        final float[] fm = filterMatrix(c.filter);
        if (fm != null) {
            fx.add(new RgbMatrix() {
                @Override public float[] getMatrix(long presentationTimeUs, boolean useHdr) { return fm; }
            });
        }
        if (c.chroma) fx.add(new ChromaKeyEffect(c.keyColor, c.sim, c.smooth, c.spill));
        if (c.type == T_VIDEO && c.speed != 1f) fx.add(new SpeedChangeEffect(c.speed));
        if (main) {
            fx.add(Presentation.createForWidthAndHeight(W, H,
                    fillMode ? Presentation.LAYOUT_SCALE_TO_FIT_WITH_CROP : Presentation.LAYOUT_SCALE_TO_FIT));
        } else {
            fx.add(Presentation.createForAspectRatio(W / (float) H, Presentation.LAYOUT_SCALE_TO_FIT_WITH_CROP));
        }
        return fx;
    }

    private List<AudioProcessor> audioProcessors(Clip c) {
        List<AudioProcessor> ap = new ArrayList<>();
        if (c.speed != 1f) {
            SonicAudioProcessor s = new SonicAudioProcessor();
            s.setSpeed(c.speed);
            s.setPitch(1f);
            ap.add(s);
        }
        if (c.volume != 1f) {
            ChannelMixingAudioProcessor m = new ChannelMixingAudioProcessor();
            for (int ch = 1; ch <= 2; ch++) m.putChannelMixingMatrix(ChannelMixingMatrix.create(ch, ch).scaleBy(c.volume));
            ap.add(m);
        }
        return ap;
    }

    private EditedMediaItem toItem(Clip c, int W, int H, boolean main) {
        MediaItem.Builder mib = new MediaItem.Builder().setUri(c.uri);
        if ((c.type == T_VIDEO || c.type == T_AUDIO) && (c.trimStart > 0 || c.trimEnd < c.srcDurMs)) {
            mib.setClippingConfiguration(new MediaItem.ClippingConfiguration.Builder()
                    .setStartPositionMs(c.trimStart)
                    .setEndPositionMs(c.trimEnd >= c.srcDurMs ? C.TIME_END_OF_SOURCE : c.trimEnd)
                    .build());
        }
        EditedMediaItem.Builder eb = new EditedMediaItem.Builder(mib.build());
        if (c.type == T_IMAGE) eb.setDurationUs(c.durMs * 1000L).setFrameRate(30);
        if (c.type == T_AUDIO) {
            eb.setRemoveVideo(true);
            eb.setEffects(new Effects(audioProcessors(c), new ArrayList<Effect>()));
        } else {
            eb.setEffects(new Effects(c.type == T_IMAGE ? new ArrayList<AudioProcessor>() : audioProcessors(c), videoEffects(c, W, H, main)));
        }
        return eb.build();
    }

    /** Builds the full multi-layer composition. Returns null when there is nothing to render. */
    private Composition buildComposition(int shortSide, boolean forExport) {
        int[] cs = canvas(shortSide);
        List<Clip> over = new ArrayList<>();
        List<Clip> audio = new ArrayList<>();
        List<Clip> texts = new ArrayList<>();
        EditedMediaItemSequence.Builder mainB = new EditedMediaItemSequence.Builder();
        boolean any = false;
        for (Clip c : clips) {
            if (c.track == TR_MAIN) { mainB.addItem(toItem(c, cs[0], cs[1], true)); any = true; }
            else if (c.track == TR_OVER) over.add(c);
            else if (c.track == TR_AUDIO) audio.add(c);
            else texts.add(c);
        }
        if (!any) return null;

        List<EditedMediaItemSequence> seqs = new ArrayList<>();
        seqs.add(mainB.build());
        for (Clip c : over) {                      // each overlay layer = its own sequence (video inputs come first)
            EditedMediaItemSequence.Builder b = new EditedMediaItemSequence.Builder();
            if (c.offsetMs > 0) b.addGap(c.offsetMs * 1000L);
            b.addItem(toItem(c, cs[0], cs[1], false));
            seqs.add(b.build());
        }
        for (Clip c : audio) {                     // audio-only sequences go last
            EditedMediaItemSequence.Builder b = new EditedMediaItemSequence.Builder();
            if (c.offsetMs > 0) b.addGap(c.offsetMs * 1000L);
            b.addItem(toItem(c, cs[0], cs[1], false));
            seqs.add(b.build());
        }

        final List<Clip> overFinal = over;
        VideoCompositorSettings vcs = new VideoCompositorSettings() {
            @Override public Size getOutputSize(List<Size> inputSizes) { return inputSizes.get(0); }
            @Override public OverlaySettings getOverlaySettings(int inputId, long presentationTimeUs) {
                if (inputId <= 0 || inputId > overFinal.size()) return new OverlaySettings.Builder().build();
                Clip c = overFinal.get(inputId - 1);
                return new OverlaySettings.Builder()
                        .setScale(c.scale, c.scale)
                        .setBackgroundFrameAnchor(c.posX, c.posY)
                        .setAlphaScale(c.opacity)
                        .build();
            }
        };

        // composition-level effects: timed text overlays + frame rate
        List<Effect> vfx = new ArrayList<>();
        if (!texts.isEmpty()) {
            int[] tc = canvas(Math.min(shortSide, 1080));
            Bitmap empty = Bitmap.createBitmap(1, 1, Bitmap.Config.ARGB_8888);
            List<TextureOverlay> tos = new ArrayList<>();
            for (Clip t : texts) {
                OverlaySettings os = new OverlaySettings.Builder()
                        .setScale(t.scale, t.scale)
                        .setBackgroundFrameAnchor(t.posX, t.posY).build();
                tos.add(new TimedBitmapOverlay(renderText(t, tc[0], tc[1]), empty,
                        t.offsetMs * 1000L, (t.offsetMs + t.durMs) * 1000L, os));
            }
            vfx.add(new OverlayEffect(ImmutableList.copyOf(tos)));
        }
        if (forExport && exportFpsIdx() > 0) {
            vfx.add(FrameDropEffect.createDefaultFrameDropEffect(exportFpsIdx() == 1 ? 30f : 24f));
        }

        return new Composition.Builder(seqs)
                .setEffects(new Effects(new ArrayList<AudioProcessor>(), vfx))
                .setVideoCompositorSettings(vcs)
                .build();
    }

    private Bitmap renderText(Clip c, int W, int H) {
        Bitmap b = Bitmap.createBitmap(W, H, Bitmap.Config.ARGB_8888);
        Canvas cv = new Canvas(b);
        TextPaint tp = new TextPaint(Paint.ANTI_ALIAS_FLAG);
        tp.setColor(c.textColor);
        tp.setTextSize(H * c.textSize / 1000f);
        tp.setTypeface(Typeface.DEFAULT_BOLD);
        tp.setShadowLayer(H * 0.004f, 0, H * 0.002f, Color.BLACK);
        String s = c.text.isEmpty() ? " " : c.text;
        StaticLayout sl = StaticLayout.Builder.obtain(s, 0, s.length(), tp, (int) (W * 0.9f))
                .setAlignment(Layout.Alignment.ALIGN_CENTER).build();
        cv.translate(W / 2f - sl.getWidth() / 2f, H / 2f - sl.getHeight() / 2f);
        sl.draw(cv);
        return b;
    }

    /** Text overlay that is only visible between startUs and endUs. */
    static class TimedBitmapOverlay extends BitmapOverlay {
        private final Bitmap bmp, empty;
        private final long startUs, endUs;
        private final OverlaySettings settings;

        TimedBitmapOverlay(Bitmap bmp, Bitmap empty, long startUs, long endUs, OverlaySettings s) {
            this.bmp = bmp; this.empty = empty; this.startUs = startUs; this.endUs = endUs; this.settings = s;
        }
        @Override public Bitmap getBitmap(long t) { return (t >= startUs && t < endUs) ? bmp : empty; }
        @Override public OverlaySettings getOverlaySettings(long t) { return settings; }
    }

    // ================================================================== preview
    private final Runnable refreshRunnable = this::rebuildPreview;

    private void scheduleRefresh() {
        renderTimelineSafe();
        ui.removeCallbacks(refreshRunnable);
        ui.postDelayed(refreshRunnable, 450);
    }

    private void renderTimelineSafe() { renderTimeline(); }

    private void rebuildPreview() {
        if (exporting || !surfaceReady) return;
        long pos = player != null ? player.getCurrentPosition() : 0;
        boolean wasPlaying = player != null && player.isPlaying();
        releasePlayer();
        Composition comp;
        try {
            comp = buildComposition(PREVIEW_SHORT_SIDE, false);
        } catch (Exception e) {
            toast("Preview error: " + e.getMessage());
            return;
        }
        txtEmpty.setVisibility(comp == null ? View.VISIBLE : View.GONE);
        if (comp == null) return;
        player = new CompositionPlayer.Builder(this).build();
        player.setVideoSurfaceView(surface);
        player.addListener(new Player.Listener() {
            @Override public void onPlayerError(PlaybackException error) { toast("Preview: " + error.getMessage()); }
            @Override public void onIsPlayingChanged(boolean isPlaying) { btnPlay.setText(isPlaying ? "❚❚" : "▶"); }
        });
        player.setComposition(comp);
        player.prepare();
        player.seekTo(Math.min(pos, Math.max(0, totalMs() - 50)));
        if (wasPlaying) player.play();
    }

    private void releasePlayer() {
        if (player != null) {
            player.release();
            player = null;
            btnPlay.setText("▶");
        }
    }

    // ================================================================== export
    private void setupExportPanel() {
        Spinner r = findViewById(R.id.spinRes), f = findViewById(R.id.spinFps),
                c = findViewById(R.id.spinCodec), q = findViewById(R.id.spinQuality);
        r.setAdapter(new ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item, RES_NAMES));
        f.setAdapter(new ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item, FPS_NAMES));
        c.setAdapter(new ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item, CODEC_NAMES));
        q.setAdapter(new ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item, QUALITY_NAMES));
        r.setSelection(1); q.setSelection(1);
        findViewById(R.id.btnStartExport).setOnClickListener(v -> startExport());
        findViewById(R.id.btnCancelExport).setOnClickListener(v -> {
            if (exporting && transformer != null) transformer.cancel();
            panelExport.setVisibility(View.GONE);
        });
    }

    private int exportFpsIdx() { return ((Spinner) findViewById(R.id.spinFps)).getSelectedItemPosition(); }

    private boolean encoderSupports(String mime, int w, int h) {
        for (MediaCodecInfo ci : new MediaCodecList(MediaCodecList.REGULAR_CODECS).getCodecInfos()) {
            if (!ci.isEncoder()) continue;
            for (String t : ci.getSupportedTypes()) {
                if (!t.equalsIgnoreCase(mime)) continue;
                try {
                    if (ci.getCapabilitiesForType(t).getVideoCapabilities().isSizeSupported(w, h)) return true;
                } catch (Exception ignored) { }
            }
        }
        return false;
    }

    private void startExport() {
        if (exporting) return;
        int resIdx = ((Spinner) findViewById(R.id.spinRes)).getSelectedItemPosition();
        boolean hevc = ((Spinner) findViewById(R.id.spinCodec)).getSelectedItemPosition() == 1;
        int qIdx = ((Spinner) findViewById(R.id.spinQuality)).getSelectedItemPosition();
        int shortSide = RES_VALUES[resIdx];
        int[] cs = canvas(shortSide);
        String mime = hevc ? MimeTypes.VIDEO_H265 : MimeTypes.VIDEO_H264;

        if (!encoderSupports(mime, cs[0], cs[1])) {
            toast("This phone has no " + (hevc ? "H.265" : "H.264") + " encoder for " + cs[0] + "×" + cs[1]
                    + ". Export will fall back to a lower resolution.");
        }

        Composition comp;
        try {
            comp = buildComposition(shortSide, true);
        } catch (Exception e) {
            toast("Cannot build project: " + e.getMessage());
            return;
        }
        if (comp == null) { toast("Add a main video first"); return; }

        releasePlayer();                                   // free hardware codecs for the encoder
        float mbps = BASE_MBPS[resIdx] * QUALITY_MULT[qIdx] * (hevc ? 0.65f : 1f);
        VideoEncoderSettings ves = new VideoEncoderSettings.Builder().setBitrate((int) (mbps * 1_000_000)).build();
        File out = new File(getCacheDir(), "export_" + System.currentTimeMillis() + ".mp4");

        transformer = new Transformer.Builder(this)
                .setVideoMimeType(mime)
                .setAudioMimeType(MimeTypes.AUDIO_AAC)
                .setEncoderFactory(new DefaultEncoderFactory.Builder(this)
                        .setRequestedVideoEncoderSettings(ves)
                        .setEnableFallback(true).build())
                .addListener(new Transformer.Listener() {
                    @Override public void onCompleted(Composition composition, ExportResult exportResult) {
                        finishExport();
                        txtExportStatus.setText("Saving to gallery…");
                        exec.execute(() -> {
                            Uri saved = saveToGallery(out);
                            ui.post(() -> exportDone(saved));
                        });
                    }
                    @Override public void onError(Composition composition, ExportResult exportResult, ExportException e) {
                        finishExport();
                        txtExportStatus.setText("Export failed: " + e.getMessage());
                        scheduleRefresh();
                    }
                })
                .build();

        exporting = true;
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        progressExport.setVisibility(View.VISIBLE);
        progressExport.setProgress(0);
        txtExportStatus.setText(String.format(Locale.US, "Exporting %d×%d  ·  %.0f Mbps", cs[0], cs[1], mbps));
        transformer.start(comp, out.getAbsolutePath());
    }

    private void finishExport() {
        exporting = false;
        getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        progressExport.setVisibility(View.GONE);
    }

    private Uri saveToGallery(File f) {
        try {
            ContentValues v = new ContentValues();
            v.put(MediaStore.Video.Media.DISPLAY_NAME, "VideoEditor_" + System.currentTimeMillis() + ".mp4");
            v.put(MediaStore.Video.Media.MIME_TYPE, "video/mp4");
            v.put(MediaStore.Video.Media.RELATIVE_PATH, "Movies/VideoEditor");
            v.put(MediaStore.Video.Media.IS_PENDING, 1);
            Uri uri = getContentResolver().insert(MediaStore.Video.Media.EXTERNAL_CONTENT_URI, v);
            try (InputStream in = new FileInputStream(f); OutputStream os = getContentResolver().openOutputStream(uri)) {
                byte[] buf = new byte[1 << 16];
                int n;
                while ((n = in.read(buf)) > 0) os.write(buf, 0, n);
            }
            v.clear();
            v.put(MediaStore.Video.Media.IS_PENDING, 0);
            getContentResolver().update(uri, v, null, null);
            //noinspection ResultOfMethodCallIgnored
            f.delete();
            return uri;
        } catch (Exception e) {
            return null;
        }
    }

    private void exportDone(Uri uri) {
        if (uri == null) { txtExportStatus.setText("Export finished but saving failed."); return; }
        txtExportStatus.setText("Saved to Movies/VideoEditor");
        new AlertDialog.Builder(this)
                .setTitle("Export complete")
                .setMessage("Your video was saved to Movies/VideoEditor.")
                .setPositiveButton("Share", (d, w) -> {
                    Intent s = new Intent(Intent.ACTION_SEND);
                    s.setType("video/mp4");
                    s.putExtra(Intent.EXTRA_STREAM, uri);
                    s.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
                    startActivity(Intent.createChooser(s, "Share video"));
                })
                .setNegativeButton("Close", null)
                .show();
        scheduleRefresh();
    }

    // ================================================================== chroma key shader
    static class ChromaKeyEffect implements GlEffect {
        final float[] key;
        final float sim, smooth, spill;

        ChromaKeyEffect(int color, float sim, float smooth, float spill) {
            this.key = new float[]{Color.red(color) / 255f, Color.green(color) / 255f, Color.blue(color) / 255f};
            this.sim = sim; this.smooth = smooth; this.spill = spill;
        }

        @Override
        public GlShaderProgram toGlShaderProgram(android.content.Context context, boolean useHdr)
                throws VideoFrameProcessingException {
            return new ChromaKeyProgram(useHdr, key, sim, smooth, spill);
        }
    }

    static class ChromaKeyProgram extends BaseGlShaderProgram {
        private static final String VERT =
                "#version 100\n"
                + "attribute vec4 aFramePosition;\n"
                + "varying vec2 vTexSamplingCoord;\n"
                + "void main() {\n"
                + "  gl_Position = aFramePosition;\n"
                + "  vTexSamplingCoord = aFramePosition.xy * 0.5 + 0.5;\n"
                + "}\n";
        private static final String FRAG =
                "#version 100\n"
                + "precision highp float;\n"
                + "uniform sampler2D uTexSampler;\n"
                + "uniform vec3 uKey;\n"
                + "uniform float uSim;\n"
                + "uniform float uSmooth;\n"
                + "uniform float uSpill;\n"
                + "varying vec2 vTexSamplingCoord;\n"
                + "vec2 rgb2uv(vec3 c) {\n"
                + "  return vec2(c.r * -0.169 + c.g * -0.331 + c.b * 0.5 + 0.5,\n"
                + "              c.r * 0.5 + c.g * -0.419 + c.b * -0.081 + 0.5);\n"
                + "}\n"
                + "void main() {\n"
                + "  vec4 c = texture2D(uTexSampler, vTexSamplingCoord);\n"
                + "  float d = distance(rgb2uv(c.rgb), rgb2uv(uKey));\n"
                + "  float a = smoothstep(uSim, uSim + uSmooth + 0.0001, d);\n"
                + "  float lum = dot(c.rgb, vec3(0.299, 0.587, 0.114));\n"
                + "  float keep = smoothstep(uSim, uSim + uSmooth + uSpill + 0.0001, d);\n"
                + "  vec3 rgb = mix(vec3(lum), c.rgb, keep);\n"
                + "  gl_FragColor = vec4(rgb, a * c.a);\n"
                + "}\n";

        private final GlProgram glProgram;
        private final float[] key;
        private final float sim, smooth, spill;

        ChromaKeyProgram(boolean useHdr, float[] key, float sim, float smooth, float spill)
                throws VideoFrameProcessingException {
            super(useHdr, /* texturePoolCount= */ 1);
            this.key = key; this.sim = sim; this.smooth = smooth; this.spill = spill;
            try {
                glProgram = new GlProgram(VERT, FRAG);
            } catch (GlUtil.GlException e) {
                throw new VideoFrameProcessingException(e);
            }
            glProgram.setBufferAttribute("aFramePosition", GlUtil.getNormalizedCoordinateBounds(),
                    GlUtil.HOMOGENEOUS_COORDINATE_VECTOR_SIZE);
        }

        @Override
        public Size configure(int inputWidth, int inputHeight) { return new Size(inputWidth, inputHeight); }

        @Override
        public void drawFrame(int inputTexId, long presentationTimeUs) throws VideoFrameProcessingException {
            try {
                glProgram.use();
                glProgram.setSamplerTexIdUniform("uTexSampler", inputTexId, /* texUnitIndex= */ 0);
                glProgram.setFloatsUniform("uKey", key);
                glProgram.setFloatUniform("uSim", sim);
                glProgram.setFloatUniform("uSmooth", smooth);
                glProgram.setFloatUniform("uSpill", spill);
                glProgram.bindAttributesAndUniforms();
                GLES20.glDrawArrays(GLES20.GL_TRIANGLE_STRIP, 0, 4);
                GlUtil.checkGlError();
            } catch (GlUtil.GlException e) {
                throw new VideoFrameProcessingException(e, presentationTimeUs);
            }
        }

        @Override
        public void release() throws VideoFrameProcessingException {
            super.release();
            try {
                glProgram.delete();
            } catch (GlUtil.GlException e) {
                throw new VideoFrameProcessingException(e);
            }
        }
    }

    // ================================================================== small helpers
    private abstract static class SimpleSel implements AdapterView.OnItemSelectedListener {
        abstract void sel(int pos);
        @Override public void onItemSelected(AdapterView<?> p, View v, int pos, long id) { sel(pos); }
        @Override public void onNothingSelected(AdapterView<?> p) { }
    }

    private int dp(int v) { return Math.round(v * getResources().getDisplayMetrics().density); }

    private void toast(String s) { Toast.makeText(this, s, Toast.LENGTH_LONG).show(); }

    private static String fmt(long ms) {
        long t = Math.max(0, ms);
        return String.format(Locale.US, "%02d:%02d.%d", t / 60000, (t / 1000) % 60, (t / 100) % 10);
    }
}
EOF_MAIN_JAVA

git init -q -b main
git add -A
git -c user.name="${GIT_AUTHOR_NAME:-$(gh api user -q .login)}" -c user.email="${GIT_AUTHOR_EMAIL:-$(gh api user -q .login)@users.noreply.github.com}" commit -q -m "Video editor app"
gh repo create "$REPO" --private --source=. --push
echo "Pushed. Waiting for GitHub Actions to start the build..."
sleep 15
RUN_ID=$(gh run list --workflow build.yml --limit 1 --json databaseId -q '.[0].databaseId')
gh run watch "$RUN_ID" --exit-status
gh release download --pattern 'VideoEditor.apk' --clobber --dir "$OLDPWD"
echo
echo "DONE  APK saved: $OLDPWD/VideoEditor.apk"
echo "Repo: $(gh repo view --json url -q .url)"
