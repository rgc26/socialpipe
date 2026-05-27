import React, { useState, useEffect, useRef } from 'react';
import AgoraRTC from 'agora-rtc-sdk-ng';
import { Mic, PhoneOff, Radio, MessageCircle, X } from 'lucide-react';
import axios from 'axios';

const APP_ID  = import.meta.env.VITE_AGORA_APP_ID;
const CHANNEL = 'socialpipe-voice';

const VoiceAgent = () => {
  console.log('VoiceAgent initialized with APP_ID:', APP_ID);
  const [isConnected, setIsConnected]     = useState(false);
  const [isSpeaking, setIsSpeaking]       = useState(false);
  const [transcripts, setTranscripts]     = useState([]);
  const [showTranscript, setShowTranscript] = useState(false);

  const client          = useRef(null);
  const localAudioTrack = useRef(null);
  const remoteAudioTrack = useRef(null);

  useEffect(() => {
    client.current = AgoraRTC.createClient({ mode: 'rtc', codec: 'vp8' });
    return () => { handleDisconnect(); };
  }, []);

  const handleConnect = async () => {
    try {
      await client.current.join(APP_ID, CHANNEL, null, null);
      localAudioTrack.current = await AgoraRTC.createMicrophoneAudioTrack();
      await client.current.publish(localAudioTrack.current);
      setIsConnected(true);
      addTranscript('System', 'Connected to SocialPipe Voice Agent.');
      simulateAgentResponse("Hello! I'm your SocialPipe sales assistant. How can I help you manage your leads today?");
    } catch (error) {
      console.error('Voice connection failed:', error);
      alert('Failed to connect to Voice Agent. Ensure VITE_AGORA_APP_ID is set.');
    }
  };

  const handleDisconnect = async () => {
    if (localAudioTrack.current) { localAudioTrack.current.stop(); localAudioTrack.current.close(); }
    if (client.current) { await client.current.leave(); }
    setIsConnected(false);
    setIsSpeaking(false);
    addTranscript('System', 'Disconnected.');
  };

  const addTranscript = (sender, text) => {
    setTranscripts(prev => [...prev.slice(-4), { sender, text, id: Date.now() }]);
  };

  const simulateAgentResponse = async (text) => {
    setIsSpeaking(true);
    addTranscript('Agent', text);
    setTimeout(() => setIsSpeaking(false), 3000);
  };

  const fetchLeadSummary = async () => {
    try {
      const response = await axios.get('http://localhost:8000/api/leads?status=hot');
      const hotLeads = response.data;
      if (hotLeads.length > 0) {
        simulateAgentResponse(`You have ${hotLeads.length} hot leads waiting. The top lead is from ${hotLeads[0].author} with a score of ${hotLeads[0].score}.`);
      } else {
        simulateAgentResponse("You don't have any hot leads at the moment. Keep scanning!");
      }
    } catch (error) {
      console.error('Failed to fetch leads for voice agent:', error);
    }
  };

  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col items-end gap-3">

      {/* Transcript card */}
      {showTranscript && (
        <div className="w-80 rounded-xl overflow-hidden bg-white" style={{ border: '1px solid #e2e8f0', boxShadow: '0 8px 30px rgba(0,0,0,0.10)' }}>
          <div className="px-5 py-3 flex justify-between items-center" style={{ borderBottom: '1px solid #f1f5f9' }}>
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-500 dot-pulse"></span>
              <span className="text-xs font-semibold uppercase tracking-widest text-slate-400">Voice Transcript</span>
            </div>
            <button onClick={() => setShowTranscript(false)} className="text-slate-300 hover:text-slate-500 transition-colors">
              <X size={16} />
            </button>
          </div>
          <div className="p-5 space-y-3 max-h-60 overflow-y-auto">
            {transcripts.length === 0 && <p className="text-sm text-slate-400 italic">No messages yet…</p>}
            {transcripts.map((t) => (
              <div key={t.id} className="text-sm">
                <span className="font-semibold mr-1.5" style={{ color: t.sender === 'Agent' ? '#2563eb' : '#94a3b8' }}>{t.sender}:</span>
                <span className="text-slate-600">{t.text}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Control row */}
      <div className="flex items-center gap-2">
        {isConnected && (
          <button
            id="voice-transcript-btn"
            onClick={() => setShowTranscript(!showTranscript)}
            className="w-12 h-12 rounded-full bg-white flex items-center justify-center text-slate-400 hover:text-blue-600 transition-colors"
            style={{ border: '1px solid #e2e8f0', boxShadow: '0 2px 8px rgba(0,0,0,0.08)' }}
          >
            <MessageCircle size={20} />
          </button>
        )}

        <div className="relative">
          {isSpeaking && (
            <>
              <div className="absolute inset-0 rounded-full bg-blue-400 opacity-20 animate-ping"></div>
              <div className="absolute inset-0 rounded-full bg-blue-400 opacity-10 animate-ping" style={{ animationDelay: '300ms' }}></div>
            </>
          )}
          <button
            id="voice-agent-btn"
            onClick={isConnected ? handleDisconnect : handleConnect}
            className="relative z-10 w-14 h-14 rounded-full text-white flex items-center justify-center transition-all duration-200 active:scale-95"
            style={{
              background: isConnected ? '#ef4444' : '#2563eb',
              boxShadow: isConnected ? '0 4px 16px rgba(239,68,68,0.35)' : '0 4px 16px rgba(37,99,235,0.35)',
            }}
          >
            {isConnected ? <PhoneOff size={22} /> : <Mic size={22} />}
          </button>

          {isConnected && (
            <div className="absolute -top-0.5 -right-0.5 w-4 h-4 bg-emerald-500 rounded-full border-2 border-white flex items-center justify-center">
              <Radio size={8} className="text-white dot-pulse" />
            </div>
          )}
        </div>
      </div>

      {/* Tooltip */}
      {!isConnected && (
        <span
          className="text-xs font-semibold text-slate-500 bg-white px-3 py-1.5 rounded-lg animate-bounce"
          style={{ border: '1px solid #e2e8f0', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}
        >
          Voice Assistant
        </span>
      )}
    </div>
  );
};

export default VoiceAgent;
