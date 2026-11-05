import React, { useState, useEffect, useRef } from 'react';
import {
  Phone,
  PhoneOff,
  Mic,
  MicOff,
  Sparkles,
  Bot,
  User,
  Clock,
  CheckCircle2,
  AlertTriangle,
  Send,
  CalendarCheck,
  CalendarX,
  Volume2,
  Radio
} from 'lucide-react';
import { useVoiceCall } from '../hooks/useVoiceCall';

interface VoiceConsoleProps {
  onAppointmentUpdated?: () => void;
}

export const VoiceConsole: React.FC<VoiceConsoleProps> = ({ onAppointmentUpdated }) => {
  const {
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
  } = useVoiceCall();

  const [callerPhone, setCallerPhone] = useState('+91-98765-43210');
  const [typedMessage, setTypedMessage] = useState('');
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    if (lastAction && (lastAction.type === 'BOOKING_CONFIRMED' || lastAction.type === 'APPOINTMENT_CANCELLED' || lastAction.type === 'APPOINTMENT_RESCHEDULED')) {
      onAppointmentUpdated?.();
    }
  }, [lastAction, onAppointmentUpdated]);

  const handleSendText = (e: React.FormEvent) => {
    e.preventDefault();
    if (!typedMessage.trim()) return;
    sendTurn(typedMessage.trim());
    setTypedMessage('');
  };

  const formatSeconds = (sec: number) => {
    const mins = Math.floor(sec / 60);
    const s = sec % 60;
    return `${mins.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  const suggestedPrompts = [
    'Mujhe skin doctor ko dikhana hai',
    'Check availability for Cardiology tomorrow',
    'Book appointment with Dr. Sharma for general checkup',
    'What are the visiting hours for general wards?',
    'I need to cancel my appointment',
    'Patient has sudden severe chest pain',
  ];

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
      {/* Voice Control & Status Panel */}
      <div className="lg:col-span-5 flex flex-col gap-6">
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl relative overflow-hidden">
          {/* Background Ambient Glow */}
          <div
            className={`absolute -top-24 -left-24 w-64 h-64 rounded-full blur-3xl pointer-events-none transition-all duration-700 ${
              callStatus === 'speaking'
                ? 'bg-sky-500/20'
                : callStatus === 'recording'
                ? 'bg-rose-500/25'
                : callStatus === 'listening'
                ? 'bg-emerald-500/20'
                : callStatus === 'thinking'
                ? 'bg-amber-500/20'
                : 'bg-indigo-500/10'
            }`}
          />

          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                Reception Voice Agent
              </span>
              <span
                className={`px-2 py-0.5 rounded-full text-[11px] font-medium capitalize ${
                  callStatus === 'connected' || callStatus === 'listening'
                    ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                    : callStatus === 'speaking'
                    ? 'bg-sky-500/10 text-sky-400 border border-sky-500/20 animate-pulse'
                    : callStatus === 'recording'
                    ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20 animate-pulse'
                    : callStatus === 'thinking'
                    ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                    : callStatus === 'error'
                    ? 'bg-red-500/10 text-red-400 border border-red-500/20'
                    : 'bg-slate-800 text-slate-400'
                }`}
              >
                ● {callStatus}
              </span>
            </div>

            {callStatus !== 'idle' && (
              <div className="flex items-center gap-1.5 text-xs text-slate-400 font-mono bg-slate-800/60 px-2.5 py-1 rounded-full border border-slate-700/50">
                <Clock className="w-3.5 h-3.5 text-slate-400" />
                <span>{formatSeconds(callDuration)}</span>
              </div>
            )}
          </div>

          {/* Microphone Permission Warning Banner */}
          {micPermissionDenied && (
            <div className="mb-4 p-3 bg-amber-500/10 border border-amber-500/30 rounded-xl flex items-start gap-2.5 text-amber-200 text-xs">
              <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
              <div>
                <p className="font-medium">Microphone Permission Blocked</p>
                <p className="opacity-90 mt-0.5">
                  Microphone is unavailable or blocked in browser settings. You can still use the text input below to test full voice agent workflows.
                </p>
              </div>
            </div>
          )}

          {/* General Error Banner */}
          {errorMessage && !micPermissionDenied && (
            <div className="mb-4 p-3 bg-red-500/10 border border-red-500/30 rounded-xl flex items-start gap-2.5 text-red-200 text-xs">
              <AlertTriangle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
              <div>
                <p className="font-medium">Connection Notice</p>
                <p className="opacity-90 mt-0.5">{errorMessage}</p>
              </div>
            </div>
          )}

          {/* Central AI Avatar / Waveform Visualizer */}
          <div className="py-6 flex flex-col items-center justify-center">
            <div className="relative">
              <div
                className={`w-28 h-28 rounded-full flex items-center justify-center transition-all duration-300 ${
                  callStatus === 'speaking'
                    ? 'bg-gradient-to-tr from-sky-500 to-indigo-500 shadow-2xl shadow-sky-500/40 ring-4 ring-sky-400/30 scale-105'
                    : callStatus === 'recording'
                    ? 'bg-gradient-to-tr from-rose-500 to-pink-600 shadow-2xl shadow-rose-500/40 ring-4 ring-rose-400/30 scale-105'
                    : callStatus === 'listening'
                    ? 'bg-gradient-to-tr from-emerald-500 to-teal-500 shadow-xl shadow-emerald-500/20'
                    : callStatus === 'thinking'
                    ? 'bg-gradient-to-tr from-amber-500 to-orange-500 animate-pulse shadow-xl shadow-amber-500/20'
                    : 'bg-slate-800 border border-slate-700'
                }`}
              >
                {callStatus === 'speaking' ? (
                  <Volume2 className="w-12 h-12 text-white animate-pulse" />
                ) : callStatus === 'recording' ? (
                  <Radio className="w-12 h-12 text-white animate-pulse" />
                ) : callStatus === 'listening' ? (
                  <Mic className="w-12 h-12 text-white" />
                ) : callStatus === 'thinking' ? (
                  <Sparkles className="w-12 h-12 text-white animate-spin" />
                ) : (
                  <Bot className="w-12 h-12 text-slate-400" />
                )}
              </div>

              {/* Pulsing rings when speaking or recording */}
              {(callStatus === 'speaking' || callStatus === 'recording') && (
                <div
                  className={`absolute inset-0 rounded-full animate-ping pointer-events-none opacity-25 ${
                    callStatus === 'speaking' ? 'bg-sky-400' : 'bg-rose-400'
                  }`}
                />
              )}
            </div>

            {/* Speaking / Listening State Text */}
            <p className="mt-4 font-medium text-sm text-slate-200">
              {callStatus === 'speaking' && 'Maya is speaking...'}
              {callStatus === 'recording' && 'Recording microphone audio...'}
              {callStatus === 'listening' && (isMuted ? 'Microphone muted' : 'Listening for your voice...')}
              {callStatus === 'thinking' && 'Processing your request...'}
              {callStatus === 'connected' && 'Call connected'}
              {callStatus === 'connecting' && 'Establishing WebSocket call...'}
              {callStatus === 'idle' && 'AI Receptionist Ready'}
              {callStatus === 'error' && 'Session interrupted'}
            </p>

            {/* Audio Waveform Meter */}
            {callStatus !== 'idle' && (
              <div className="w-full max-w-xs mt-3 flex items-center gap-1.5 justify-center">
                <span className="text-[10px] text-slate-500 font-mono">MIC</span>
                <div className="flex-1 h-2 bg-slate-800 rounded-full overflow-hidden p-0.5 border border-slate-700">
                  <div
                    className="h-full bg-gradient-to-r from-emerald-500 via-sky-500 to-indigo-500 rounded-full transition-all duration-75"
                    style={{ width: `${Math.min(100, Math.max(8, audioLevel))}%` }}
                  />
                </div>
                <span className="text-[10px] text-slate-400 font-mono w-6 text-right">{audioLevel}%</span>
              </div>
            )}
          </div>

          {/* Caller Details & Controls */}
          <div className="mt-4 pt-4 border-t border-slate-800/80">
            {callStatus === 'idle' && (
              <div className="mb-4">
                <label className="block text-xs font-medium text-slate-400 mb-1.5">
                  Caller Phone Number (for Patient Lookup/Registration)
                </label>
                <input
                  type="text"
                  value={callerPhone}
                  onChange={(e) => setCallerPhone(e.target.value)}
                  placeholder="+91-98765-43210"
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-sky-500"
                />
              </div>
            )}

            <div className="flex flex-col gap-2.5">
              <div className="flex items-center gap-3">
                {callStatus === 'idle' ? (
                  <button
                    onClick={() => startCall(callerPhone)}
                    className="flex-1 py-3 px-4 rounded-xl bg-gradient-to-r from-sky-500 to-indigo-600 hover:from-sky-400 hover:to-indigo-500 text-white font-medium flex items-center justify-center gap-2 shadow-lg shadow-sky-500/25 transition-all transform active:scale-[0.98]"
                  >
                    <Phone className="w-5 h-5" />
                    <span>Start AI Reception Call</span>
                  </button>
                ) : (
                  <>
                    <button
                      onClick={toggleMute}
                      className={`p-3 rounded-xl border transition-colors ${
                        isMuted
                          ? 'bg-red-500/10 border-red-500/30 text-red-400'
                          : 'bg-slate-800 border-slate-700 text-slate-300 hover:text-white'
                      }`}
                      title={isMuted ? 'Unmute' : 'Mute'}
                    >
                      {isMuted ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
                    </button>

                    <button
                      onClick={endCall}
                      className="flex-1 py-3 px-4 rounded-xl bg-red-600 hover:bg-red-500 text-white font-medium flex items-center justify-center gap-2 shadow-lg shadow-red-500/25 transition-all"
                    >
                      <PhoneOff className="w-5 h-5" />
                      <span>End Call</span>
                    </button>
                  </>
                )}
              </div>

              {/* Push-to-talk live mic recording button when call is active */}
              {callStatus !== 'idle' && (
                <button
                  onMouseDown={startRecordingAudio}
                  onMouseUp={stopRecordingAudio}
                  onTouchStart={startRecordingAudio}
                  onTouchEnd={stopRecordingAudio}
                  className={`w-full py-2.5 px-3 rounded-xl border text-xs font-semibold flex items-center justify-center gap-2 transition-all ${
                    isRecording
                      ? 'bg-rose-600 text-white border-rose-500 shadow-lg shadow-rose-500/30 scale-[0.99]'
                      : 'bg-slate-800/90 hover:bg-slate-800 text-slate-200 border-slate-700'
                  }`}
                >
                  <Radio className={`w-3.5 h-3.5 ${isRecording ? 'text-white animate-pulse' : 'text-rose-400'}`} />
                  <span>{isRecording ? 'Release to Send Voice Audio' : 'Hold to Speak (Live Mic)'}</span>
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Action Result Notification Card */}
        {lastAction && (
          <div
            className={`p-4 rounded-xl border transition-all ${
              lastAction.type === 'BOOKING_CONFIRMED' || lastAction.type === 'BOOKING_SUCCESS'
                ? 'bg-emerald-950/40 border-emerald-700/60 text-emerald-200'
                : lastAction.type === 'APPOINTMENT_CANCELLED'
                ? 'bg-amber-950/40 border-amber-700/60 text-amber-200'
                : 'bg-sky-950/40 border-sky-700/60 text-sky-200'
            }`}
          >
            <div className="flex items-start gap-3">
              {(lastAction.type === 'BOOKING_CONFIRMED' || lastAction.type === 'BOOKING_SUCCESS') && (
                <CalendarCheck className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />
              )}
              {lastAction.type === 'APPOINTMENT_CANCELLED' && (
                <CalendarX className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
              )}
              {lastAction.type === 'DOCTORS_FOUND' && (
                <CheckCircle2 className="w-5 h-5 text-sky-400 shrink-0 mt-0.5" />
              )}

              <div>
                <p className="font-semibold text-sm">
                  {(lastAction.type === 'BOOKING_CONFIRMED' || lastAction.type === 'BOOKING_SUCCESS') && 'Appointment Confirmed!'}
                  {lastAction.type === 'APPOINTMENT_CANCELLED' && 'Appointment Cancelled'}
                  {lastAction.type === 'APPOINTMENT_RESCHEDULED' && 'Appointment Rescheduled'}
                  {lastAction.type === 'DOCTORS_FOUND' && 'Available Doctors Found'}
                </p>
                <p className="text-xs opacity-90 mt-0.5">
                  {(lastAction.payload?.appointment_number || lastAction.payload?.booking_reference) && (
                    `Ref: ${lastAction.payload?.appointment_number || lastAction.payload?.booking_reference} • `
                  )}
                  {lastAction.payload?.doctor_name && `With ${lastAction.payload.doctor_name} • `}
                  {lastAction.payload?.time && `${lastAction.payload.time}`}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Suggested Voice Prompts */}
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4">
          <div className="flex items-center gap-2 mb-3 text-xs font-semibold text-slate-400 uppercase tracking-wider">
            <Sparkles className="w-3.5 h-3.5 text-sky-400" />
            <span>Suggested Voice Queries (Click to Speak/Simulate)</span>
          </div>
          <div className="flex flex-col gap-2">
            {suggestedPrompts.map((prompt, i) => (
              <button
                key={i}
                onClick={() => {
                  if (callStatus === 'idle') {
                    startCall(callerPhone).then(() => {
                      setTimeout(() => sendTurn(prompt), 800);
                    });
                  } else {
                    sendTurn(prompt);
                  }
                }}
                className="text-left text-xs bg-slate-800/80 hover:bg-slate-800 border border-slate-700/60 hover:border-sky-500/40 text-slate-300 hover:text-white px-3 py-2 rounded-lg transition-all"
              >
                "{prompt}"
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Real-time Transcription & Conversation Log */}
      <div className="lg:col-span-7 flex flex-col bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-xl h-[650px]">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-900/60">
          <div className="flex items-center gap-2">
            <Volume2 className="w-4 h-4 text-sky-400" />
            <h4 className="font-semibold text-sm text-white">Live Conversation Transcript</h4>
          </div>
          <span className="text-xs text-slate-500 font-mono">
            {sessionId ? `Session: ${sessionId}` : 'Awaiting Call'}
          </span>
        </div>

        {/* Messages Scroll Area */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-slate-500 text-center px-4">
              <Bot className="w-12 h-12 text-slate-700 mb-3" />
              <p className="text-sm font-medium text-slate-400">No active conversation yet</p>
              <p className="text-xs text-slate-500 max-w-sm mt-1">
                Start a call or click any suggested prompt on the left to talk with the AI receptionist.
              </p>
            </div>
          ) : (
            messages.map((m) => {
              const isAssistant = m.speaker === 'assistant';
              return (
                <div
                  key={m.id}
                  className={`flex gap-3 max-w-[85%] ${isAssistant ? 'self-start' : 'self-end ml-auto flex-row-reverse'}`}
                >
                  <div
                    className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 text-xs font-semibold ${
                      isAssistant
                        ? 'bg-sky-500/20 text-sky-300 border border-sky-500/30'
                        : 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/30'
                    }`}
                  >
                    {isAssistant ? <Bot className="w-4 h-4" /> : <User className="w-4 h-4" />}
                  </div>

                  <div>
                    <div
                      className={`p-3.5 rounded-2xl text-sm leading-relaxed ${
                        isAssistant
                          ? 'bg-slate-800/90 text-slate-100 rounded-tl-none border border-slate-700/60'
                          : 'bg-indigo-600 text-white rounded-tr-none shadow-md'
                      }`}
                    >
                      {m.message}
                    </div>

                    <div
                      className={`flex items-center gap-2 mt-1 text-[11px] text-slate-500 ${
                        isAssistant ? '' : 'justify-end'
                      }`}
                    >
                      <span>{m.timestamp}</span>
                      {m.latency_ms && (
                        <span className="text-emerald-400 font-mono">
                          ⚡ {Math.round(m.latency_ms)}ms
                        </span>
                      )}
                      {m.provider && (
                        <span className="px-1.5 py-0.5 rounded bg-slate-800 border border-slate-700 text-slate-300 font-mono text-[10px]">
                          {m.provider}
                        </span>
                      )}
                      {m.action_type && (
                        <span className="px-1.5 py-0.5 rounded bg-sky-500/20 text-sky-300 font-mono text-[10px]">
                          {m.action_type}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              );
            })
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Bar (for typed speech simulation / silent input) */}
        <div className="p-4 border-t border-slate-800 bg-slate-900/80">
          <form onSubmit={handleSendText} className="flex items-center gap-2">
            <input
              type="text"
              value={typedMessage}
              onChange={(e) => setTypedMessage(e.target.value)}
              placeholder="Type a message or spoken command (e.g. 'Mujhe skin doctor ko dikhana hai')..."
              className="flex-1 bg-slate-950 border border-slate-700 rounded-xl px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-sky-500"
            />
            <button
              type="submit"
              disabled={!typedMessage.trim()}
              className="p-2.5 rounded-xl bg-sky-600 hover:bg-sky-500 disabled:opacity-50 disabled:hover:bg-sky-600 text-white transition-colors"
            >
              <Send className="w-4 h-4" />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};
