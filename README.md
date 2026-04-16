# 📱 HTML → Signed APK/AAB Builder

Auto-build a signed Android APK or AAB from any `index.html` or `index.zip` using GitHub Actions. No Android Studio needed — just fill in prompts in the browser.

---

## 🚀 How to Use

### Step 1 — Set up the repository

```
your-repo/
├── .github/
│   └── workflows/
│       └── build-apk.yml     ← the workflow file
├── index.html                ← your web app (OR index.zip)
└── README.md
```

Upload either:
- **`index.html`** — single file app
- **`index.zip`** — multi-file app (HTML + CSS + JS + assets)

---

### Step 2 — Trigger the build

1. Go to your GitHub repo → **Actions** tab
2. Click **"🚀 Build Signed APK / AAB from HTML"**
3. Click **"Run workflow"**
4. Fill in the prompts:

| Prompt | Example | Description |
|--------|---------|-------------|
| 📱 App Name | `Picture Dictionary` | Display name on phone |
| 📦 Package Name | `com.abhay.dictionary` | Unique app ID (reverse domain) |
| 🔢 Version Name | `1.0.0` | Human-readable version |
| 🔢 Version Code | `1` | Integer, increment each release |
| 📦 Build Type | `APK` / `AAB` / `BOTH` | APK = sideload, AAB = Play Store |
| 📱 Min SDK | `21` | Android 5.0+ recommended |
| 📐 Orientation | `unspecified` / `portrait` / `landscape` | Screen lock |
| 🎨 Theme Color | `#ff6f61` | App icon background color |
| 🔑 Keystore Password | `mypass123` | Min 6 characters |
| 🔑 Key Alias | `mykey` | Name for your signing key |
| 🔑 Key Password | `mypass123` | Can be same as keystore password |
| 📅 Validity Years | `25` | How long the key is valid |
| 👤 Certificate CN | `Your Name` | Your name or organization |

5. Click **"Run workflow"** → wait ~5–10 minutes
6. Download signed APK/AAB from the **Artifacts** section ✅

---

### Step 3 — Auto-build on push (optional)

The workflow also auto-triggers whenever you push a new `index.html` or `index.zip`.  
For auto-builds, store your keystore credentials as **GitHub Secrets**:

Go to **Settings → Secrets and variables → Actions → New repository secret**:

| Secret Name | Value |
|-------------|-------|
| `KEYSTORE_PASSWORD` | your keystore password |
| `KEY_PASSWORD` | your key password |

---

## 🔒 Keystore Tips

> **IMPORTANT:** Save your keystore credentials safely!  
> If you lose them, you cannot update your app on Play Store.

- Use the same keystore for all future updates of the same app
- After first build, download the `keystore.jks` from the build logs or store the credentials in GitHub Secrets
- For Play Store: use **AAB** format
- For direct install / sideloading: use **APK** format

---

## ⚙️ What the Workflow Does

```
index.html / index.zip
        ↓
  Extract web assets
        ↓
  Generate app icon (from theme color)
        ↓
  Create Android project
  (WebView wraps your HTML)
        ↓
  Generate signing keystore
        ↓
  Gradle build (release)
        ↓
  Signed APK / AAB output
        ↓
  Upload as GitHub Artifact ✅
```

---

## 🌐 Supported HTML Features

Your HTML app has full access to:

| Feature | Support |
|---------|---------|
| JavaScript | ✅ Full |
| Web Speech API | ✅ (mic permission included) |
| File Upload | ✅ (file chooser built-in) |
| File Download | ✅ |
| LocalStorage / IndexedDB | ✅ |
| SQL.js / WASM | ✅ |
| PDF.js | ✅ |
| External CDN scripts | ✅ (internet permission included) |
| Camera / Mic | ✅ (permissions included) |

---

## 📦 Package Name Rules

- Must be unique (like a reverse domain name)
- Only letters, numbers, and dots
- At least 2 segments: `com.yourname.appname`
- Examples:
  - `com.abhay.dictionary`
  - `in.myschool.quizapp`
  - `org.myproject.tool`

---

## ❓ FAQ

**Q: Can I update the app later?**  
A: Yes — use the same Package Name, increment Version Code, and use the same keystore credentials.

**Q: Can I publish to Play Store?**  
A: Yes — choose **AAB** output and upload the `.aab` file.

**Q: My zip has many files, will they all be included?**  
A: Yes — all files inside the zip are bundled into the app assets.

**Q: Where is the keystore saved?**  
A: It's generated fresh each build. For production apps, store `KS_PASSWORD` and `KEY_PASSWORD` as GitHub Secrets to reuse them.
