import { useCallback, useRef, useState } from "react";

const TARGET_SAMPLE_RATE = 16000;

function floatTo16BitPCM(input: Float32Array): ArrayBuffer {
  const buffer = new ArrayBuffer(input.length * 2);
  const view = new DataView(buffer);
  for (let i = 0; i < input.length; i++) {
    const s = Math.max(-1, Math.min(1, input[i]));
    view.setInt16(i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return buffer;
}

function downsample(buffer: Float32Array, inputRate: number, outputRate: number): Float32Array {
  if (outputRate === inputRate) return buffer;
  const ratio = inputRate / outputRate;
  const newLength = Math.round(buffer.length / ratio);
  const result = new Float32Array(newLength);
  let offsetResult = 0;
  let offsetBuffer = 0;
  while (offsetResult < newLength) {
    const nextOffsetBuffer = Math.round((offsetResult + 1) * ratio);
    let accum = 0;
    let count = 0;
    for (let i = offsetBuffer; i < nextOffsetBuffer && i < buffer.length; i++) {
      accum += buffer[i];
      count++;
    }
    result[offsetResult] = count > 0 ? accum / count : 0;
    offsetResult++;
    offsetBuffer = nextOffsetBuffer;
  }
  return result;
}

/**
 * Captures mic audio and delivers ~200ms PCM16 chunks at 16kHz via onChunk,
 * matching AssemblyAI's requirement of 50ms-1000ms binary audio frames.
 * Uses ScriptProcessorNode for broad browser support without extra build
 * config; swap for an AudioWorklet if you need to drop the deprecation
 * warning in a production build.
 */
export function useMicCapture(onChunk: (chunk: ArrayBuffer) => void) {
  const [capturing, setCapturing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [level, setLevel] = useState(0); // 0-1 smoothed amplitude, for a waveform/VU meter
  const ctxRef = useRef<AudioContext | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);

  const start = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
      streamRef.current = stream;
      const ctx = new AudioContext();
      ctxRef.current = ctx;
      await ctx.resume(); // some browsers create it suspended even after a user gesture
      const source = ctx.createMediaStreamSource(stream);
      const processor = ctx.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor;
      processor.onaudioprocess = (e) => {
        const input = e.inputBuffer.getChannelData(0);
        let sumSquares = 0;
        for (let i = 0; i < input.length; i++) sumSquares += input[i] * input[i];
        const rms = Math.sqrt(sumSquares / input.length);
        setLevel((prev) => prev * 0.6 + Math.min(1, rms * 6) * 0.4); // smoothed
        const down = downsample(input, ctx.sampleRate, TARGET_SAMPLE_RATE);
        onChunk(floatTo16BitPCM(down));
      };
      // ScriptProcessorNode only fires onaudioprocess while connected into a
      // path that reaches the destination — but connecting it straight to
      // ctx.destination plays the raw mic input out the speakers live. On
      // any device without headphones that's an audible feedback loop, and
      // the mic then picks its own echo back up mid-sentence, garbling
      // everything AssemblyAI hears after the first word or two. Route
      // through a silent (gain 0) node instead: keeps the graph alive for
      // the browser without ever making sound.
      const silentGain = ctx.createGain();
      silentGain.gain.value = 0;
      source.connect(processor);
      processor.connect(silentGain);
      silentGain.connect(ctx.destination);
      setCapturing(true);
      setError(null);
    } catch (err) {
      setError(
        err instanceof DOMException && err.name === "NotAllowedError"
          ? "Microphone permission denied."
          : "Could not access the microphone."
      );
      setCapturing(false);
    }
  }, [onChunk]);

  const stop = useCallback(() => {
    processorRef.current?.disconnect();
    streamRef.current?.getTracks().forEach((t) => t.stop());
    ctxRef.current?.close();
    processorRef.current = null;
    streamRef.current = null;
    ctxRef.current = null;
    setCapturing(false);
    setLevel(0);
  }, []);

  return { capturing, error, level, start, stop };
}
