#!/usr/bin/env python3
"""
Generate test_audio_pcm.pkl — 30s 16kHz mono float32 from any audio file.
Usage: python3 script/generate_test_audio.py [input.mp3] [output.pkl]

Priority:
  1. librosa (preferred, handles any ffmpeg-supported format)
  2. ffmpeg subprocess → WAV → manual unpack
  3. Original TTS fallback (pyttsx3 / gTTS)
"""
import pickle, io, wave, struct, os, sys, subprocess, tempfile

TARGET_SR = 16000
DURATION_S = 30
OUTPUT_DEFAULT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_audio_pcm.pkl")


def from_audio_file(input_file: str) -> list[float]:
    """Extract 30s at 16kHz mono from any audio format."""
    # --- Method 1: librosa (best) ---
    try:
        import numpy as np
        import librosa
        import soundfile as sf
        audio, sr = librosa.load(input_file, sr=TARGET_SR, mono=True, duration=DURATION_S)
        audio = audio.astype(np.float32)
        pcm = audio.tolist()
        print(f"[librosa] {len(pcm)} samples ({len(pcm)/TARGET_SR:.1f}s)")
        return pcm
    except ImportError:
        pass

    # --- Method 2: ffmpeg → WAV → manual ---
    print("[ffmpeg] decoding...")
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
        tmp_wav = tmp.name
    try:
        subprocess.run([
            'ffmpeg', '-y', '-i', input_file, '-t', str(DURATION_S),
            '-ar', str(TARGET_SR), '-ac', '1', '-f', 'wav', tmp_wav
        ], check=True, capture_output=True)
        with wave.open(tmp_wav, 'rb') as wf:
            n_frames = wf.getnframes()
            raw = wf.readframes(n_frames)
            pcm = [struct.unpack_from('<h', raw, i)[0] / 32768.0 for i in range(0, len(raw), 2)]
        print(f"[ffmpeg] {len(pcm)} samples ({len(pcm)/TARGET_SR:.1f}s)")
        return pcm
    finally:
        os.unlink(tmp_wav)


def from_tts() -> list[float]:
    """Fallback: TTS synthesis."""
    PHRASES = [
        "Hello, this is a test call.",
        "The quick brown fox jumps over the lazy dog.",
        "Testing one two three, audio quality check.",
        "This is a WhatsApp voice over IP test.",
        "If you can hear this clearly, the audio pipeline is working.",
        "Packet loss concealment test in progress.",
        "End of test message. Thank you for listening.",
    ]
    def _wav_to_pcm(wav_bytes):
        with wave.open(io.BytesIO(wav_bytes), 'rb') as wf:
            raw = wf.readframes(wf.getnframes())
        samples = [struct.unpack_from('<h', raw, i)[0] for i in range(0, len(raw), 2)]
        ratio = TARGET_SR / wf.getframerate()
        out_len = int(len(samples) * ratio)
        resampled = []
        for i in range(out_len):
            si = i / ratio; lo, hi = int(si), min(int(si)+1, len(samples)-1)
            frac = si - lo
            resampled.append(samples[lo]*(1-frac) + samples[hi]*frac)
        return [s/32768.0 for s in resampled]

    # pyttsx3
    try:
        import pyttsx3
        engine = pyttsx3.init(); engine.setProperty("rate", 150)
        all_pcm = []
        for phrase in PHRASES:
            tmp = "temp_tts.wav"
            engine.save_to_file(phrase, tmp); engine.runAndWait()
            with open(tmp, 'rb') as f:
                all_pcm.extend(_wav_to_pcm(f.read()))
            os.remove(tmp)
            all_pcm.extend([0.0] * int(TARGET_SR * 0.3))
        return all_pcm
    except ImportError:
        pass

    # gTTS
    try:
        from gtts import gTTS
        mp3_buf = io.BytesIO()
        gTTS(". ".join(PHRASES), lang="en").write_to_fp(mp3_buf)
        mp3_buf.seek(0)
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
            f.write(mp3_buf.read()); mp3_path = f.name
        wav_path = mp3_path.replace('.mp3', '.wav')
        subprocess.run(['ffmpeg','-y','-i',mp3_path,'-ar',str(TARGET_SR),'-ac','1','-sample_fmt','s16',wav_path],
                       capture_output=True, check=True)
        with open(wav_path, 'rb') as f:
            pcm = _wav_to_pcm(f.read())
        os.unlink(mp3_path); os.unlink(wav_path)
        return pcm
    except Exception:
        raise RuntimeError("No TTS engine available. Install pyttsx3, gTTS, or ffmpeg.")


if __name__ == '__main__':
    proj_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    input_file = sys.argv[1] if len(sys.argv) > 1 else os.path.join(proj_root, 'example.mp3')
    output_file = sys.argv[2] if len(sys.argv) > 2 else OUTPUT_DEFAULT

    if os.path.exists(input_file) and input_file.endswith(('.mp3','.wav','.m4a','.ogg','.flac')):
        pcm = from_audio_file(input_file)
    else:
        print(f"No audio file found at {input_file}, falling back to TTS...")
        pcm = from_tts()

    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, 'wb') as f:
        pickle.dump(pcm, f)
    print(f"✅ Saved {output_file}: {len(pcm)} samples ({len(pcm)/TARGET_SR:.1f}s)")
