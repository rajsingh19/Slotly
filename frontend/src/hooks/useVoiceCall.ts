import { useState, useRef, useEffect, useCallback } from 'react';
import { VoiceTranscriptMessage } from '../types';
import { api } from '../services/api';

export type CallStatus = 'idle' | 'connecting' | 'connected' | 'listening' | 'thinking' | 'speaking' | 'error';

export function useVoiceCall() {
  const [callStatus, setCallStatus] = useState<CallStatus>('idle');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<VoiceTranscriptMessage[]>([]);
  const [isMuted, setIsMuted] = useState(false);
  const [audioLevel, setAudioLevel] = useState<number>(0);
  const [lastAction, setLastAction] = useState<{ type: string; payload: any } | null>(null);
  const [callDuration, setCallDuration] = useState<number>(0);

  const socketRef = useRef<WebSocket | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animFrameRef = useRef<number | null>(null);
  const durationTimerRef = useRef<any>(null);
  const speechRecognitionRef = useRef<any>(null);

  // Play incoming base64 WAV/MP3 audio
  const playAudioChunk = useCallback((base64Data: string) => {
    try {
      const binaryString = atob(base64Data);
      const len = binaryString.length;
      const bytes = new Uint8Array(len);
      for (let i = 0; i < len; i++) {
        bytes[i] = binaryString.charCodeAt(i);
      }
      const blob = new Blob([bytes.buffer], { type: 'audio/wav' });
      const audioUrl = URL.createObjectURL(blob);
      const audio = new Audio(audioUrl);
      
      setCallStatus('speaking');
      audio.onended = () => {
        URL.revokeObjectURL(audioUrl);
        setCallStatus('listening');
      };
      audio.play().catch(e => {
        console.warn('Audio playback auto-play restriction:', e);
        setCallStatus('listening');
      });
    } catch (e) {
      console.error('Error decoding/playing audio chunk:', e);
      setCallStatus('listening');
    }
  }, []);

  // Connect WebSocket
  const startCall = useCallback(async (phone?: string) => {
    try {
      setCallStatus('connecting');
      setMessages([]);
      setLastAction(null);
      setCallDuration(0);

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
        // Start duration counter
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
      };

      ws.onclose = () => {
        setCallStatus('idle');
      };

      // 3. Setup Browser Microphone
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
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

        // Optional Browser Speech Recognition for seamless local speech
        const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
        if (SpeechRecognition) {
          const recognition = new SpeechRecognition();
          recognition.continuous = true;
          recognition.interimResults = false;
          recognition.lang = 'en-US';

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

          recognition.start();
          speechRecognitionRef.current = recognition;
        }

      } catch (micErr) {
        console.warn('Microphone access denied or unavailable. Fallback to typed voice simulation mode.', micErr);
        // User can still type prompts or use one-click voice prompt chips
      }

    } catch (err) {
      console.error('Failed to start call:', err);
      setCallStatus('error');
    }
  }, [playAudioChunk]);

  // End call
  const endCall = useCallback(() => {
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
    setIsMuted(prev => !prev);
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
    startCall,
    endCall,
    sendTurn,
    toggleMute,
  };
}
