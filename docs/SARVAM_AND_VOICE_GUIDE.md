# Sarvam AI STT & Bulbul TTS Configuration Guide

## 1. Overview

The Hospital Receptionist Voice Agent integrates **Sarvam AI** for Indian and global English speech recognition and expressive voice synthesis.

- **STT (Speech-to-Text)**: Sarvam AI `saarika:v2`
- **TTS (Text-to-Speech)**: Sarvam AI Bulbul `bulbul:v1`

---

## 2. Setting Up Your Sarvam AI API Key

1. Sign up at [Sarvam AI Developer Portal](https://www.sarvam.ai/).
2. Obtain your API subscription key from your dashboard.
3. Open your `.env` file in the project root:
   ```env
   SARVAM_API_KEY=your_actual_sarvam_api_key_here
   SARVAM_STT_LANGUAGE_CODE=en-IN
   SARVAM_TTS_MODEL=bulbul:v1
   SARVAM_TTS_SPEAKER=ananya
   ```
4. Restart the backend service:
   ```bash
   uvicorn app.main:app --reload
   ```

> [!NOTE]
> If `SARVAM_API_KEY` is left blank, the system automatically falls back to the **High-Fidelity Mock & Web Audio Engine**, generating synthetic WAV tones and utilizing browser Web Speech API for 100% zero-cost local development!

---

## 3. Sarvam Speech-to-Text (`saarika:v2`)

- **API Endpoint**: `https://api.sarvam.ai/speech-to-text`
- **Supported Audio Formats**: WAV, MP3, AAC, M4A, OGG
- **Recommended Parameters**:
  - Sample Rate: `16000 Hz` (16 kHz)
  - Bit Depth: `16-bit PCM`
  - Channels: `1` (Mono)
  - Target Language: `en-IN` (Indian English), `hi-IN` (Hindi), `ta-IN` (Tamil), etc.

### Request Sample:
```python
headers = {
    "api-subscription-key": settings.SARVAM_API_KEY
}
files = {
    "file": ("audio.wav", raw_audio_bytes, "audio/wav")
}
data = {
    "language_code": "en-IN",
    "model": "saarika:v2"
}
```

---

## 4. Sarvam Bulbul Text-to-Speech (`bulbul:v1`)

- **API Endpoint**: `https://api.sarvam.ai/text-to-speech`
- **Popular Speakers**:
  - `ananya`: Professional, empathetic female voice (ideal for hospital receptionist)
  - `aditya`: Calm, warm male voice
  - `kavya`: Expressive female tone
- **Features**:
  - `pitch`: Pitch shift adjustment (-1.0 to 1.0)
  - `pace`: Speaking speed (0.8 to 1.5, default `1.0`)
  - `loudness`: Volume multiplier (default `1.2`)
  - `enable_preprocessing`: Normalizes numbers, dates (e.g. "APT-20261105"), and medical terms.

### Request Sample:
```json
{
  "inputs": ["Welcome to Apex Hospital. How can I help you book your consultation today?"],
  "target_language_code": "en-IN",
  "speaker": "ananya",
  "pitch": 0,
  "pace": 1.0,
  "loudness": 1.2,
  "speech_sample_rate": 16000,
  "enable_preprocessing": true,
  "model": "bulbul:v1"
}
```

---

## 5. Latency Optimization Tips

1. **Sentence Streaming**: The voice orchestrator splits dialogue turns at sentence boundaries (`.`, `?`, `!`) to begin synthesizing the first sentence while subsequent clauses are being processed.
2. **Audio Chunk Size**: Use 100ms - 250ms audio frames over WebSocket to minimize buffer buildup.
3. **Local In-Memory Cache**: Cached doctor schedules and hospital FAQs are served with sub-5ms lookup latency.
