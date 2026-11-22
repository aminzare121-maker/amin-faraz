package com.amin.support.mobile

import android.content.Context
import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioManager
import android.media.AudioTrack
import android.os.Handler
import android.os.Looper
import com.k2fsa.sherpa.onnx.OfflineTts
import com.k2fsa.sherpa.onnx.OfflineTtsConfig
import com.k2fsa.sherpa.onnx.OfflineTtsModelConfig
import com.k2fsa.sherpa.onnx.OfflineTtsVitsModelConfig
import java.io.File
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicInteger
import kotlin.math.roundToInt

/**
 * TRUE on-device Persian Piper neural TTS; never calls an online speech API.
 * Required model, eSpeak phonemizer and ONNX runtime are IN the offline APK.
 *
 * No promise of ChatGPT voice identity or subjective quality. Model quality is
 * independent of the ChatGPT model which writes the response.
 */
class OfflinePersianTts(context: Context) {
    interface Listener {
        fun finished()
        fun error(reason: String)
    }

    private val app = context.applicationContext
    private val main = Handler(Looper.getMainLooper())
    private val worker = Executors.newSingleThreadExecutor()
    private val generation = AtomicInteger(0)
    private var engine: OfflineTts? = null
    @Volatile private var player: AudioTrack? = null
    @Volatile private var destroyed = false
    @Volatile private var ready = false

    fun isBundled(): Boolean {
        return try {
            app.assets.open("offline_voice/tts/model_fa.onnx").use { it.available() > 10_000_000 } &&
                app.assets.open("offline_voice/tts/tokens_fa.txt").use { it.available() > 100 }
        } catch (e: Exception) {
            false
        }
    }

    fun isReady(): Boolean = ready

    private fun copyAssets(path: String, destination: File) {
        val children = app.assets.list(path) ?: throw IllegalStateException("Missing Persian phonemizer")
        if (children.isEmpty()) {
            destination.parentFile?.mkdirs()
            val tmp = File(destination.parentFile, destination.name + ".partial")
            app.assets.open(path).use { input ->
                tmp.outputStream().use { output -> input.copyTo(output, 128 * 1024) }
            }
            if (destination.exists() && !destination.delete()) {
                tmp.delete()
                throw IllegalStateException("Cannot replace voice model")
            }
            if (!tmp.renameTo(destination)) {
                tmp.delete()
                throw IllegalStateException("Voice asset extraction failed")
            }
        } else {
            destination.mkdirs()
            for (name in children) {
                if (name == "." || name == ".." || name.contains('/')) {
                    throw IllegalStateException("Invalid voice asset path")
                }
                copyAssets("$path/$name", File(destination, name))
            }
        }
    }

    private fun startEngine(): OfflineTts {
        engine?.let { return it }
        val root = File(app.filesDir, "amin_persian_voice/v1")
        val model = File(root, "model_fa.onnx")
        val tokens = File(root, "tokens_fa.txt")
        val phonemizer = File(root, "espeak-ng-data")
        // Do not claim an offline voice exists if a previous extraction failed.
        if (!model.isFile || model.length() < 10_000_000 ||
            !tokens.isFile || !phonemizer.isDirectory ||
            phonemizer.listFiles().isNullOrEmpty()) {
            copyAssets("offline_voice/tts/model_fa.onnx", model)
            copyAssets("offline_voice/tts/tokens_fa.txt", tokens)
            copyAssets("offline_voice/tts/espeak-ng-data", phonemizer)
        }
        val vits = OfflineTtsVitsModelConfig(
            model = model.absolutePath,
            lexicon = "",
            tokens = tokens.absolutePath,
            dataDir = phonemizer.absolutePath,
            noiseScale = 0.667f,
            noiseScaleW = 0.8f,
            lengthScale = 1.0f
        )
        val modelConfig = OfflineTtsModelConfig(
            vits = vits,
            numThreads = 2,
            debug = false,
            provider = "cpu"
        )
        val instance = OfflineTts(config = OfflineTtsConfig(model = modelConfig))
        engine = instance
        ready = true
        return instance
    }

