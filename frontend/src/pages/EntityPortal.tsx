import { useState, useEffect } from 'react';
import { api } from '../api';
import { UploadCloud, ShieldCheck, KeyRound, CheckCircle2, UserPlus, FileSignature, Key, List, Eye, AlertTriangle, LogOut } from 'lucide-react';
import { ed25519 } from '@noble/curves/ed25519.js';
import { Link } from 'react-router-dom';

function extractSeedFromPKCS8(pem: string): Uint8Array {
    const base64 = pem.replace(/-----BEGIN PRIVATE KEY-----/, '')
                      .replace(/-----END PRIVATE KEY-----/, '')
                      .replace(/\s+/g, '');
    const der = Uint8Array.from(atob(base64), c => c.charCodeAt(0));
    return der.slice(der.length - 32);
}

export default function EntityPortal() {
  const [activeTab, setActiveTab] = useState<'ACCOUNT' | 'PUBLISH' | 'REVOKE' | 'ASSETS'>('ACCOUNT');
  
  // Global Session State
  const [loggedInEntity, setLoggedInEntity] = useState<any>(() => {
      const saved = localStorage.getItem('prism_entity');
      return saved ? JSON.parse(saved) : null;
  });

  useEffect(() => {
      if (loggedInEntity) {
          localStorage.setItem('prism_entity', JSON.stringify(loggedInEntity));
      } else {
          localStorage.removeItem('prism_entity');
      }
  }, [loggedInEntity]);

  // Account Tab State
  const [accountMode, setAccountMode] = useState<'REGISTER' | 'SIGN_IN'>('REGISTER');
  
  // Registration State
  const [regName, setRegName] = useState('');
  const [regType, setRegType] = useState('bank');
  const [regResult, setRegResult] = useState<any>(null);
  const [regError, setRegError] = useState('');
  const [hasRevealedKey, setHasRevealedKey] = useState(false);

  // Sign In State
  const [signInName, setSignInName] = useState('');
  const [signInError, setSignInError] = useState('');

  // Publishing State
  const [pubKeyPem, setPubKeyPem] = useState('');
  const [pubTitle, setPubTitle] = useState('');
  const [pubFile, setPubFile] = useState<File | null>(null);
  const [pubText, setPubText] = useState('');
  const [pubStatus, setPubStatus] = useState<'IDLE' | 'SIGNING' | 'SUCCESS'>('IDLE');
  const [pubError, setPubError] = useState('');
  const [pubResult, setPubResult] = useState<any>(null);

  // Revoke/Rotate State
  const [revokeStatus, setRevokeStatus] = useState<'IDLE' | 'ROTATING' | 'SUCCESS'>('IDLE');
  const [revokeError, setRevokeError] = useState('');
  const [revokeResult, setRevokeResult] = useState<any>(null);
  const [revokeHasRevealed, setRevokeHasRevealed] = useState(false);

  // Assets State
  const [assets, setAssets] = useState<any[]>([]);
  const [assetsLoading, setAssetsLoading] = useState(false);

  // Actions
  const handleRegister = async () => {
      setRegError('');
      setRegResult(null);
      setHasRevealedKey(false);
      try {
          const res = await api.registerEntity({ name: regName, type: regType });
          setRegResult(res);
          setLoggedInEntity(res);
      } catch (e: any) {
          setRegError(e?.response?.data?.detail || "Registration failed");
      }
  };

  const handleSignIn = async () => {
      setSignInError('');
      try {
          const res = await api.getEntityByName(signInName);
          setLoggedInEntity(res);
          // clear reg state just in case
          setRegResult(null); 
          setHasRevealedKey(false);
      } catch (e: any) {
          setSignInError(e?.response?.data?.detail || "Sign in failed");
      }
  };

  const handleSignOut = () => {
      setLoggedInEntity(null);
      setRegResult(null);
      setRevokeResult(null);
      setPubKeyPem('');
      setPubText('');
      setAccountMode('SIGN_IN');
      setActiveTab('ACCOUNT');
  };

  const handlePublish = async () => {
      if (!pubFile && !pubText) return setPubError("Please provide a file or text to sign.");
      if (pubFile && pubText) return setPubError("Please provide ONLY a file or text, not both.");
      if (!pubKeyPem.includes("BEGIN PRIVATE KEY")) return setPubError("Invalid Private Key PEM format.");
      if (!loggedInEntity) return setPubError("You must be logged in.");

      setPubError('');
      setPubStatus('SIGNING');

      try {
          const prepRes = await api.prepareSignature({ file: pubFile || undefined, text: pubText || undefined });
          const seed = extractSeedFromPKCS8(pubKeyPem);
          const payloadBytes = Uint8Array.from(atob(prepRes.payload_b64), c => c.charCodeAt(0));
          const signatureBytes = ed25519.sign(payloadBytes, seed);
          const signatureB64 = btoa(String.fromCharCode(...signatureBytes));

          const submitRes = await api.submitSignature({
              entity_id: loggedInEntity.id,
              payload_b64: prepRes.payload_b64,
              signature_b64: signatureB64,
              title: pubTitle,
              reference_url: ""
          });

          setPubResult(submitRes);
          setPubStatus('SUCCESS');
          setPubKeyPem(''); // Security: clear after signing
      } catch (e: any) {
          setPubError(e?.response?.data?.detail || "Signing failed");
          setPubStatus('IDLE');
      }
  };

  const handleRotateKey = async () => {
      if (!loggedInEntity) return;
      setRevokeError('');
      setRevokeStatus('ROTATING');
      setRevokeHasRevealed(false);
      try {
          const res = await api.rotateKey(loggedInEntity.id);
          setRevokeResult(res);
          setRevokeStatus('SUCCESS');
      } catch (e: any) {
          setRevokeError(e?.response?.data?.detail || "Rotation failed");
          setRevokeStatus('IDLE');
      }
  };

  useEffect(() => {
      const fetchAssets = async () => {
          if (!loggedInEntity) return;
          setAssetsLoading(true);
          try {
              const res = await api.getSignedAssets(loggedInEntity.id);
              setAssets(res);
          } catch(e) {
              console.error(e);
          } finally {
              setAssetsLoading(false);
          }
      };

      if (activeTab === 'ASSETS' && loggedInEntity) {
          fetchAssets();
      }
  }, [activeTab, loggedInEntity]);

  // Private Key Reveal Component
  const PrivateKeyCard = ({ pem, revealed, onReveal }: { pem: string, revealed: boolean, onReveal: () => void }) => {
      if (!revealed) {
          return (
              <div className="bg-black border border-gray-800 rounded-lg p-6 shadow-xl relative overflow-hidden flex flex-col items-center justify-center text-center min-h-[200px]">
                  <div className="absolute top-0 right-0 w-32 h-32 bg-cyan-500/10 rounded-full blur-3xl"></div>
                  <AlertTriangle size={32} className="text-yellow-500 mb-4" />
                  <h3 className="text-white font-black tracking-widest text-sm mb-2">PRIVATE KEY GENERATED</h3>
                  <p className="text-xs text-gray-400 mb-6 max-w-sm">This key is highly confidential and will only be displayed <strong>once</strong>. If you leave this page, it is lost forever.</p>
                  <button 
                      onClick={onReveal}
                      className="bg-cyan-500 hover:bg-cyan-400 text-black font-black tracking-widest px-6 py-3 rounded-md text-xs flex items-center gap-2 transition"
                  >
                      <Eye size={16} /> REVEAL PRIVATE KEY
                  </button>
              </div>
          );
      }

      return (
          <div className="bg-black border border-gray-800 rounded-lg p-6 shadow-xl relative overflow-hidden animate-in fade-in duration-500">
              <div className="absolute top-0 right-0 w-32 h-32 bg-cyan-500/10 rounded-full blur-3xl"></div>
              <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2 text-red-500 font-black text-xs tracking-widest">
                      <KeyRound size={14} /> HIGHLY CONFIDENTIAL: PRIVATE KEY
                  </div>
                  <a 
                      href={`data:text/plain;charset=utf-8,${encodeURIComponent(pem)}`}
                      download="prism_private_key.pem"
                      className="bg-cyan-500/10 text-cyan-400 hover:bg-cyan-500/20 px-3 py-1 rounded text-[10px] font-black tracking-widest transition cursor-pointer"
                  >
                      DOWNLOAD .PEM
                  </a>
              </div>
              <p className="text-xs text-gray-400 mb-4 leading-relaxed font-medium">
                  Copy and store this Ed25519 Private Key securely offline. PRISM operates on a Zero-Trust architecture—this key is never saved on our servers.
              </p>
              <textarea 
                  readOnly
                  className="w-full h-32 bg-[#050505] border border-gray-800 text-[#39FF14] font-mono text-[10px] p-4 rounded resize-none focus:outline-none"
                  value={pem}
              />
          </div>
      );
  };

  return (
    <div className="min-h-screen bg-gray-50 text-black font-sans flex overflow-x-hidden">
      {/* Portal Navbar */}
      <div className="w-full h-[72px] bg-black border-b border-gray-800 fixed top-0 left-0 z-50 flex items-center px-8 justify-between">
        <div className="flex items-center">
            <Link to="/" className="text-cyan-400 font-bold text-xl tracking-widest hover:text-cyan-300 transition">
                PRISM
            </Link>
            <div className="ml-8 text-gray-500 text-xs font-black tracking-widest border-l border-gray-800 pl-8">
                ENTITY PORTAL
            </div>
        </div>
        {loggedInEntity && (
            <div className="flex items-center gap-6">
                <div className="text-xs font-bold text-gray-400">
                    LOGGED IN AS: <span className="text-cyan-400 tracking-wider ml-2">{loggedInEntity.name.toUpperCase()}</span>
                </div>
            </div>
        )}
      </div>

      {/* Portal Sidebar */}
      <div className="w-64 h-[calc(100vh-72px)] bg-black border-r border-gray-800 flex flex-col justify-between text-white fixed top-[72px] left-0 z-40">
        <div className="pt-4">
            <button 
              onClick={() => setActiveTab('ACCOUNT')}
              className={`flex items-center gap-4 px-8 py-5 text-sm font-bold tracking-widest w-full text-left transition ${activeTab === 'ACCOUNT' ? 'text-cyan-400 border-l-2 border-cyan-400 bg-gray-900/50' : 'text-gray-400 hover:text-white'}`}
            >
              <UserPlus size={20} />
              ACCOUNT
            </button>
            <button 
              onClick={() => setActiveTab('PUBLISH')}
              disabled={!loggedInEntity}
              className={`flex items-center gap-4 px-8 py-5 text-sm font-bold tracking-widest w-full text-left transition ${!loggedInEntity ? 'opacity-30 cursor-not-allowed' : activeTab === 'PUBLISH' ? 'text-cyan-400 border-l-2 border-cyan-400 bg-gray-900/50' : 'text-gray-400 hover:text-white'}`}
            >
              <FileSignature size={20} />
              SIGN ASSET
            </button>
            <button 
              onClick={() => setActiveTab('REVOKE')}
              disabled={!loggedInEntity}
              className={`flex items-center gap-4 px-8 py-5 text-sm font-bold tracking-widest w-full text-left transition ${!loggedInEntity ? 'opacity-30 cursor-not-allowed' : activeTab === 'REVOKE' ? 'text-cyan-400 border-l-2 border-cyan-400 bg-gray-900/50' : 'text-gray-400 hover:text-white'}`}
            >
              <Key size={20} />
              REVOKE KEY
            </button>
            <button 
              onClick={() => setActiveTab('ASSETS')}
              disabled={!loggedInEntity}
              className={`flex items-center gap-4 px-8 py-5 text-sm font-bold tracking-widest w-full text-left transition ${!loggedInEntity ? 'opacity-30 cursor-not-allowed' : activeTab === 'ASSETS' ? 'text-cyan-400 border-l-2 border-cyan-400 bg-gray-900/50' : 'text-gray-400 hover:text-white'}`}
            >
              <List size={20} />
              SIGNED ASSETS
            </button>
        </div>
        {loggedInEntity && (
            <div className="p-4 border-t border-gray-800">
                <button 
                  onClick={handleSignOut}
                  className="flex items-center gap-4 px-8 py-4 text-sm font-bold tracking-widest w-full text-left text-gray-500 hover:text-red-400 hover:bg-gray-900/50 transition rounded-md"
                >
                  <LogOut size={20} />
                  SIGN OUT
                </button>
            </div>
        )}
      </div>

      {/* Main Content */}
      <div className="ml-64 pt-32 p-12 w-full max-w-5xl">
        
        {/* ACCOUNT TAB */}
        {activeTab === 'ACCOUNT' && (
            <div>
                <div className="flex items-center gap-4 mb-10">
                    <ShieldCheck size={40} className="text-cyan-500" />
                    <div>
                        <h1 className="text-3xl font-black text-gray-900 tracking-widest uppercase">
                            Entity Access
                        </h1>
                        <p className="text-gray-500 text-sm mt-1 tracking-wide">
                            Register your organization or sign in to access your assets.
                        </p>
                    </div>
                </div>

                {!loggedInEntity ? (
                    <div className="max-w-2xl bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
                        <div className="flex border-b border-gray-200">
                            <button 
                                onClick={() => { setAccountMode('SIGN_IN'); setRegError(''); setSignInError(''); }}
                                className={`flex-1 py-4 text-xs font-black tracking-widest transition ${accountMode === 'SIGN_IN' ? 'bg-black text-cyan-400' : 'bg-gray-50 text-gray-500 hover:bg-gray-100'}`}
                            >
                                SIGN IN
                            </button>
                            <button 
                                onClick={() => { setAccountMode('REGISTER'); setRegError(''); setSignInError(''); }}
                                className={`flex-1 py-4 text-xs font-black tracking-widest transition ${accountMode === 'REGISTER' ? 'bg-black text-cyan-400' : 'bg-gray-50 text-gray-500 hover:bg-gray-100'}`}
                            >
                                REGISTER NEW
                            </button>
                        </div>
                        
                        <div className="p-8">
                            {accountMode === 'SIGN_IN' ? (
                                <div className="space-y-6">
                                    <div>
                                        <label className="block text-xs font-black tracking-widest text-gray-500 mb-2">ORGANIZATION NAME</label>
                                        <input 
                                            type="text" 
                                            className="w-full bg-gray-50 border border-gray-200 rounded-md p-4 text-sm font-bold text-gray-900 focus:border-cyan-500 focus:bg-white outline-none transition"
                                            placeholder="e.g. HDFC Bank"
                                            value={signInName}
                                            onChange={(e) => setSignInName(e.target.value)}
                                        />
                                    </div>
                                    <button 
                                        onClick={handleSignIn}
                                        disabled={!signInName}
                                        className="w-full bg-black text-cyan-400 hover:opacity-80 font-black tracking-widest py-4 rounded-md transition disabled:cursor-not-allowed shadow-md"
                                    >
                                        SIGN IN
                                    </button>
                                    {signInError && <div className="text-red-500 text-xs font-bold mt-2 tracking-widest text-center">{signInError}</div>}
                                </div>
                            ) : (
                                <div className="space-y-6">
                                    <div>
                                        <label className="block text-xs font-black tracking-widest text-gray-500 mb-2">ORGANIZATION NAME</label>
                                        <input 
                                            type="text" 
                                            className="w-full bg-gray-50 border border-gray-200 rounded-md p-4 text-sm font-bold text-gray-900 focus:border-cyan-500 focus:bg-white outline-none transition"
                                            placeholder="e.g. SEBI"
                                            value={regName}
                                            onChange={(e) => setRegName(e.target.value)}
                                        />
                                    </div>
                                    <div>
                                        <label className="block text-xs font-black tracking-widest text-gray-500 mb-2">ENTITY TYPE</label>
                                        <select 
                                            className="w-full bg-gray-50 border border-gray-200 rounded-md p-4 text-sm font-bold text-gray-900 focus:border-cyan-500 focus:bg-white outline-none transition appearance-none"
                                            value={regType}
                                            onChange={(e) => setRegType(e.target.value)}
                                        >
                                            <option value="bank">Bank / Financial Institution</option>
                                            <option value="regulator">Regulator</option>
                                            <option value="broker">Broker</option>
                                            <option value="news">News Broadcaster</option>
                                        </select>
                                    </div>
                                    <button 
                                        onClick={handleRegister}
                                        disabled={!regName}
                                        className="w-full bg-black text-cyan-400 hover:opacity-80 font-black tracking-widest py-4 rounded-md transition disabled:cursor-not-allowed shadow-md"
                                    >
                                        REGISTER & GENERATE KEYS
                                    </button>
                                    {regError && <div className="text-red-500 text-xs font-bold mt-2 tracking-widest text-center">{regError}</div>}
                                </div>
                            )}
                        </div>
                    </div>
                ) : (
                    <div className="max-w-2xl">
                        <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-8 mb-8 flex items-center justify-between">
                            <div>
                                <h3 className="text-emerald-800 font-black tracking-widest mb-1 flex items-center gap-2"><CheckCircle2 size={18} /> ACCESS GRANTED</h3>
                                <p className="text-emerald-600 text-sm font-medium">You are securely signed in as {loggedInEntity.name}.</p>
                            </div>
                            <div className="bg-white p-3 rounded-lg shadow-sm border border-emerald-100">
                                <div className="text-[10px] text-gray-400 font-black tracking-widest mb-1">ENTITY ID</div>
                                <div className="font-mono text-xs font-bold text-gray-900">{loggedInEntity.id}</div>
                            </div>
                        </div>

                        {regResult && regResult.private_key_pem && (
                            <div className="mt-8">
                                <PrivateKeyCard 
                                    pem={regResult.private_key_pem} 
                                    revealed={hasRevealedKey} 
                                    onReveal={() => setHasRevealedKey(true)} 
                                />
                            </div>
                        )}
                    </div>
                )}
            </div>
        )}

        {/* PUBLISH TAB */}
        {activeTab === 'PUBLISH' && loggedInEntity && (
            <div>
                 <div className="flex items-center gap-4 mb-10">
                    <FileSignature size={40} className="text-cyan-500" />
                    <div>
                        <h1 className="text-3xl font-black text-gray-900 tracking-widest uppercase">Sign Asset</h1>
                        <p className="text-gray-500 text-sm mt-1 tracking-wide">Securely sign media with your offline private key.</p>
                    </div>
                </div>

                <div className="max-w-3xl bg-white border border-gray-200 rounded-xl p-8 shadow-sm">
                    {pubStatus === 'SUCCESS' ? (
                        <div className="text-center py-16 animate-in zoom-in duration-500">
                            <div className="w-24 h-24 bg-emerald-100 rounded-full flex items-center justify-center mx-auto mb-6 shadow-inner">
                                <CheckCircle2 size={48} className="text-emerald-500" />
                            </div>
                            <h2 className="text-2xl font-black text-gray-900 tracking-widest mb-2">ASSET SECURED</h2>
                            <p className="text-gray-500 text-sm max-w-md mx-auto mb-8 font-medium leading-relaxed">
                                Your asset has been {pubResult?.algorithm?.startsWith('sha256') ? 'exactly hashed' : 'fuzzy-hashed'}, mathematically signed, and permanently recorded in the immutable PRISM registry. 
                            </p>
                            <div className="bg-gray-50 border border-gray-200 p-6 rounded-lg inline-block text-left mb-8 shadow-sm">
                                <div className="text-[10px] text-gray-500 font-black tracking-widest mb-1">SIGNED ASSET ID</div>
                                <div className="text-sm font-mono text-cyan-700 font-bold">{pubResult?.id}</div>
                                <div className="text-[10px] text-gray-500 font-black tracking-widest mb-1 mt-4">ALGORITHM</div>
                                <div className="text-xs font-mono text-gray-800 font-bold">{pubResult?.algorithm}</div>
                            </div>
                            <br/>
                            <button 
                                onClick={() => { setPubStatus('IDLE'); setPubFile(null); setPubText(''); setPubResult(null); }}
                                className="bg-black hover:bg-gray-800 text-white font-black tracking-widest px-8 py-4 rounded-md transition shadow-md"
                            >
                                SIGN ANOTHER ASSET
                            </button>
                        </div>
                    ) : (
                        <div className="space-y-8">
                            <div className="flex gap-6 h-48">
                                {/* TEXT INPUT SIDE */}
                                <div className={`w-1/2 bg-gray-50 border-2 border-dashed border-gray-300 rounded-xl p-4 flex flex-col transition focus-within:border-cyan-500 focus-within:bg-cyan-50/50 ${pubFile ? 'opacity-40 pointer-events-none' : ''}`}>
                                    <textarea 
                                        className="w-full flex-1 bg-transparent text-gray-900 resize-none outline-none border-none text-sm font-bold leading-relaxed mb-2"
                                        placeholder="Paste Text to Sign..."
                                        value={pubText}
                                        onChange={(e) => setPubText(e.target.value)}
                                        disabled={pubFile !== null}
                                    />
                                </div>

                                {/* FILE UPLOAD SIDE */}
                                <div 
                                    onClick={() => !pubText && document.getElementById('portal-file-upload')?.click()}
                                    className={`w-1/2 bg-gray-50 border-2 border-dashed border-gray-300 rounded-xl flex flex-col items-center justify-center cursor-pointer hover:border-cyan-500 hover:bg-cyan-50/50 transition group ${pubText ? 'opacity-40 pointer-events-none' : ''}`}
                                >
                                    <UploadCloud size={48} className="text-gray-400 group-hover:text-cyan-500 mb-4 transition" strokeWidth={1.5} />
                                    <div className="text-gray-500 font-black text-sm tracking-widest group-hover:text-cyan-700 transition text-center px-4">
                                        {pubFile ? pubFile.name : "SELECT MEDIA TO SIGN"}
                                    </div>
                                    {pubFile && (
                                        <div 
                                            onClick={(e) => { e.stopPropagation(); setPubFile(null); }}
                                            className="mt-2 text-xs font-bold text-red-500 hover:text-red-700"
                                        >
                                            Remove
                                        </div>
                                    )}
                                    <input 
                                        type="file" 
                                        id="portal-file-upload" 
                                        className="hidden" 
                                        onChange={(e) => {
                                            if (e.target.files && e.target.files.length > 0) {
                                                setPubFile(e.target.files[0]);
                                            }
                                        }}
                                    />
                                </div>
                            </div>
                            
                            {/* RESET BUTTON FOR TEXT */}
                            {pubText && (
                                <div className="flex justify-end mt-[-1rem]">
                                    <button 
                                        onClick={() => setPubText('')}
                                        className="text-xs font-bold text-red-500 hover:text-red-700 uppercase tracking-widest"
                                    >
                                        Clear Text
                                    </button>
                                </div>
                            )}

                            <div>
                                <label className="block text-[10px] font-black tracking-widest text-gray-500 mb-2">ASSET TITLE (OPTIONAL)</label>
                                <input 
                                    type="text" 
                                    className="w-full bg-gray-50 border border-gray-200 rounded-md p-3 text-sm font-bold text-gray-900 focus:border-cyan-500 focus:bg-white outline-none transition"
                                    value={pubTitle}
                                    onChange={(e) => setPubTitle(e.target.value)}
                                />
                            </div>

                            <div>
                                <label className="flex items-center gap-2 text-[10px] font-black tracking-widest text-gray-500 mb-2">
                                    <KeyRound size={12} /> PRIVATE KEY (PASTE HERE)
                                </label>
                                <textarea 
                                    className="w-full h-32 bg-black border border-gray-800 rounded-md p-4 text-[10px] font-mono text-[#39FF14] focus:border-cyan-500 outline-none transition resize-none placeholder-gray-800 shadow-inner"
                                    placeholder="-----BEGIN PRIVATE KEY-----"
                                    value={pubKeyPem}
                                    onChange={(e) => setPubKeyPem(e.target.value)}
                                />
                                <p className="text-[10px] font-medium text-gray-500 mt-2">Your key remains in the browser. It will be cleared immediately after signing.</p>
                            </div>

                            <button 
                                onClick={handlePublish}
                                disabled={!pubFile || !pubKeyPem || pubStatus === 'SIGNING'}
                                className="w-full bg-black text-cyan-400 hover:opacity-80 font-black tracking-widest py-4 rounded-md transition disabled:cursor-not-allowed flex justify-center items-center gap-2 shadow-md mt-4"
                            >
                                {pubStatus === 'SIGNING' ? (
                                    <><div className="w-4 h-4 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin"></div> SIGNING...</>
                                ) : (
                                    "AUTHORIZE & PUBLISH"
                                )}
                            </button>
                            
                            {pubError && <div className="text-red-500 text-xs font-bold text-center tracking-widest mt-2">{pubError}</div>}
                        </div>
                    )}
                </div>
            </div>
        )}

        {/* REVOKE TAB */}
        {activeTab === 'REVOKE' && loggedInEntity && (
            <div>
                 <div className="flex items-center gap-4 mb-10">
                    <Key size={40} className="text-red-500" />
                    <div>
                        <h1 className="text-3xl font-black text-gray-900 tracking-widest uppercase">Revoke Key</h1>
                        <p className="text-gray-500 text-sm mt-1 tracking-wide">Compromised key? Revoke it immediately and generate a new one.</p>
                    </div>
                </div>

                <div className="max-w-2xl bg-white border border-gray-200 rounded-xl p-8 shadow-sm">
                    {revokeStatus === 'SUCCESS' ? (
                        <div className="animate-in fade-in duration-500">
                             <div className="bg-emerald-50 border border-emerald-200 p-4 rounded-lg mb-8">
                                <div className="flex items-center gap-2 text-emerald-700 font-black text-sm tracking-widest mb-1">
                                    <CheckCircle2 size={16} /> ROTATION SUCCESSFUL
                                </div>
                                <p className="text-emerald-600 text-xs font-medium">Your old key is revoked. A new public key is bound to your entity.</p>
                            </div>
                            <PrivateKeyCard 
                                pem={revokeResult.private_key_pem} 
                                revealed={revokeHasRevealed} 
                                onReveal={() => setRevokeHasRevealed(true)} 
                            />
                            <button onClick={() => setRevokeStatus('IDLE')} className="mt-8 text-xs font-bold text-gray-400 hover:text-black">← Back</button>
                        </div>
                    ) : (
                        <div className="text-center py-8">
                            <AlertTriangle size={64} className="text-red-500 mx-auto mb-6" />
                            <h2 className="text-xl font-black text-gray-900 tracking-widest mb-4">CRITICAL ACTION</h2>
                            <p className="text-gray-500 text-sm mb-8 leading-relaxed max-w-md mx-auto font-medium">
                                This will permanently revoke your current active public key. All future verifications will require assets to be signed with the newly generated private key.
                            </p>
                            <button 
                                onClick={handleRotateKey}
                                disabled={revokeStatus === 'ROTATING'}
                                className="bg-red-500 hover:bg-red-600 text-white font-black tracking-widest px-8 py-4 rounded-md transition disabled:opacity-50"
                            >
                                {revokeStatus === 'ROTATING' ? 'ROTATING...' : 'REVOKE & ROTATE KEY'}
                            </button>
                            {revokeError && <div className="text-red-500 text-xs font-bold mt-4 tracking-widest">{revokeError}</div>}
                        </div>
                    )}
                </div>
            </div>
        )}

        {/* ASSETS TAB */}
        {activeTab === 'ASSETS' && loggedInEntity && (
            <div>
                 <div className="flex items-center gap-4 mb-10">
                    <List size={40} className="text-cyan-500" />
                    <div>
                        <h1 className="text-3xl font-black text-gray-900 tracking-widest uppercase">Signed Assets</h1>
                        <p className="text-gray-500 text-sm mt-1 tracking-wide">A cryptographic ledger of everything your entity has signed.</p>
                    </div>
                </div>

                <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
                    {assetsLoading ? (
                        <div className="p-12 text-center text-gray-400 font-black tracking-widest text-sm animate-pulse">
                            FETCHING LEDGER...
                        </div>
                    ) : assets.length === 0 ? (
                        <div className="p-12 text-center text-gray-400 font-bold text-sm">
                            No assets have been signed by this entity yet.
                        </div>
                    ) : (
                        <table className="w-full text-left">
                            <thead className="bg-black border-b border-gray-800">
                                <tr>
                                    <th className="px-6 py-4 text-[10px] font-black tracking-widest text-cyan-400">ASSET ID</th>
                                    <th className="px-6 py-4 text-[10px] font-black tracking-widest text-cyan-400">TITLE</th>
                                    <th className="px-6 py-4 text-[10px] font-black tracking-widest text-cyan-400">MEDIA</th>
                                    <th className="px-6 py-4 text-[10px] font-black tracking-widest text-cyan-400">DATE</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-100">
                                {assets.map(asset => (
                                    <tr key={asset.id} className="hover:bg-gray-50 transition">
                                        <td className="px-6 py-4 font-mono text-xs text-gray-500">{asset.id}</td>
                                        <td className="px-6 py-4 text-sm font-bold text-gray-900">{asset.title || '-'}</td>
                                        <td className="px-6 py-4">
                                            <span className="bg-cyan-50 text-cyan-700 px-2 py-1 rounded text-[10px] font-black tracking-widest uppercase border border-cyan-100">
                                                {asset.media_type}
                                            </span>
                                        </td>
                                        <td className="px-6 py-4 text-xs font-bold text-gray-500">
                                            {new Date(asset.signed_at).toLocaleDateString()}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    )}
                </div>
            </div>
        )}

      </div>
    </div>
  );
}
