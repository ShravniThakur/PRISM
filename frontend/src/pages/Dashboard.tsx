import Sidebar from '../components/Sidebar';
import { useState, useEffect } from 'react';
import { api } from '../api';
import { AlertTriangle, UploadCloud } from 'lucide-react';
import { useLocation } from 'react-router-dom';

type UIState = 'INPUT' | 'LOADING' | 'RESULT';

export default function Dashboard() {
  const location = useLocation();
  const [uiState, setUiState] = useState<UIState>('INPUT');
  const [textInput, setTextInput] = useState('');
  const [file, setFile] = useState<File | null>(null);
  
  // Results
  const [loadingMsgs, setLoadingMsgs] = useState<string[]>([]);
  const [finalScore, setFinalScore] = useState<any>(null);
  const [animatedScore, setAnimatedScore] = useState(0);

  useEffect(() => {
     if (location.state?.historyScan) {
         setFinalScore(location.state.historyScan);
         setUiState('RESULT');
     }
  }, [location.state]);

  useEffect(() => {
     if (uiState === 'RESULT' && finalScore) {
         const timer = setTimeout(() => {
             setAnimatedScore(Math.round(finalScore.threat_probability));
         }, 100);
         return () => clearTimeout(timer);
     } else {
         setAnimatedScore(0);
     }
  }, [uiState, finalScore]);

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
        let combinedText = textInput;

        const authRes = await api.verifySignature({ 
            text: combinedText || undefined, 
            file: file || undefined 
        });
        authScore = authRes.is_authenticated_sender;

        if (combinedText) {
            const textRes = await api.analyzeText(combinedText);
            txtScore = textRes.threat_score_text;
        }

        if (file) {
            const mediaRes = await api.analyzeMedia(file);
            vidScore = mediaRes.video_fake_score;
            audScore = mediaRes.audio_fake_score;
            
            // If the backend transcribed the audio or extracted OCR text, pass it to the linguistic engine!
            if (mediaRes.extracted_ocr_text) {
                const textRes = await api.analyzeText(mediaRes.extracted_ocr_text);
                // We combine or take the worst-case text score if both textInput and audio transcript exist
                txtScore = Math.max(txtScore, textRes.threat_score_text);
                
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
            domain: combinedText ? "example.com" : "", // Mock domain, extract proper URL later
            is_authenticated_sender: authScore,
            raw_text: combinedText || "File uploaded without any textual/spoken content."
        });
        
        setFinalScore(scoreRes);
        setUiState('RESULT');
    } catch (e) {
        console.error(e);
        setUiState('INPUT'); // Reset on error
    }
  };

  return (
    <div className="min-h-screen bg-white text-black font-sans flex overflow-x-hidden">
      <div className="print:hidden">
         <Sidebar />
      </div>
      <div className="ml-56 print:ml-0 p-12 print:p-0 w-full max-w-6xl pt-28 print:pt-8">
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
          <div className="flex gap-10 mt-8 items-stretch">
             {/* Left Column: Report */}
               <div className="w-7/12">
                <div className="bg-[#F8F9FA] border border-gray-200 rounded-xl p-8 h-full flex flex-col justify-between shadow-sm">
                   <div>
                       <div className="text-xs font-black text-gray-500 mb-6 tracking-widest uppercase">THREAT REPORT</div>
                       <div className="text-gray-800 text-sm font-medium leading-relaxed whitespace-pre-wrap">
                           {finalScore.llm_threat_report || "No report generated."}
                       </div>
                   </div>
                   
                   <div className="flex gap-4 mt-12 print:hidden">
                      <button onClick={() => window.print()} className="flex-1 bg-black text-cyan-400 font-bold py-4 text-xs tracking-widest rounded-lg hover:bg-gray-900 transition shadow-md hover:shadow-lg">
                         EXPORT TO PDF
                      </button>
                      <button onClick={() => setUiState('INPUT')} className="flex-1 bg-black text-white font-bold py-4 text-xs tracking-widest rounded-lg hover:bg-gray-900 transition shadow-md hover:shadow-lg">
                         NEW ANALYSIS
                      </button>
                   </div>
                </div>
             </div>
             
             {/* Right Column: Gauges */}
             <div className="w-5/12 flex flex-col gap-4">
                 {/* Top Badge */}
                 <div className="mb-2">
                     <div className={`flex items-center justify-center gap-2 w-full px-6 py-4 rounded-xl font-black tracking-widest text-sm bg-black ${finalScore.classification === 'Safe' ? 'text-[#39FF14]' : 'text-[#FF3333]'}`}>
                         <AlertTriangle size={18} />
                         {finalScore.classification === 'Safe' ? 'SAFE' : 'MALICIOUS'}
                     </div>
                 </div>
                 
                 {/* Gauge Box */}
                 <div className="bg-black border border-gray-800 rounded-xl p-6 flex flex-col items-center justify-center py-10 shadow-lg">
                     <div className="text-xs font-black text-white mb-8 tracking-widest">THREAT PROBABILITY</div>
                     <div className="relative w-48 h-48 flex items-center justify-center">
                         <svg className="absolute w-full h-full transform -rotate-90" viewBox="0 0 192 192">
                             <circle cx="96" cy="96" r="80" stroke="#1f2937" strokeWidth="16" fill="transparent" />
                             <circle 
                                 cx="96" cy="96" r="80" 
                                 stroke={finalScore.threat_probability > 50 ? '#FF8A8A' : '#34d399'} 
                                 strokeWidth="16" fill="transparent" 
                                 strokeDasharray={2 * Math.PI * 80} 
                                 strokeDashoffset={(2 * Math.PI * 80) - ((animatedScore / 100) * (2 * Math.PI * 80))} 
                                 className="transition-all duration-1000 ease-out" 
                                 strokeLinecap="round" 
                             />
                         </svg>
                         <div className="absolute flex flex-col items-center text-white">
                             <div className="text-5xl font-black">{Math.round(finalScore.threat_probability)}%</div>
                             <div className="text-xs font-black tracking-widest mt-2 text-gray-400">{finalScore.threat_probability > 50 ? 'MALICIOUS' : 'AUTHENTIC'}</div>
                         </div>
                     </div>
                 </div>

                 {/* Breakdowns */}
                 <div className="bg-black border border-gray-800 rounded-xl p-6 space-y-6 shadow-lg">
                     <div className={`w-full py-4 text-center rounded-lg font-black text-xs tracking-widest ${finalScore.is_authenticated_sender ? 'bg-emerald-400 text-black' : 'bg-[#FF8A8A] text-black'}`}>
                        {finalScore.is_authenticated_sender ? 'AUTHENTICATED SENDER' : 'NOT AUTHENTICATED'}
                     </div>
                     
                     <div className="pt-2">
                        <div className="flex justify-between items-end mb-2">
                           <div className="text-[8px] font-black text-white tracking-widest">VIDEO DEEPFAKE SCORE</div>
                           <div className="text-[10px] font-black text-cyan-400">{Math.round((finalScore.features_used?.video_score || 0)*100)}%</div>
                        </div>
                        <div className="w-full h-3 bg-gray-900 rounded-full overflow-hidden">
                           <div className="h-full bg-cyan-400 transition-all duration-1000 ease-out" style={{ width: `${(finalScore.features_used?.video_score || 0)*100}%` }}></div>
                        </div>
                     </div>
                     <div>
                        <div className="flex justify-between items-end mb-2">
                           <div className="text-[8px] font-black text-white tracking-widest">AUDIO DEEPFAKE SCORE</div>
                           <div className="text-[10px] font-black text-cyan-400">{Math.round((finalScore.features_used?.audio_score || 0)*100)}%</div>
                        </div>
                        <div className="w-full h-3 bg-gray-900 rounded-full overflow-hidden">
                           <div className="h-full bg-cyan-400 transition-all duration-1000 ease-out" style={{ width: `${(finalScore.features_used?.audio_score || 0)*100}%` }}></div>
                        </div>
                     </div>
                     <div>
                        <div className="flex justify-between items-end mb-2">
                           <div className="text-[8px] font-black text-white tracking-widest">TEXT PHISHING SCORE</div>
                           <div className="text-[10px] font-black text-cyan-400">{Math.round((finalScore.features_used?.text_score || 0)*100)}%</div>
                        </div>
                        <div className="w-full h-3 bg-gray-900 rounded-full overflow-hidden">
                           <div className="h-full bg-cyan-400 transition-all duration-1000 ease-out" style={{ width: `${(finalScore.features_used?.text_score || 0)*100}%` }}></div>
                        </div>
                     </div>
                 </div>
             </div>
          </div>
        )}
      </div>
    </div>
  );
}
