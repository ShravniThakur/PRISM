import Sidebar from '../components/Sidebar';
import { useEffect, useState } from 'react';
import { api } from '../api';
import { useNavigate } from 'react-router-dom';

export default function History() {
  const [scans, setScans] = useState<any[]>([]);
  const navigate = useNavigate();
  
  useEffect(() => {
    api.getScanHistory().then(setScans);
  }, []);

  return (
    <div className="min-h-screen bg-white text-black font-sans flex">
      <Sidebar />
      <div className="ml-56 p-12 w-full max-w-5xl pt-28">
        <h1 className="text-3xl font-black mb-8 tracking-widest uppercase">HISTORY</h1>
        
        <div className="space-y-4">
          {scans.length === 0 ? (
             <p className="text-gray-500">No scan history found. Run an analysis first!</p>
          ) : (
             scans.map((scan) => (
               <div key={scan.id} className="flex justify-between items-center bg-[#E2E4E9] p-4 rounded-md">
                 <div className="font-bold text-gray-800 text-sm px-4">
                   SCAN_{scan.id.split('-')[0].toUpperCase()}.LOG
                 </div>
                 <button 
                   onClick={() => navigate('/dashboard', { state: { 
                      historyScan: {
                          threat_probability: scan.final_score,
                          classification: scan.classification,
                          llm_threat_report: scan.llm_threat_report,
                          is_authenticated_sender: scan.is_authenticated_sender,
                          features_used: {
                              video_score: scan.video_score,
                              audio_score: scan.audio_score,
                              text_score: scan.text_score
                          }
                      }
                   }})}
                   className="bg-black border border-gray-700 px-10 py-3 text-cyan-400 font-bold text-xs tracking-widest rounded hover:bg-gray-900 transition">
                   VIEW
                 </button>
               </div>
             ))
          )}
        </div>
      </div>
    </div>
  );
}
