package com.example.videoeditor;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.ContentValues;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
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
import androidx.media3.effect.VideoCompositorSettings;
import androidx.media3.common.VideoFrameProcessingException;
import androidx.media3.common.VideoSize;
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
import androidx.media3.exoplayer.ExoPlayer;
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
import java.io.PrintWriter;
import java.io.StringWriter;
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
    private Player player;                       // CompositionPlayer (full) or ExoPlayer (simple)
    private boolean simplePreview = false, forceSimple = false;
    private float simpleAspect = 0f;
    private static final String PREFS = "ve";
    private Transformer transformer;
    private boolean exporting = false, userSeeking = false;

    // ================================================================== lifecycle
    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        installCrashLogger();
        SharedPreferences sp0 = getSharedPreferences(PREFS, MODE_PRIVATE);
        if (sp0.getBoolean("full_preview_pending", false)) {
            // last run died while the full preview was starting -> stay on the simple preview
            sp0.edit().putBoolean("force_simple", true).putBoolean("full_preview_pending", false).commit();
        }
        forceSimple = sp0.getBoolean("force_simple", false);
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
        showPreviousCrash();
    }

    private void installCrashLogger() {
        final Thread.UncaughtExceptionHandler prev = Thread.getDefaultUncaughtExceptionHandler();
        Thread.setDefaultUncaughtExceptionHandler((t, e) -> {
            try {
                StringWriter sw = new StringWriter();
                e.printStackTrace(new PrintWriter(sw));
                getSharedPreferences(PREFS, MODE_PRIVATE).edit()
                        .putString("last_crash", "Thread: " + t.getName() + "\n" + sw).commit();
            } catch (Throwable ignored) { }
            if (prev != null) prev.uncaughtException(t, e);
        });
    }

    private void showPreviousCrash() {
        SharedPreferences sp = getSharedPreferences(PREFS, MODE_PRIVATE);
        final String crash = sp.getString("last_crash", null);
        if (crash == null) return;
        sp.edit().remove("last_crash").commit();
        new AlertDialog.Builder(this)
                .setTitle("The app crashed last time")
                .setMessage(crash.length() > 3500 ? crash.substring(0, 3500) : crash)
                .setPositiveButton("Copy", (d, w) -> {
                    ClipboardManager cm = (ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
                    if (cm != null) cm.setPrimaryClip(ClipData.newPlainText("crash", crash));
                    toast("Crash report copied");
                })
                .setNegativeButton("Close", null)
                .show();
    }

    @Override
    protected void onPause() {
        super.onPause();
        getSharedPreferences(PREFS, MODE_PRIVATE).edit().putBoolean("full_preview_pending", false).apply();
        try { if (player != null) player.pause(); } catch (Throwable ignored) { }
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
        float ar = (simplePreview && simpleAspect > 0f) ? simpleAspect : RATIOS[ratioIdx][0] / RATIOS[ratioIdx][1];
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
            try { if (player.isPlaying()) player.pause(); else player.play(); } catch (Throwable t) { toast("Playback error: " + t); }
        });
        btnPlay.setOnLongClickListener(v -> {
            forceSimple = !forceSimple;
            getSharedPreferences(PREFS, MODE_PRIVATE).edit().putBoolean("force_simple", forceSimple).commit();
            toast(forceSimple ? "Simple preview ON (main video only)" : "Full preview ON (all layers)");
            scheduleRefresh();
            return true;
        });
        seekPlay.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
            @Override public void onProgressChanged(SeekBar s, int p, boolean fromUser) {
                if (fromUser && player != null) seekGlobal(previewTotalMs() * p / 1000L);
            }
            @Override public void onStartTrackingTouch(SeekBar s) { userSeeking = true; }
            @Override public void onStopTrackingTouch(SeekBar s) { userSeeking = false; }
        });
    }

    private final Runnable progressTicker = new Runnable() {
        @Override public void run() {
            try {
                long total = Math.max(1, previewTotalMs());
                if (player != null && !userSeeking) {
                    long pos = Math.min(curPos(), total);
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
            } catch (Throwable ignored) { }
            ui.postDelayed(this, 250);
        }
    };

    private long playhead() { return curPos(); }

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
                    try {
                        r.setDataSource(this, uri);
                        String d = r.extractMetadata(MediaMetadataRetriever.METADATA_KEY_DURATION);
                        long dur = 5000;
                        try { if (d != null) dur = Long.parseLong(d); } catch (NumberFormatException ignored) { }
                        c.srcDurMs = dur > 0 ? dur : 5000;
                        boolean isAudio = (mime != null && mime.startsWith("audio/"))
                                || "yes".equals(r.extractMetadata(MediaMetadataRetriever.METADATA_KEY_HAS_AUDIO)) && r.extractMetadata(MediaMetadataRetriever.METADATA_KEY_HAS_VIDEO) == null;
                        c.type = isAudio ? T_AUDIO : T_VIDEO;
                        if (!isAudio) {
                            try { c.thumb = r.getScaledFrameAtTime(0, MediaMetadataRetriever.OPTION_CLOSEST_SYNC, 160, 160); }
                            catch (Throwable ignored) { }
                        }
                        c.trimStart = 0; c.trimEnd = c.srcDurMs;
                    } finally {
                        try { r.release(); } catch (Throwable ignored) { }
                    }
                }
            } catch (Throwable e) {
                ui.post(() -> toast("Cannot read file: " + e));
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
        long pos = curPos();
        boolean wasPlaying = false;
        try { wasPlaying = player != null && player.isPlaying(); } catch (Throwable ignored) { }
        releasePlayer();
        boolean any = hasMain();
        txtEmpty.setVisibility(any ? View.GONE : View.VISIBLE);
        if (!any) return;
        boolean ok = false;
        if (!forceSimple) ok = startFullPreview();
        if (!ok) ok = startSimplePreview();
        if (!ok) return;
        fitPreview();
        try {
            seekGlobal(Math.min(pos, Math.max(0, previewTotalMs() - 50)));
            if (wasPlaying) player.play();
        } catch (Throwable ignored) { }
    }

    /** Full preview: every layer, effect and text through CompositionPlayer. Falls back automatically. */
    private boolean startFullPreview() {
        final SharedPreferences sp = getSharedPreferences(PREFS, MODE_PRIVATE);
        try {
            Composition comp = buildComposition(PREVIEW_SHORT_SIDE, false);
            if (comp == null) return false;
            sp.edit().putBoolean("full_preview_pending", true).commit();
            final CompositionPlayer cp = new CompositionPlayer.Builder(this).build();
            player = cp;
            simplePreview = false;
            cp.setVideoSurfaceView(surface);
            cp.addListener(new Player.Listener() {
                @Override public void onPlayerError(PlaybackException error) {
                    sp.edit().putBoolean("full_preview_pending", false).commit();
                    if (player == cp) {
                        forceSimple = true;       // this session only
                        toast("Full preview not supported on this phone - using simple preview. Export still has all layers.");
                        ui.post(() -> rebuildPreview());
                    }
                }
                @Override public void onPlaybackStateChanged(int state) {
                    if (state == Player.STATE_READY) sp.edit().putBoolean("full_preview_pending", false).commit();
                }
                @Override public void onIsPlayingChanged(boolean isPlaying) { btnPlay.setText(isPlaying ? "❚❚" : "▶"); }
            });
            cp.setComposition(comp);
            cp.prepare();
            return true;
        } catch (Throwable t) {
            sp.edit().putBoolean("full_preview_pending", false).commit();
            releasePlayer();
            forceSimple = true;                   // this session only
            toast("Full preview unavailable (" + t.getClass().getSimpleName() + ") - using simple preview");
            return false;
        }
    }

    /** Simple preview: main-track videos / photos only, through ExoPlayer. Very stable. */
    private boolean startSimplePreview() {
        try {
            List<MediaItem> items = new ArrayList<>();
            for (Clip c : clips) {
                if (c.track != TR_MAIN) continue;
                MediaItem.Builder mb = new MediaItem.Builder().setUri(c.uri);
                if (c.type == T_IMAGE) {
                    mb.setImageDurationMs(c.durMs);
                } else if (c.trimStart > 0 || c.trimEnd < c.srcDurMs) {
                    mb.setClippingConfiguration(new MediaItem.ClippingConfiguration.Builder()
                            .setStartPositionMs(c.trimStart)
                            .setEndPositionMs(c.trimEnd >= c.srcDurMs ? C.TIME_END_OF_SOURCE : c.trimEnd)
                            .build());
                }
                items.add(mb.build());
            }
            if (items.isEmpty()) return false;
            final ExoPlayer ep = new ExoPlayer.Builder(this).build();
            player = ep;
            simplePreview = true;
            simpleAspect = 0f;
            ep.setVideoSurfaceView(surface);
            ep.addListener(new Player.Listener() {
                @Override public void onPlayerError(PlaybackException error) { toast("Preview: " + error.getMessage()); }
                @Override public void onIsPlayingChanged(boolean isPlaying) { btnPlay.setText(isPlaying ? "❚❚" : "▶"); }
                @Override public void onVideoSizeChanged(VideoSize vs) {
                    if (vs.width > 0 && vs.height > 0) {
                        simpleAspect = vs.width * vs.pixelWidthHeightRatio / vs.height;
                        fitPreview();
                    }
                }
            });
            ep.setMediaItems(items);
            ep.prepare();
            return true;
        } catch (Throwable t) {
            releasePlayer();
            toast("Preview unavailable: " + t);
            return false;
        }
    }

    private void releasePlayer() {
        if (player != null) {
            Player p = player;
            player = null;
            try { p.release(); } catch (Throwable ignored) { }
            btnPlay.setText("▶");
        }
        simplePreview = false;
        simpleAspect = 0f;
    }

    // ---- position helpers (simple preview plays one item at a time, so positions are mapped)
    private long rawMs(Clip c) { return c.type == T_IMAGE ? c.durMs : Math.max(1, c.trimEnd - c.trimStart); }

    private long previewTotalMs() {
        if (!simplePreview || player == null) return totalMs();
        long sum = 0;
        for (Clip c : clips) if (c.track == TR_MAIN) sum += rawMs(c);
        return Math.max(1, sum);
    }

    private long curPos() {
        try {
            if (player == null) return 0;
            long cur = Math.max(0, player.getCurrentPosition());
            if (!simplePreview) return cur;
            int idx = player.getCurrentMediaItemIndex(), i = 0;
            long acc = 0;
            for (Clip c : clips) {
                if (c.track != TR_MAIN) continue;
                if (i >= idx) break;
                acc += rawMs(c);
                i++;
            }
            return acc + cur;
        } catch (Throwable t) {
            return 0;
        }
    }

    private void seekGlobal(long ms) {
        try {
            if (player == null) return;
            if (!simplePreview) { player.seekTo(Math.max(0, ms)); return; }
            long acc = 0;
            int i = 0, last = 0;
            long lastLen = 0;
            for (Clip c : clips) {
                if (c.track != TR_MAIN) continue;
                long e = rawMs(c);
                if (ms < acc + e) { player.seekTo(i, Math.max(0, ms - acc)); return; }
                acc += e; last = i; lastLen = e; i++;
            }
            player.seekTo(last, Math.max(0, lastLen - 1));
        } catch (Throwable ignored) { }
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
        try {
            transformer.start(comp, out.getAbsolutePath());
        } catch (Throwable t) {
            finishExport();
            txtExportStatus.setText("Export failed: " + t);
            scheduleRefresh();
        }
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
