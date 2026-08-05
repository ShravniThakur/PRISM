import Sidebar from '../components/Sidebar';
import { useState, useEffect } from 'react';
import { api } from '../api';
import { AlertTriangle, UploadCloud, Download, RotateCcw, CheckCircle, AlertOctagon, ShieldAlert, ShieldCheck, Info } from 'lucide-react';
import { useLocation } from 'react-router-dom';
import { Radar, RadarChart, PolarGrid, PolarAngleAxis, ResponsiveContainer } from 'recharts';

type UIState = 'INPUT' | 'LOADING' | 'RESULT';

export default function Dashboard() {
    const location = useLocation();
    const [uiState, setUiState] = useState<UIState>('INPUT');
    const [textInput, setTextInput] = useState('');
    const [file, setFile] = useState<File | null>(null);

    // Results
    const [loadingMsgs, setLoadingMsgs] = useState<string[]>([]);
    const [finalScore, setFinalScore] = useState<any>(null);

    useEffect(() => {
        if (location.state?.historyScan) {
            setFinalScore(location.state.historyScan);
            setUiState('RESULT');
        }
    }, [location.state]);

    const handleScan = async () => {
        setUiState('LOADING');
        setLoadingMsgs([]);

        // Fake the loading messages cycling
        const msgs = [
            "Checking if the sender is an officially registered financial entity...",
            "Scanning video and audio for AI-generated deepfakes...",
            "Analyzing text and hidden links for phishing attempts...",
            "Compiling results and generating your final AI Threat Report..."
        ];

        for (let i = 0; i < msgs.length; i++) {
            setLoadingMsgs(prev => [...prev, msgs[i]]);
            await new Promise(r => setTimeout(r, 1500));
        }

        try {
            let inputPayload: { text?: string; file?: File } = {};
            if (textInput) {
                inputPayload.text = textInput;
            } else if (file) {
                inputPayload.file = file;
            }

            const scoreRes = await api.analyzeUnified(inputPayload);


            setFinalScore(scoreRes);
            setUiState('RESULT');
        } catch (e) {
            console.error(e);
            setUiState('INPUT'); // Reset on error
        }
    };

    const radarData = finalScore ? [
        { subject: 'VIDEO', A: Math.round((finalScore.features_used?.video_score || 0) * 100), fullMark: 100 },
        { subject: 'AUDIO', A: Math.round((finalScore.features_used?.audio_score || 0) * 100), fullMark: 100 },
        { subject: 'TEXT', A: Math.round((finalScore.features_used?.text_score || 0) * 100), fullMark: 100 },
    ] : [];

    let bannerStatus = 'SAFE';
    let bannerColor = 'text-[#39FF14]';
    let BannerIcon = CheckCircle;

    if (finalScore?.threat_probability > 60) {
        bannerStatus = 'MALICIOUS';
        bannerColor = 'text-[#FF3333]';
        BannerIcon = AlertOctagon;
    } else if (finalScore?.threat_probability > 25) {
        bannerStatus = 'SUSPICIOUS';
        bannerColor = 'text-[#FFB800]';
        BannerIcon = AlertTriangle;
    }

    // Parse the LLM Threat Report JSON
  let parsedReport: { summary: string[], recommended_actions: { title: string, description: string }[] } = {
      summary: [],
      recommended_actions: []
  };

  const rawReport = finalScore?.llm_threat_report || "{}";
  try {
      // It might be already an object if the frontend interceptor parsed it, or a string
      if (typeof rawReport === 'string') {
          parsedReport = JSON.parse(rawReport);
      } else {
          parsedReport = rawReport;
      }
      
      // Fallback if the LLM didn't return an array for summary
      if (typeof parsedReport.summary === 'string') {
          parsedReport.summary = [parsedReport.summary];
      }
  } catch (e) {
      console.error("Failed to parse LLM JSON report:", e);
      parsedReport = {
          summary: [rawReport],
          recommended_actions: []
      };
  }

  const summarySentences = parsedReport.summary || [];
  const recommendedActions = parsedReport.recommended_actions || [];

    // Forensic Red Flag Badges Logic
    const redFlags: { title: string, description: string, color: string }[] = [];
    if (finalScore) {
        if (!finalScore.features_used?.is_auth) {
            redFlags.push({ title: "UNVERIFIED SENDER", description: "Zero-Trust Cryptographic Signature is missing or invalid.", color: "text-cyan-400" });
        }
        if ((finalScore.features_used?.video_score || 0) > 0.6) {
            redFlags.push({ title: "VISUAL ANOMALIES", description: "Spatiotemporal inconsistencies detected indicative of a deepfake.", color: "text-cyan-400" });
        }
        if ((finalScore.features_used?.audio_score || 0) > 0.6) {
            redFlags.push({ title: "SYNTHETIC AUDIO", description: "Acoustic patterns match AI voice synthesis models.", color: "text-cyan-400" });
        }
        if ((finalScore.features_used?.text_score || 0) > 0.6) {
            redFlags.push({ title: "PHISHING SEMANTICS", description: "High-urgency language and manipulative phrasing detected.", color: "text-cyan-400" });
        }
        if (redFlags.length === 0) {
            redFlags.push({ title: "NO ANOMALIES DETECTED", description: "The asset appears to be safe based on current heuristics.", color: "text-cyan-400" });
        }
    }

    return (
        <div className="min-h-screen bg-white text-black font-sans flex overflow-x-hidden">
            <div className="print:hidden">
                <Sidebar />
            </div>
            <div className="ml-56 print:ml-0 p-12 print:p-0 w-full pt-28 print:pt-8 pr-12">
                <h1 className="text-3xl font-black mb-2 tracking-widest uppercase">
                    {uiState === 'RESULT' ? 'Analysis Dashboard' : 'Analyse'}
                </h1>
                {uiState === 'INPUT' && (
                    <p className="text-gray-600 mb-8 text-sm font-medium">Upload suspicious media (Video, Audio, Images), documents (PDFs), or paste raw text and URLs to instantly initiate a tri-layer threat analysis.</p>
                )}

                {/* INPUT STATE */}
                {uiState === 'INPUT' && (
                    <div className="flex flex-col gap-6">
                        <div className="flex gap-6 h-64">
                            {/* TEXT INPUT SIDE */}
                            <div className={`w-1/2 bg-[#E2E4E9] rounded-lg p-4 flex flex-col transition-opacity ${file ? 'opacity-40 pointer-events-none' : ''}`}>
                                <textarea
                                    className="w-full flex-1 bg-white text-black p-6 rounded-md resize-none outline-none border-none text-xs font-bold leading-relaxed shadow-sm mb-4"
                                    value={textInput}
                                    onChange={(e) => setTextInput(e.target.value)}
                                    disabled={file !== null}
                                />
                                <div className="text-center text-gray-500 font-black text-sm tracking-widest pb-2">Paste Text Here</div>
                            </div>

                            {/* FILE UPLOAD SIDE */}
                            <div
                                onClick={() => !textInput && document.getElementById('file-upload')?.click()}
                                className={`w-1/2 bg-[#E2E4E9] rounded-lg p-6 flex flex-col items-center justify-center cursor-pointer hover:bg-gray-200 transition relative ${textInput ? 'opacity-40 pointer-events-none' : ''}`}
                            >
                                <UploadCloud size={64} className="text-gray-600 mb-4" strokeWidth={1} />
                                <div className="text-gray-800 font-black text-sm tracking-widest">
                                    {file ? file.name : "Upload Files"}
                                </div>
                                {file && (
                                    <div
                                        onClick={(e) => { e.stopPropagation(); setFile(null); }}
                                        className="absolute top-4 right-4 text-xs font-bold text-red-500 hover:text-red-700"
                                    >
                                        Remove
                                    </div>
                                )}
                                <input
                                    type="file"
                                    id="file-upload"
                                    className="hidden"
                                    onChange={(e) => {
                                        if (e.target.files && e.target.files.length > 0) {
                                            setFile(e.target.files[0]);
                                        }
                                    }}
                                />
                            </div>
                        </div>

                        <div className="flex gap-6">
                            {/* TEXT ANALYZE BUTTON */}
                            <button
                                onClick={handleScan}
                                disabled={!textInput || file !== null}
                                className={`w-1/2 bg-black border border-gray-800 font-bold tracking-widest py-4 rounded-md transition text-sm ${textInput && !file ? 'text-cyan-400 hover:bg-gray-900 cursor-pointer' : 'text-gray-600 cursor-not-allowed'}`}
                            >
                                ANALYSE
                            </button>

                            {/* FILE ANALYZE BUTTON */}
                            <button
                                onClick={handleScan}
                                disabled={!file || textInput.length > 0}
                                className={`w-1/2 bg-black border border-gray-800 font-bold tracking-widest py-4 rounded-md transition text-sm ${file && !textInput ? 'text-cyan-400 hover:bg-gray-900 cursor-pointer' : 'text-gray-600 cursor-not-allowed'}`}
                            >
                                ANALYSE
                            </button>
                        </div>
                    </div>
                )}

                {/* LOADING STATE */}
                {uiState === 'LOADING' && (
                    <div className="mt-16">
                        <div className="text-gray-500 mb-12 text-sm font-medium">Analysing ...</div>
                        <div className="relative flex flex-col gap-6 font-bold text-gray-800 text-lg tracking-wide">
                            {/* Connecting Vertical Line */}
                            <div className="absolute top-6 bottom-6 left-6 w-[2px] bg-gray-200 transform -translate-x-1/2 z-0"></div>

                            {loadingMsgs.map((msg, idx) => (
                                <div key={idx} className="flex items-center gap-6 relative z-10">
                                    {idx === loadingMsgs.length - 1 ? (
                                        <div className="w-12 h-12 rounded-full bg-cyan-50 border-2 border-cyan-400 flex items-center justify-center shrink-0 animate-pulse shadow-[0_0_15px_rgba(34,211,238,0.4)]">
                                            <div className="w-4 h-4 bg-cyan-400 rounded-full"></div>
                                        </div>
                                    ) : (
                                        <div className="w-12 h-12 bg-white rounded-full border-2 border-cyan-400 flex items-center justify-center shrink-0 shadow-sm">
                                            <div className="text-cyan-500 font-black text-xl">✓</div>
                                        </div>
                                    )}
                                    <span className={idx === loadingMsgs.length - 1 ? 'text-gray-800' : 'text-gray-400 font-medium'}>
                                        {msg}
                                    </span>
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {/* RESULT STATE */}
                {uiState === 'RESULT' && finalScore && (
                    <div className="flex flex-col gap-8 mt-8">

                        {/* Row 1: Top Badge */}
                        <div className={`flex flex-row items-center justify-center gap-3 w-full py-5 px-8 rounded-xl font-black tracking-widest text-2xl bg-black border border-gray-800 shadow-lg ${bannerColor}`}>
                            <BannerIcon size={32} />
                            <div className="text-center">{bannerStatus}</div>
                        </div>

                        {/* Row 2: 5 Separate Blocks (Auth, Video, Audio, Text, Overall) */}
                        <div className="grid grid-cols-1 lg:grid-cols-5 print:grid-cols-3 gap-6 items-stretch print:items-start print:break-inside-avoid">
                            <div className="bg-black border border-gray-800 rounded-xl p-5 flex flex-col justify-center shadow-lg h-full">
                                <div className="text-[10px] font-black text-white tracking-widest mb-2">AUTHENTICATION STATUS</div>
                                <div className={`flex items-center gap-2 text-[10px] font-black tracking-widest ${finalScore.features_used?.is_auth ? 'text-[#39FF14]' : 'text-[#FF3333]'}`}>
                                    {finalScore.features_used?.is_auth ? <ShieldCheck size={14} /> : <ShieldAlert size={14} />}
                                    {finalScore.features_used?.is_auth ? 'VERIFIED' : 'UNKNOWN'}
                                </div>
                            </div>

                            <div className="bg-black border border-gray-800 rounded-xl p-5 flex items-center justify-between gap-3 shadow-lg h-full">
                                <div className="text-[10px] font-black text-white tracking-widest leading-relaxed">VIDEO DEEPFAKE SCORE</div>
                                <div className="relative w-12 h-12 flex items-center justify-center shrink-0">
                                    <svg className="absolute w-full h-full transform -rotate-90" viewBox="0 0 36 36">
                                        <circle cx="18" cy="18" r="14" stroke="#1f2937" strokeWidth="4" fill="transparent" />
                                        <circle cx="18" cy="18" r="14" stroke="#22d3ee" strokeWidth="4" fill="transparent" strokeDasharray={2 * Math.PI * 14} strokeDashoffset={(2 * Math.PI * 14) - (((finalScore.features_used?.video_score || 0)) * (2 * Math.PI * 14))} className="transition-all duration-1000 ease-out" strokeLinecap="round" />
                                    </svg>
                                    <div className="absolute text-[10px] font-black text-cyan-400">{Math.round((finalScore.features_used?.video_score || 0) * 100)}<span className="text-[8px]">%</span></div>
                                </div>
                            </div>

                            <div className="bg-black border border-gray-800 rounded-xl p-5 flex items-center justify-between gap-3 shadow-lg h-full">
                                <div className="text-[10px] font-black text-white tracking-widest leading-relaxed">AUDIO DEEPFAKE SCORE</div>
                                <div className="relative w-12 h-12 flex items-center justify-center shrink-0">
                                    <svg className="absolute w-full h-full transform -rotate-90" viewBox="0 0 36 36">
                                        <circle cx="18" cy="18" r="14" stroke="#1f2937" strokeWidth="4" fill="transparent" />
                                        <circle cx="18" cy="18" r="14" stroke="#22d3ee" strokeWidth="4" fill="transparent" strokeDasharray={2 * Math.PI * 14} strokeDashoffset={(2 * Math.PI * 14) - (((finalScore.features_used?.audio_score || 0)) * (2 * Math.PI * 14))} className="transition-all duration-1000 ease-out" strokeLinecap="round" />
                                    </svg>
                                    <div className="absolute text-[10px] font-black text-cyan-400">{Math.round((finalScore.features_used?.audio_score || 0) * 100)}<span className="text-[8px]">%</span></div>
                                </div>
                            </div>

                            <div className="bg-black border border-gray-800 rounded-xl p-5 flex items-center justify-between gap-3 shadow-lg h-full">
                                <div className="text-[10px] font-black text-white tracking-widest leading-relaxed">TEXT PHISHING SCORE</div>
                                <div className="relative w-12 h-12 flex items-center justify-center shrink-0">
                                    <svg className="absolute w-full h-full transform -rotate-90" viewBox="0 0 36 36">
                                        <circle cx="18" cy="18" r="14" stroke="#1f2937" strokeWidth="4" fill="transparent" />
                                        <circle cx="18" cy="18" r="14" stroke="#22d3ee" strokeWidth="4" fill="transparent" strokeDasharray={2 * Math.PI * 14} strokeDashoffset={(2 * Math.PI * 14) - (((finalScore.features_used?.text_score || 0)) * (2 * Math.PI * 14))} className="transition-all duration-1000 ease-out" strokeLinecap="round" />
                                    </svg>
                                    <div className="absolute text-[10px] font-black text-cyan-400">{Math.round((finalScore.features_used?.text_score || 0) * 100)}<span className="text-[8px]">%</span></div>
                                </div>
                            </div>

                            <div className="bg-black border border-gray-800 rounded-xl p-5 flex items-center justify-between gap-3 shadow-lg h-full">
                                <div className="text-[10px] font-black text-white tracking-widest leading-relaxed">OVERALL THREAT SCORE</div>
                                <div className="relative w-12 h-12 flex items-center justify-center shrink-0">
                                    <svg className="absolute w-full h-full transform -rotate-90" viewBox="0 0 36 36">
                                        <circle cx="18" cy="18" r="14" stroke="#1f2937" strokeWidth="4" fill="transparent" />
                                        <circle cx="18" cy="18" r="14" stroke={finalScore.threat_probability > 60 ? '#FF3333' : finalScore.threat_probability > 25 ? '#FFB800' : '#39FF14'} strokeWidth="4" fill="transparent" strokeDasharray={2 * Math.PI * 14} strokeDashoffset={(2 * Math.PI * 14) - ((finalScore.threat_probability / 100) * (2 * Math.PI * 14))} className="transition-all duration-1000 ease-out" strokeLinecap="round" />
                                    </svg>
                                    <div className="absolute text-[10px] font-black" style={{ color: finalScore.threat_probability > 60 ? '#FF3333' : finalScore.threat_probability > 25 ? '#FFB800' : '#39FF14' }}>
                                        {Math.round(finalScore.threat_probability)}<span className="text-[8px]">%</span>
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* Row 3: Grid (Report | Timeline) */}
                        <div className="grid grid-cols-1 lg:grid-cols-2 print:grid-cols-1 gap-8 items-stretch print:items-start">
                            {/* Left Column: Threat Report */}
                            <div className="flex flex-col print:break-inside-avoid">
                                <div className="bg-white border border-gray-200 rounded-xl p-6 flex flex-col h-full print:h-auto shadow-sm">
                                    <div className="text-sm font-black text-black mb-4 tracking-widest uppercase flex items-center gap-3">
                                        <div className="w-6 h-6 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center">
                                            <Info size={14} strokeWidth={3} />
                                        </div>
                                        ANALYST SUMMARY
                                    </div>
                                    <div className="bg-[#F4F7FB] border border-blue-50 rounded-xl p-5 space-y-4 flex-1">
                                        {summarySentences.length > 0 ? summarySentences.map((sentence: any, idx: number) => {
                                            const text = typeof sentence === 'string' ? sentence : (sentence.text || JSON.stringify(sentence));
                                            return (
                                            <div key={idx} className="flex items-start gap-3">
                                                <div className="mt-0.5 text-blue-500 shrink-0">
                                                    <Info size={16} />
                                                </div>
                                                <div className="text-gray-700 text-[13px] font-medium leading-relaxed">
                                                    {text.trim()}
                                                </div>
                                            </div>
                                            );
                                        }) : (
                                            <div className="text-gray-700 text-[13px] font-medium">No summary provided.</div>
                                        )}
                                    </div>
                                </div>
                            </div>

                            {/* Right Column: Forensic Badges */}
                            <div className="flex flex-col print:break-inside-avoid">
                                <div className="bg-white border border-gray-200 rounded-xl p-6 flex flex-col h-full print:h-auto shadow-sm">
                                    <div className="text-sm font-black text-black mb-4 tracking-widest uppercase flex items-center gap-3">
                                        <div className="w-6 h-6 bg-red-100 text-red-600 rounded-full flex items-center justify-center">
                                            <AlertTriangle size={14} strokeWidth={3} />
                                        </div>
                                        FORENSIC RED FLAGS
                                    </div>
                                    <div className="flex flex-col gap-4 flex-1 overflow-y-auto print:overflow-visible pr-2">
                                        {redFlags.map((flag, idx) => (
                                            <div key={idx} className="bg-white rounded-xl shadow-sm flex flex-col overflow-hidden border border-gray-200">
                                                <div className="bg-black p-3 flex items-center gap-3">
                                                    <div className={`w-6 h-6 rounded-full bg-gray-900 border border-gray-800 flex items-center justify-center shrink-0 ${flag.color}`}>
                                                        {flag.title === "NO ANOMALIES DETECTED" ? <CheckCircle size={12} /> : <AlertTriangle size={12} />}
                                                    </div>
                                                    <div className="text-white text-[10px] font-black tracking-widest uppercase mt-0.5">
                                                        {flag.title}
                                                    </div>
                                                </div>
                                                <div className="p-4 flex-1">
                                                    <div className="text-gray-700 text-[12px] font-medium leading-relaxed">
                                                        {flag.description}
                                                    </div>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            </div>

                        </div>

                        {/* Row 4: Recommended Actions (Full Width) */}
                        <div className="bg-[#F8F9FA] border border-gray-200 rounded-xl p-6 shadow-sm mt-8 print:break-inside-avoid">
                            <div className="text-sm font-black text-black mb-6 tracking-widest uppercase flex items-center gap-3">
                                <div className="w-2 h-2 bg-emerald-400 rounded-full"></div>
                                RECOMMENDED ACTIONS
                            </div>
                            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 print:grid-cols-2 gap-6">
                                {recommendedActions.length > 0 ? recommendedActions.map((action: any, idx: number) => (
                                    <div key={idx} className="bg-white rounded-xl shadow-sm hover:shadow-md transition-all flex flex-col overflow-hidden border border-gray-200">
                                        <div className="bg-black p-4 flex items-center gap-3">
                                            <div className="w-8 h-8 rounded-full bg-gray-900 border border-gray-800 text-cyan-400 flex items-center justify-center shrink-0">
                                                {idx === 0 ? <ShieldAlert size={14} /> : idx === 1 ? <AlertTriangle size={14} /> : <CheckCircle size={14} />}
                                            </div>
                                            <div className="text-white text-[10px] font-black tracking-widest uppercase mt-0.5">
                                                {action.title}
                                            </div>
                                        </div>
                                        <div className="p-4 flex-1">
                                            <div className="text-gray-700 text-[13px] font-medium leading-relaxed">
                                                {action.description}
                                            </div>
                                        </div>
                                    </div>
                                )) : (
                                    <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm text-gray-700 text-[14px] font-medium">
                                        No recommendations available.
                                    </div>
                                )}
                            </div>
                        </div>

                        {/* Row 5: Bottom Section (Analysis Timeline & Footprint) */}
                        <div className="grid grid-cols-1 lg:grid-cols-2 print:grid-cols-1 gap-8 items-stretch print:items-start mt-8">
                            {/* Left Col: Analysis Timeline */}
                            <div className="bg-[#F8F9FA] border border-gray-200 rounded-xl p-6 shadow-sm flex flex-col print:break-inside-avoid">
                                <div className="text-sm font-black text-black mb-6 tracking-widest uppercase flex items-center gap-3">
                                    <div className="w-2 h-2 bg-blue-600 rounded-full"></div>
                                    ANALYSIS TIMELINE
                                </div>
                                <div className="flex-1 flex items-start justify-between relative mt-12">
                                    {/* Connecting Snake Line */}
                                    <div className="absolute -top-6 left-12 right-12 h-24 z-0">
                                        <svg width="100%" height="100%" preserveAspectRatio="none" viewBox="0 0 100 100" style={{ overflow: 'visible' }}>
                                            <path d="M 0 50 Q 12.5 -50, 25 50 T 50 50 T 75 50 T 100 50" stroke="black" strokeWidth="4" fill="none" vectorEffect="non-scaling-stroke" strokeLinecap="round" />
                                        </svg>
                                    </div>

                                    {/* Steps */}
                                    <div className="flex flex-col items-center gap-8 relative z-10 w-24">
                                        <div className="w-12 h-12 rounded-full bg-black flex items-center justify-center text-cyan-400 shadow-lg"><Download size={20} /></div>
                                        <div className="text-[10px] font-black text-gray-800 text-center uppercase tracking-wider">Asset Uploaded</div>
                                    </div>
                                    <div className="flex flex-col items-center gap-8 relative z-10 w-24">
                                        <div className="w-12 h-12 rounded-full bg-black flex items-center justify-center text-cyan-400 shadow-lg"><UploadCloud size={20} /></div>
                                        <div className="text-[10px] font-black text-gray-800 text-center uppercase tracking-wider">Media Processed</div>
                                    </div>
                                    <div className="flex flex-col items-center gap-8 relative z-10 w-24">
                                        <div className="w-12 h-12 rounded-full bg-black flex items-center justify-center text-cyan-400 shadow-lg"><Info size={20} /></div>
                                        <div className="text-[10px] font-black text-gray-800 text-center uppercase tracking-wider">Transcript Analysed</div>
                                    </div>
                                    <div className="flex flex-col items-center gap-8 relative z-10 w-24">
                                        <div className="w-12 h-12 rounded-full bg-black flex items-center justify-center text-cyan-400 shadow-lg"><AlertTriangle size={20} /></div>
                                        <div className="text-[10px] font-black text-gray-800 text-center uppercase tracking-wider">Threat Detected</div>
                                    </div>
                                    <div className="flex flex-col items-center gap-8 relative z-10 w-24">
                                        <div className="w-12 h-12 rounded-full bg-black flex items-center justify-center text-cyan-400 shadow-lg"><CheckCircle size={20} /></div>
                                        <div className="text-[10px] font-black text-gray-800 text-center uppercase tracking-wider">Report Generated</div>
                                    </div>
                                </div>
                            </div>

                            {/* Right Col: Threat Footprint & Buttons */}
                            <div className="flex flex-col gap-6 print:break-inside-avoid">
                                <div className="bg-[#F8F9FA] border border-gray-200 rounded-xl p-6 shadow-sm flex-1 print:h-auto">
                                    <div className="text-sm font-black text-black mb-4 tracking-widest uppercase flex items-center gap-3">
                                        <div className="w-2 h-2 bg-cyan-400 rounded-full"></div>
                                        THREAT FOOTPRINT
                                    </div>
                                    <div className="flex flex-row items-center h-48">
                                        {/* Radar Chart */}
                                        <div className="w-1/2 h-full relative">
                                            <ResponsiveContainer width="100%" height="100%">
                                                <RadarChart cx="50%" cy="50%" outerRadius="80%" data={radarData}>
                                                    <PolarGrid stroke="#e5e7eb" strokeWidth={1.5} />
                                                    <PolarAngleAxis dataKey="subject" tick={{ fill: '#4b5563', fontSize: 10, fontWeight: 900, letterSpacing: 1 }} />
                                                    <Radar name="Threat" dataKey="A" stroke="#06b6d4" strokeWidth={3} fill="#22d3ee" fillOpacity={0.6} isAnimationActive={true} />
                                                </RadarChart>
                                            </ResponsiveContainer>
                                        </div>

                                        {/* Scores List */}
                                        <div className="w-1/2 flex flex-col justify-center pl-8 gap-4">
                                            <div className="flex justify-between items-center pb-2 border-b border-gray-200/50">
                                                <div className="text-[11px] font-black text-gray-600 uppercase tracking-widest">Text</div>
                                                <div className="text-sm font-black text-[#FF3333]">{Math.round((finalScore.features_used?.text_score || 0) * 100)}%</div>
                                            </div>
                                            <div className="flex justify-between items-center pb-2 border-b border-gray-200/50">
                                                <div className="text-[11px] font-black text-gray-600 uppercase tracking-widest">Audio</div>
                                                <div className="text-sm font-black text-[#FFB800]">{Math.round((finalScore.features_used?.audio_score || 0) * 100)}%</div>
                                            </div>
                                            <div className="flex justify-between items-center">
                                                <div className="text-[11px] font-black text-gray-600 uppercase tracking-widest">Video</div>
                                                <div className="text-sm font-black text-[#34d399]">{Math.round((finalScore.features_used?.video_score || 0) * 100)}%</div>
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                {/* Buttons */}
                                <div className="flex gap-4 print:hidden">
                                    <button onClick={() => window.print()} className="w-1/2 flex items-center justify-center gap-3 bg-black text-cyan-400 font-bold py-4 text-xs tracking-widest rounded-xl hover:bg-gray-900 transition-all shadow-md group">
                                        <Download size={16} className="group-hover:-translate-y-1 transition-transform" />
                                        EXPORT TO PDF
                                    </button>
                                    <button onClick={() => setUiState('INPUT')} className="w-1/2 flex items-center justify-center gap-3 bg-black text-white font-bold py-4 text-xs tracking-widest rounded-xl hover:bg-gray-900 transition-all shadow-md group">
                                        <RotateCcw size={16} className="group-hover:-rotate-90 transition-transform" />
                                        NEW ANALYSIS
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
