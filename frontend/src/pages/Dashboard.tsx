import Sidebar from '../components/Sidebar';
import { useState, useEffect } from 'react';
import { api } from '../api';
import { AlertTriangle, UploadCloud, Download, RotateCcw, CheckCircle, AlertOctagon, ShieldAlert, ShieldCheck, Info } from 'lucide-react';
import { useLocation } from 'react-router-dom';
import { Radar, RadarChart, PolarGrid, PolarAngleAxis, ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts';

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
    
    for (let i=0; i<msgs.length; i++) {
        setLoadingMsgs(prev => [...prev, msgs[i]]);
        await new Promise(r => setTimeout(r, 1500));
    }

    try {
        let authScore = 0;
        let txtScore = 0;
        let vidScore = 0;
        let audScore = 0;
        let segTxt: number[] = [];
        let segVid: number[] = [];
        let segAud: number[] = [];
        let combinedText = textInput;

        const authRes = await api.verifySignature({ 
            text: combinedText || undefined, 
            file: file || undefined 
        });
        authScore = authRes.is_authenticated_sender;

        if (combinedText) {
            const textRes = await api.analyzeText(combinedText);
            txtScore = textRes.final_text_score || 0;
            segTxt = textRes.segmented_text_scores || [];
        }

        if (file) {
            const mediaRes = await api.analyzeMedia(file);
            vidScore = mediaRes.video_fake_score;
            audScore = mediaRes.audio_fake_score;
            segVid = mediaRes.segmented_video_scores || [];
            segAud = mediaRes.segmented_audio_scores || [];
            
            // If the backend transcribed the audio or extracted OCR text, pass it to the linguistic engine!
            if (mediaRes.extracted_ocr_text) {
                const textRes = await api.analyzeText(mediaRes.extracted_ocr_text);
                // We combine or take the worst-case text score if both textInput and audio transcript exist
                txtScore = Math.max(txtScore, textRes.final_text_score || 0);
                if (textRes.segmented_text_scores && textRes.segmented_text_scores.length > 0) {
                    segTxt = textRes.segmented_text_scores;
                }
                
                // Append the transcribed text so the LLM can reference it
                if (combinedText) {
                    combinedText += "\n\n[Extracted from Media]:\n" + mediaRes.extracted_ocr_text;
                } else {
                    combinedText = mediaRes.extracted_ocr_text; // Fake it into combinedText so getFinalScore uses it
                }
            }
        }

        const scoreRes = await api.getFinalScore({
            text_score: txtScore,
            video_score: vidScore,
            audio_score: audScore,
            domain: "", // Pass empty string if no URL is detected
            is_authenticated_sender: authScore,
            raw_text: combinedText || "File uploaded without any textual/spoken content.",
            segmented_text_scores: segTxt,
            segmented_video_scores: segVid,
            segmented_audio_scores: segAud
        });
        
        setFinalScore(scoreRes);
        setUiState('RESULT');
    } catch (e) {
        console.error(e);
        setUiState('INPUT'); // Reset on error
    }
  };

  const radarData = finalScore ? [
    { subject: 'VIDEO', A: Math.round((finalScore.features_used?.video_score || 0)*100), fullMark: 100 },
    { subject: 'AUDIO', A: Math.round((finalScore.features_used?.audio_score || 0)*100), fullMark: 100 },
    { subject: 'TEXT', A: Math.round((finalScore.features_used?.text_score || 0)*100), fullMark: 100 },
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

  // Parse the LLM Threat Report into Summary and Recommendations
  const rawReport = finalScore?.llm_threat_report || "No report generated.";
  const reportParagraphs = rawReport.split(/\n\n+/).filter((p: string) => p.trim() !== '');
  const splitIndex = Math.max(1, Math.ceil(reportParagraphs.length / 2));
  const summaryText = reportParagraphs.length > 1 ? reportParagraphs.slice(0, splitIndex).join(' ') : rawReport;
  const recommendationText = reportParagraphs.length > 1 ? reportParagraphs.slice(splitIndex).join(' ') : "No specific recommendations provided.";

  // Split into sentences for bullet points
  const summarySentences = summaryText.split(/(?<=[.!?])\s+/).filter((s: string) => s.trim().length > 10);
  const recommendationSentences = recommendationText.split(/(?<=[.!?])\s+/).filter((s: string) => s.trim().length > 10);

  // Timeline Data Processing
  const timelineDataObj = finalScore?.timeline_data || {};
  let chartData: any[] = [];
  let chartTitle = 'THREAT PROBABILITY OVER TIME';

  if (timelineDataObj.video && timelineDataObj.video.length > 0) {
      chartData = timelineDataObj.video.map((score: number, idx: number) => ({ name: `0:0${idx*5}`, score: Math.round(score * 100) }));
      chartTitle = 'VIDEO THREAT PROBABILITY TIMELINE';
  } else if (timelineDataObj.audio && timelineDataObj.audio.length > 0) {
      chartData = timelineDataObj.audio.map((score: number, idx: number) => ({ name: `0:0${idx*5}`, score: Math.round(score * 100) }));
      chartTitle = 'AUDIO THREAT PROBABILITY TIMELINE';
  } else if (timelineDataObj.text && timelineDataObj.text.length > 0) {
      chartData = timelineDataObj.text.map((score: number, idx: number) => ({ name: `Segment ${idx+1}`, score: Math.round(score * 100) }));
      chartTitle = 'TEXT THREAT PROBABILITY TIMELINE';
  } else {
      // Fallback flatline if no data
      chartData = [
          { name: 'Start', score: Math.round((finalScore?.threat_probability || 0)) },
          { name: 'End', score: Math.round((finalScore?.threat_probability || 0)) }
      ];
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
             <div className="grid grid-cols-1 lg:grid-cols-5 gap-6 items-stretch">
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
                         <div className="absolute text-[10px] font-black text-cyan-400">{Math.round((finalScore.features_used?.video_score || 0)*100)}<span className="text-[8px]">%</span></div>
                     </div>
                 </div>

                 <div className="bg-black border border-gray-800 rounded-xl p-5 flex items-center justify-between gap-3 shadow-lg h-full">
                     <div className="text-[10px] font-black text-white tracking-widest leading-relaxed">AUDIO DEEPFAKE SCORE</div>
                     <div className="relative w-12 h-12 flex items-center justify-center shrink-0">
                         <svg className="absolute w-full h-full transform -rotate-90" viewBox="0 0 36 36">
                             <circle cx="18" cy="18" r="14" stroke="#1f2937" strokeWidth="4" fill="transparent" />
                             <circle cx="18" cy="18" r="14" stroke="#22d3ee" strokeWidth="4" fill="transparent" strokeDasharray={2 * Math.PI * 14} strokeDashoffset={(2 * Math.PI * 14) - (((finalScore.features_used?.audio_score || 0)) * (2 * Math.PI * 14))} className="transition-all duration-1000 ease-out" strokeLinecap="round" />
                         </svg>
                         <div className="absolute text-[10px] font-black text-cyan-400">{Math.round((finalScore.features_used?.audio_score || 0)*100)}<span className="text-[8px]">%</span></div>
                     </div>
                 </div>

                 <div className="bg-black border border-gray-800 rounded-xl p-5 flex items-center justify-between gap-3 shadow-lg h-full">
                     <div className="text-[10px] font-black text-white tracking-widest leading-relaxed">TEXT PHISHING SCORE</div>
                     <div className="relative w-12 h-12 flex items-center justify-center shrink-0">
                         <svg className="absolute w-full h-full transform -rotate-90" viewBox="0 0 36 36">
                             <circle cx="18" cy="18" r="14" stroke="#1f2937" strokeWidth="4" fill="transparent" />
                             <circle cx="18" cy="18" r="14" stroke="#22d3ee" strokeWidth="4" fill="transparent" strokeDasharray={2 * Math.PI * 14} strokeDashoffset={(2 * Math.PI * 14) - (((finalScore.features_used?.text_score || 0)) * (2 * Math.PI * 14))} className="transition-all duration-1000 ease-out" strokeLinecap="round" />
                         </svg>
                         <div className="absolute text-[10px] font-black text-cyan-400">{Math.round((finalScore.features_used?.text_score || 0)*100)}<span className="text-[8px]">%</span></div>
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
             <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 items-stretch">
                {/* Left Column: Threat Report */}
                <div className="flex flex-col">
                    <div className="bg-white border border-gray-200 rounded-xl p-6 flex flex-col h-full shadow-sm">
                       <div className="text-xs font-black text-black mb-4 tracking-widest uppercase flex items-center gap-3">
                           <div className="w-6 h-6 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center">
                               <Info size={14} strokeWidth={3} />
                           </div>
                           ANALYST SUMMARY
                       </div>
                       <div className="bg-[#F4F7FB] border border-blue-50 rounded-xl p-5 space-y-4 flex-1">
                           {summarySentences.length > 0 ? summarySentences.map((sentence: string, idx: number) => (
                               <div key={idx} className="flex items-start gap-3">
                                    <div className="mt-0.5 text-blue-500 shrink-0">
                                        <Info size={16} />
                                    </div>
                                    <div className="text-gray-700 text-[13px] font-medium leading-relaxed">
                                        {sentence.trim()}
                                    </div>
                               </div>
                           )) : (
                               <div className="text-gray-700 text-[13px] font-medium">{summaryText}</div>
                           )}
                       </div>
                    </div>
                </div>                

                {/* Right Column: Timeline Graph */}
                <div className="flex flex-col">
                    <div className="bg-[#F8F9FA] border border-gray-200 rounded-xl p-6 flex flex-col h-full shadow-sm">
                        <div className="flex justify-between items-center mb-6">
                            <div className="text-xs font-black text-black tracking-widest uppercase flex items-center gap-3">
                                <div className="w-2 h-2 bg-[#FF3333] rounded-full"></div>
                                {chartTitle}
                            </div>
                        </div>
                        <div className="flex-1 w-full min-h-[250px]">
                            <ResponsiveContainer width="100%" height="100%">
                                <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                                    <defs>
                                        <linearGradient id="colorScore" x1="0" y1="0" x2="0" y2="1">
                                            <stop offset="5%" stopColor="#FF3333" stopOpacity={0.3}/>
                                            <stop offset="95%" stopColor="#FF3333" stopOpacity={0}/>
                                        </linearGradient>
                                    </defs>
                                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e7eb" />
                                    <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#6b7280', fontWeight: 600 }} axisLine={false} tickLine={false} dy={10} />
                                    <YAxis tick={{ fontSize: 11, fill: '#6b7280', fontWeight: 600 }} axisLine={false} tickLine={false} tickFormatter={(val) => `${val}%`} />
                                    <Tooltip 
                                        contentStyle={{ backgroundColor: '#111827', borderRadius: '8px', border: 'none', color: '#fff' }}
                                        itemStyle={{ color: '#FF3333', fontWeight: 'bold' }}
                                        labelStyle={{ color: '#9ca3af', fontSize: '12px', marginBottom: '4px' }}
                                    />
                                    <Area type="monotone" dataKey="score" stroke="#FF3333" strokeWidth={3} fillOpacity={1} fill="url(#colorScore)" activeDot={{ r: 6, fill: '#FF3333', stroke: '#fff', strokeWidth: 2 }} />
                                </AreaChart>
                            </ResponsiveContainer>
                        </div>
                    </div>
                </div>

             </div>

             {/* Row 4: Recommended Actions (Full Width) */}
             <div className="bg-[#F8F9FA] border border-gray-200 rounded-xl p-6 shadow-sm mt-8">
                 <div className="text-xs font-black text-black mb-6 tracking-widest uppercase flex items-center gap-3">
                     <div className="w-2 h-2 bg-emerald-400 rounded-full"></div>
                     RECOMMENDED ACTIONS
                 </div>
                 <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                 {recommendationSentences.length > 0 ? recommendationSentences.slice(0, 4).map((sentence: string, idx: number) => (
                     <div key={idx} className="bg-white rounded-xl shadow-sm hover:shadow-md transition-all flex flex-col overflow-hidden border border-gray-200">
                          <div className="bg-black p-4 flex items-center gap-3">
                              <div className="w-8 h-8 rounded-full bg-gray-900 border border-gray-800 text-cyan-400 flex items-center justify-center shrink-0">
                                  {idx === 0 ? <ShieldAlert size={14} /> : idx === 1 ? <AlertTriangle size={14} /> : <CheckCircle size={14} />}
                              </div>
                              <div className="text-white text-[10px] font-black tracking-widest uppercase mt-0.5">
                                  {idx === 0 ? 'Immediate Action' : idx === 1 ? 'Precaution' : idx === 2 ? 'Verification' : 'Security Tip'}
                              </div>
                          </div>
                          <div className="p-4 flex-1">
                              <div className="text-gray-700 text-[13px] font-medium leading-relaxed">
                                  {sentence.trim()}
                              </div>
                          </div>
                     </div>
                 )) : (
                     <div className="text-gray-800 text-[14px] font-medium">{recommendationText}</div>
                 )}
                 </div>
             </div>

             {/* Row 5: Bottom Section (Analysis Timeline & Footprint) */}
             <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 items-stretch mt-8">
                 {/* Left Col: Analysis Timeline */}
                 <div className="bg-[#F8F9FA] border border-gray-200 rounded-xl p-6 shadow-sm flex flex-col">
                      <div className="text-xs font-black text-black mb-6 tracking-widest uppercase flex items-center gap-3">
                          <div className="w-2 h-2 bg-blue-600 rounded-full"></div>
                          ANALYSIS TIMELINE
                      </div>
                      <div className="flex-1 flex items-center justify-between relative px-2 mt-4">
                          {/* Connecting Line */}
                          <div className="absolute top-4 left-10 right-10 h-[2px] bg-gray-200 z-0"></div>
                          
                          {/* Steps */}
                          <div className="flex flex-col items-center gap-3 relative z-10">
                             <div className="w-8 h-8 rounded-full border border-gray-300 bg-white flex items-center justify-center text-gray-500 shadow-sm"><Download size={14} /></div>
                             <div className="text-[9px] font-black text-gray-800 text-center uppercase tracking-wider max-w-[80px]">Asset Uploaded</div>
                          </div>
                          <div className="flex flex-col items-center gap-3 relative z-10">
                             <div className="w-8 h-8 rounded-full border border-gray-300 bg-white flex items-center justify-center text-cyan-500 shadow-sm"><UploadCloud size={14} /></div>
                             <div className="text-[9px] font-black text-gray-800 text-center uppercase tracking-wider max-w-[80px]">Media Processed</div>
                          </div>
                          <div className="flex flex-col items-center gap-3 relative z-10">
                             <div className="w-8 h-8 rounded-full border border-gray-300 bg-white flex items-center justify-center text-blue-500 shadow-sm"><Info size={14} /></div>
                             <div className="text-[9px] font-black text-gray-800 text-center uppercase tracking-wider max-w-[80px]">Transcript Analysed</div>
                          </div>
                          <div className="flex flex-col items-center gap-3 relative z-10">
                             <div className="w-8 h-8 rounded-full border border-red-200 bg-red-50 flex items-center justify-center text-red-500 shadow-sm shadow-red-100"><AlertTriangle size={14} /></div>
                             <div className="text-[9px] font-black text-gray-800 text-center uppercase tracking-wider max-w-[80px]">Threat Detected</div>
                          </div>
                          <div className="flex flex-col items-center gap-3 relative z-10">
                             <div className="w-8 h-8 rounded-full border border-gray-300 bg-white flex items-center justify-center text-gray-800 shadow-sm"><CheckCircle size={14} /></div>
                             <div className="text-[9px] font-black text-gray-800 text-center uppercase tracking-wider max-w-[80px]">Report Generated</div>
                          </div>
                      </div>
                 </div>

                 {/* Right Col: Threat Footprint & Buttons */}
                 <div className="flex flex-col gap-6">
                     <div className="bg-[#F8F9FA] border border-gray-200 rounded-xl p-6 shadow-sm flex-1">
                          <div className="text-xs font-black text-black mb-4 tracking-widest uppercase flex items-center gap-3">
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
                                      <div className="text-sm font-black text-[#FF3333]">{Math.round((finalScore.features_used?.text_score || 0)*100)}%</div>
                                  </div>
                                  <div className="flex justify-between items-center pb-2 border-b border-gray-200/50">
                                      <div className="text-[11px] font-black text-gray-600 uppercase tracking-widest">Audio</div>
                                      <div className="text-sm font-black text-[#FFB800]">{Math.round((finalScore.features_used?.audio_score || 0)*100)}%</div>
                                  </div>
                                  <div className="flex justify-between items-center">
                                      <div className="text-[11px] font-black text-gray-600 uppercase tracking-widest">Video</div>
                                      <div className="text-sm font-black text-[#34d399]">{Math.round((finalScore.features_used?.video_score || 0)*100)}%</div>
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
