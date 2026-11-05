import { useState, useRef, useEffect, useCallback } from 'react';
import { VoiceTranscriptMessage } from '../types';
import { api } from '../services/api';

export type CallStatus = 'idle' | 'connecting' | 'connected' | 'listening' | 'recording' | 'thinking' | 'speaking' | 'error';

export function useVoiceCall() {
  const [callStatus, setCallStatus] = useState<CallStatus>('idle');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<VoiceTranscriptMessage[]>([]);
  const [isMuted, setIsMuted] = useState(false);
  const [audioLevel, setAudioLevel] = useState<number>(0);
  const [lastAction, setLastAction] = useState<{ type: string; payload: any } | null>(null);
  const [callDuration, setCallDuration] = useState<number>(0);
  const [micPermissionDenied, setMicPermissionDenied] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isRecording, setIsRecording] = useState<boolean>(false);

  const socketRef = useRef<WebSocket | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animFrameRef = useRef<number | null>(null);
  const durationTimerRef = useRef<any>(null);
  const speechRecognitionRef = useRef<any>(null);

  // Audio Playback Queue for smooth sentence-boundary streaming
  const audioQueueRef = useRef<string[]>([]);
  const isPlayingRef = useRef<boolean>(false);
  const currentAudioRef = useRef<HTMLAudioElement | null>(null);

  const processAudioQueue = useCallback(() => {
    if (isPlayingRef.current || audioQueueRef.current.length === 0) {
      if (!isPlayingRef.current && audioQueueRef.current.length === 0) {
        setCallStatus(prev => (prev === 'speaking' ? 'listening' : prev));
      }
      return;
    }

    const nextBase64 = audioQueueRef.current.shift();
    if (!nextBase64) return;

    try {
      isPlayingRef.current = true;
      setCallStatus('speaking');

      const binaryString = atob(nextBase64);
      const len = binaryString.length;
      const bytes = new Uint8Array(len);
      for (let i = 0; i < len; i++) {
        bytes[i] = binaryString.charCodeAt(i);
      }
      const blob = new Blob([bytes.buffer], { type: 'audio/wav' });
      const audioUrl = URL.createObjectURL(blob);
      const audio = new Audio(audioUrl);
      currentAudioRef.current = audio;

      audio.onended = () => {
        URL.revokeObjectURL(audioUrl);
        currentAudioRef.current = null;
        isPlayingRef.current = false;
        processAudioQueue();
      };

      audio.onerror = (e) => {
        console.warn('Audio playback error, skipping chunk:', e);
        URL.revokeObjectURL(audioUrl);
        currentAudioRef.current = null;
        isPlayingRef.current = false;
        processAudioQueue();
      };

      audio.play().catch(e => {
        console.warn('Audio autoplay prevented or error:', e);
        URL.revokeObjectURL(audioUrl);
        currentAudioRef.current = null;
        isPlayingRef.current = false;
        processAudioQueue();
      });
    } catch (e) {
      console.error('Error decoding audio chunk:', e);
      isPlayingRef.current = false;
      processAudioQueue();
    }
  }, []);

  const playAudioChunk = useCallback((base64Data: string) => {
    audioQueueRef.current.push(base64Data);
    processAudioQueue();
  }, [processAudioQueue]);

  // Connect WebSocket & Setup Media
  const startCall = useCallback(async (phone?: string) => {
    try {
      setCallStatus('connecting');
      setMessages([]);
      setLastAction(null);
      setCallDuration(0);
      setErrorMessage(null);
      setMicPermissionDenied(false);

      // 1. Initialize session via REST
      const session = await api.createVoiceSession(phone);
      setSessionId(session.session_id);

      // 2. Connect WebSocket
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${protocol}//${window.location.host}/api/v1/voice/ws/${session.session_id}`;
      const ws = new WebSocket(wsUrl);
      socketRef.current = ws;

      ws.onopen = () => {
        setCallStatus('connected');
        durationTimerRef.current = setInterval(() => {
          setCallDuration(prev => prev + 1);
        }, 1000);
      };

      ws.onmessage = (event) => {
        try {
          const frame = JSON.parse(event.data);

          if (frame.type === 'text') {
            const newMsg: VoiceTranscriptMessage = {
              id: `msg-${Date.now()}-${Math.random()}`,
              speaker: frame.role || 'assistant',
              message: frame.data || '',
              timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
              latency_ms: frame.latency_ms,
              provider: frame.provider,
              action_type: frame.action_type,
              action_payload: frame.action_payload,
            };
            setMessages(prev => [...prev, newMsg]);

            if (frame.action_type) {
              setLastAction({ type: frame.action_type, payload: frame.action_payload });
            }
          } else if (frame.type === 'audio' && frame.data) {
            playAudioChunk(frame.data);
          }
        } catch (e) {
          console.error('Failed to parse WebSocket message:', e);
        }
      };

      ws.onerror = (err) => {
        console.error('WebSocket voice error:', err);
        setCallStatus('error');
        setErrorMessage('Voice WebSocket connection encountered an error.');
      };

      ws.onclose = () => {
        setCallStatus('idle');
      };

      // 3. Setup Browser Microphone
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaStreamRef.current = stream;

        const audioCtx = new (window.AudioContext || (window as any).webkitAudioContext)();
        audioContextRef.current = audioCtx;
        const source = audioCtx.createMediaStreamSource(stream);
        const analyser = audioCtx.createAnalyser();
        analyser.fftSize = 64;
        source.connect(analyser);
        analyserRef.current = analyser;

        // Waveform level ticker
        const dataArray = new Uint8Array(analyser.frequencyBinCount);
        const updateLevel = () => {
          analyser.getByteFrequencyData(dataArray);
          let sum = 0;
          for (let i = 0; i < dataArray.length; i++) {
            sum += dataArray[i];
          }
          const avg = sum / dataArray.length;
          setAudioLevel(Math.min(100, Math.round(avg * 1.5)));
          animFrameRef.current = requestAnimationFrame(updateLevel);
        };
        updateLevel();

        // Setup MediaRecorder for pushing voice packets to backend
        try {
          const recorder = new MediaRecorder(stream);
          mediaRecorderRef.current = recorder;

          recorder.ondataavailable = (e) => {
            if (e.data.size > 0) {
              audioChunksRef.current.push(e.data);
            }
          };

          recorder.onstop = async () => {
            if (audioChunksRef.current.length > 0) {
              const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/wav' });
              audioChunksRef.current = [];
              const reader = new FileReader();
              reader.onloadend = () => {
                const base64Audio = (reader.result as string).split(',')[1];
                if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN && base64Audio) {
                  setCallStatus('thinking');
                  socketRef.current.send(JSON.stringify({
                    type: 'audio',
                    data: base64Audio,
                    format: 'wav'
                  }));
                }
              };
              reader.readAsDataURL(audioBlob);
            }
            setIsRecording(false);
          };
        } catch (recErr) {
          console.warn('MediaRecorder not available or failed:', recErr);
        }

        // Web Speech Recognition for continuous transcription
        const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
        if (SpeechRecognition) {
          const recognition = new SpeechRecognition();
          recognition.continuous = true;
          recognition.interimResults = false;
          recognition.lang = 'en-IN';

          recognition.onresult = (e: any) => {
            const transcript = e.results[e.results.length - 1][0].transcript.trim();
            if (transcript && ws.readyState === WebSocket.OPEN) {
              setCallStatus('thinking');
              ws.send(JSON.stringify({ type: 'text', data: transcript, role: 'user' }));
            }
          };

          recognition.onerror = (e: any) => {
            console.warn('Speech recognition warning:', e.error);
          };

          try {
            recognition.start();
            speechRecognitionRef.current = recognition;
          } catch (e) {}
        }

      } catch (micErr: any) {
        console.warn('Microphone access denied or unavailable:', micErr);
        setMicPermissionDenied(true);
        setErrorMessage('Microphone access denied. You can continue speaking via text or simulate voice turns.');
      }

    } catch (err: any) {
      console.error('Failed to start call:', err);
      setCallStatus('error');
      setErrorMessage(err.message || 'Failed to start voice session');
    }
  }, [playAudioChunk]);

  // Start / Stop manual audio recording turn
  const startRecordingAudio = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'inactive') {
      audioChunksRef.current = [];
      mediaRecorderRef.current.start();
      setIsRecording(true);
      setCallStatus('recording');
    }
  }, []);

  const stopRecordingAudio = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      mediaRecorderRef.current.stop();
    }
  }, []);

  // End call
  const endCall = useCallback(() => {
    // Clear audio playback queue
    audioQueueRef.current = [];
    if (currentAudioRef.current) {
      try {
        currentAudioRef.current.pause();
        currentAudioRef.current = null;
      } catch (e) {}
    }
    isPlayingRef.current = false;

    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      try { mediaRecorderRef.current.stop(); } catch (e) {}
    }

    if (socketRef.current) {
      try {
        socketRef.current.send(JSON.stringify({ type: 'control', data: 'HANGUP' }));
        socketRef.current.close();
      } catch (e) {}
      socketRef.current = null;
    }

    if (speechRecognitionRef.current) {
      try { speechRecognitionRef.current.stop(); } catch (e) {}
      speechRecognitionRef.current = null;
    }

    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach(track => track.stop());
      mediaStreamRef.current = null;
    }

    if (animFrameRef.current) {
      cancelAnimationFrame(animFrameRef.current);
      animFrameRef.current = null;
    }

    if (audioContextRef.current) {
      audioContextRef.current.close().catch(() => {});
      audioContextRef.current = null;
    }

    if (durationTimerRef.current) {
      clearInterval(durationTimerRef.current);
      durationTimerRef.current = null;
    }

    setCallStatus('idle');
    setAudioLevel(0);
    setIsRecording(false);
  }, []);

  // Send a text speech turn (works via WebSocket or REST)
  const sendTurn = useCallback(async (text: string) => {
    if (!text.trim()) return;

    if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
      setCallStatus('thinking');
      socketRef.current.send(JSON.stringify({
        type: 'text',
        data: text,
        role: 'user',
      }));
    } else if (sessionId) {
      // REST fallback
      setCallStatus('thinking');
      try {
        const res = await api.simulateTurn(sessionId, text);
        setMessages(prev => [
          ...prev,
          {
            id: `msg-${Date.now()}-u`,
            speaker: 'user',
            message: text,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          },
          {
            id: `msg-${Date.now()}-a`,
            speaker: 'assistant',
            message: res.assistant_reply,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          }
        ]);
        setCallStatus('listening');
      } catch (e) {
        setCallStatus('error');
      }
    }
  }, [sessionId]);

  const toggleMute = () => {
    setIsMuted(prev => {
      const next = !prev;
      if (mediaStreamRef.current) {
        mediaStreamRef.current.getAudioTracks().forEach(track => {
          track.enabled = !next;
        });
      }
      return next;
    });
  };

  useEffect(() => {
    return () => {
      endCall();
    };
  }, [endCall]);

  return {
    callStatus,
    sessionId,
    messages,
    isMuted,
    audioLevel,
    lastAction,
    callDuration,
    micPermissionDenied,
    errorMessage,
    isRecording,
    startCall,
    endCall,
    sendTurn,
    toggleMute,
    startRecordingAudio,
    stopRecordingAudio,
  };
}