    fun speak(raw: String?, speed: Float, listener: Listener) {
        val text = raw?.trim().orEmpty()
        if (text.isEmpty()) {
            main.post { listener.error("متنی برای پخش وجود ندارد") }
            return
        }
        if (destroyed) {
            main.post { listener.error("موتور صدا بسته شده است") }
            return
        }
        val turn = generation.incrementAndGet()
        player?.pause()
        player?.flush()
        worker.execute {
            var track: AudioTrack? = null
            try {
                if (!isBundled()) throw IllegalStateException("مدل فارسی آفلاین داخل این APK نیست")
                val tts = startEngine()
                val rate = tts.sampleRate()
                if (rate !in 8000..48000) throw IllegalStateException("Invalid Persian TTS sample rate")
                val min = AudioTrack.getMinBufferSize(
                    rate, AudioFormat.CHANNEL_OUT_MONO, AudioFormat.ENCODING_PCM_16BIT)
                val buffer = maxOf(8192, min * 3)
                track = AudioTrack.Builder()
                    .setAudioAttributes(AudioAttributes.Builder()
                        .setUsage(AudioAttributes.USAGE_ASSISTANT)
                        .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build())
                    .setAudioFormat(AudioFormat.Builder()
                        .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                        .setSampleRate(rate)
                        .setChannelMask(AudioFormat.CHANNEL_OUT_MONO).build())
                    .setTransferMode(AudioTrack.MODE_STREAM)
                    .setBufferSizeInBytes(buffer).build()
                if (track.state != AudioTrack.STATE_INITIALIZED) {
                    throw IllegalStateException("Speaker could not initialize")
                }
                player = track
                track.play()
                val normalized = text.replace(Regex("[*_#`]+"), " ")
                    .replace(Regex("https?://\\S+"), "پیوند اینترنتی")
                    .take(2800)
                val sections = normalized.split(Regex("(?<=[.!؟؛،\\n])\\s+"))
                    .filter { it.isNotBlank() }
                for (part in sections) {
                    if (generation.get() != turn || destroyed) break
                    tts.generateWithCallback(part, 0, speed.coerceIn(0.8f, 1.2f)) { samples ->
                        if (generation.get() != turn || destroyed) {
                            0
                        } else {
                            val pcm = ByteArray(samples.size * 2)
                            for (i in samples.indices) {
                                val p = (samples[i].coerceIn(-1f, 1f) * 32767f).roundToInt().toShort()
                                pcm[2 * i] = p.toInt().toByte()
                                pcm[2 * i + 1] = (p.toInt() shr 8).toByte()
                            }
                            var written = 0
                            while (written < pcm.size && generation.get() == turn && !destroyed) {
                                val n = track.write(pcm, written, pcm.size - written)
                                if (n <= 0) break
                                written += n
                            }
                            if (generation.get() == turn && written == pcm.size) 1 else 0
                        }
                    }
                }
                if (generation.get() == turn && !destroyed) {
                    // Finish queued audio before the conversation resumes listening.
                    val playedSamples = track.playbackHeadPosition.toLong() and 0xffffffffL
                    val estimated = (normalized.length * 70L).coerceIn(200L, 1800L)
                    Thread.sleep(estimated)  // bounded tail wait; not a claim of sample-perfect playback
                    main.post { if (!destroyed && generation.get() == turn) listener.finished() }
                }
            } catch (e: Throwable) {
                if (!destroyed && generation.get() == turn) {
                    main.post { listener.error("صدای فارسی آفلاین قابل اجرا نیست: " + e.javaClass.simpleName) }
                }
            } finally {
                if (player === track) player = null
                try { track?.pause(); track?.flush(); track?.release() } catch (_: Throwable) {}
            }
        }
    }

    fun stop() {
        generation.incrementAndGet()
        try { player?.pause(); player?.flush() } catch (_: Exception) {}
    }

    fun release() {
        destroyed = true
        stop()
        worker.execute {
            try { engine?.release() } catch (_: Throwable) {}
            engine = null
            ready = false
        }
        worker.shutdown()
    }
}
