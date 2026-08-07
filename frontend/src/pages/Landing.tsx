import Navbar from '../components/Navbar';
import { Link } from 'react-router-dom';

export default function Landing() {
  return (
    <div className="min-h-screen bg-black text-white font-sans overflow-x-hidden">
      <Navbar />

      {/* Hero Section */}
      <section className="relative w-full min-h-[480px] md:h-[600px] flex items-center overflow-hidden bg-black">
        {/* Cybersecurity Grid Background (Restricted to Left Side) */}
        <div className="absolute top-0 left-0 w-[60%] h-full bg-[url('https://transparenttextures.com/patterns/cubes.png')] opacity-100 animate-pulse [mask-image:linear-gradient(to_right,black_80%,transparent)]"></div>
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-black/50 to-black pointer-events-none z-0"></div>

        {/* Hero Background Image - hidden on mobile */}
        <div className="hidden sm:flex absolute right-0 top-0 w-[55%] h-full items-center justify-center opacity-90 mix-blend-screen">
          <img src="/hero-triangle.png" alt="PRISM Core" className="w-[80%] h-auto object-contain transform scale-110" />
        </div>

        <div className="relative z-10 px-6 sm:px-12 lg:px-16 max-w-4xl">
          <div className="inline-block border border-gray-800 bg-gray-900/50 backdrop-blur-sm text-cyan-400 font-bold text-[10px] sm:text-xs tracking-widest px-3 sm:px-4 py-1.5 rounded-full mb-4 sm:mb-6">
            ENTERPRISE-GRADE AI THREAT DETECTION
          </div>
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold leading-tight mb-4 sm:mb-6">
            <span className="text-white">Phishing and</span><br />
            <span className="text-white">Representation</span><br />
            <span className="bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text text-transparent">Integrity Surveillance</span><br />
            <span className="text-white">for Markets</span>
          </h1>
          <div className="flex flex-wrap gap-3 sm:gap-4 mt-6 sm:mt-8">
            <Link to="/dashboard" className="bg-cyan-400 text-black px-6 sm:px-8 py-3 sm:py-4 font-black text-xs sm:text-sm tracking-widest hover:bg-cyan-300 hover:shadow-[0_0_20px_rgba(34,211,238,0.4)] transition-all duration-300 rounded-sm">
              ANALYSE
            </Link>
            <Link to="/portal" className="border border-cyan-400 text-cyan-400 px-6 sm:px-8 py-3 sm:py-4 font-black text-xs sm:text-sm tracking-widest hover:bg-cyan-900/30 hover:shadow-[0_0_20px_rgba(34,211,238,0.2)] transition-all duration-300 rounded-sm">
              ENTITY PORTAL
            </Link>
          </div>
        </div>
      </section>

      {/* Partners Section */}
      <section className="w-full bg-white text-black py-6 md:py-8 border-y border-gray-200">
        <div className="flex flex-wrap justify-center md:justify-around items-center gap-6 px-6 md:px-16">
          <img src="/logo-sebi.png" alt="SEBI" className="h-7 md:h-10 object-contain" />
          <img src="/logo-groww.png" alt="Groww" className="h-7 md:h-10 object-contain" />
          <img src="/logo-bse.png" alt="BSE" className="h-7 md:h-10 object-contain" />
          <img src="/logo-nse.png" alt="NSE" className="h-7 md:h-10 object-contain" />
          <img src="/logo-zerodha.png" alt="Zerodha" className="h-7 md:h-10 object-contain" />
        </div>
      </section>

      {/* Stats Section */}
      <section className="bg-white text-black pt-12 md:pt-20 text-center relative overflow-hidden">
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full h-full bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-gray-100 via-white to-white pointer-events-none -z-10"></div>
        <p className="max-w-4xl mx-auto px-6 md:px-16 text-lg md:text-2xl font-bold text-gray-800 mb-10 md:mb-16 leading-relaxed">
          Securing billions in market capitalisation. PRISM is the trusted cryptographic layer and AI surveillance engine empowering India's most critical regulatory bodies, exchanges, and Tier-1 brokerages to defend against synthetic media manipulation.
        </p>

        <div className="flex flex-col sm:flex-row justify-around items-center mt-8 md:mt-12 w-full bg-[#E8EAEF] rounded-t-[2rem] md:rounded-t-[3rem] py-12 md:py-20 px-4 md:px-8 gap-8 sm:gap-0 shadow-inner">
          <div className="group cursor-default hover:-translate-y-2 transition-transform duration-300">
            <div className="text-5xl md:text-7xl font-black mb-2 text-gray-800 group-hover:text-cyan-600 transition-colors">01</div>
            <div className="text-gray-600 text-sm font-black tracking-widest uppercase">3 Layers<br />Of Independent Defense</div>
          </div>
          <div className="group cursor-default hover:-translate-y-2 transition-transform duration-300">
            <div className="text-5xl md:text-7xl font-black mb-2 text-gray-800 group-hover:text-cyan-600 transition-colors">02</div>
            <div className="text-gray-600 text-sm font-black tracking-widest uppercase">100%<br />Cryptographic Certainty</div>
          </div>
          <div className="group cursor-default hover:-translate-y-2 transition-transform duration-300">
            <div className="text-5xl md:text-7xl font-black mb-2 text-gray-800 group-hover:text-cyan-600 transition-colors">03</div>
            <div className="text-gray-600 text-sm font-black tracking-widest uppercase">99.5%<br />Deepfake Detection Rate</div>
          </div>
        </div>
      </section>

      {/* Core Capabilities */}
      <section className="py-12 md:py-24 bg-white text-black text-center">
        <h2 className="text-3xl md:text-4xl font-black mb-6 md:mb-8">Our Core Capabilities</h2>
        <div className="bg-black py-4 mb-10 md:mb-20">
          <p className="text-white text-base md:text-lg font-medium max-w-4xl mx-auto px-4">A modular, <span className="text-cyan-400 font-bold">tri-layer architecture</span> engineered to authenticate legitimate financial entities and neutralize AI-generated threats in <span className="text-cyan-400 font-bold">real-time</span>.</p>
        </div>

        <div className="relative w-full overflow-hidden mt-8 md:mt-12 py-10">
          {/* Gradient Fades for edges */}
          <div className="absolute top-0 left-0 w-16 md:w-32 h-full bg-gradient-to-r from-white to-transparent z-10 pointer-events-none"></div>
          <div className="absolute top-0 right-0 w-16 md:w-32 h-full bg-gradient-to-l from-white to-transparent z-10 pointer-events-none"></div>

          {/* Scrolling Track */}
          <div className="flex w-max animate-marquee gap-6 md:gap-8 px-4">
            {/* Original Set */}
            {[
              { img: 'icon-crypto.png', title: 'Zero-Trust Cryptography', desc: 'Verifies entity identities using RSA-2048 asymmetric keys to prevent spoofing.' },
              { img: 'icon-visual.png', title: 'Visual Deepfake Detection', desc: 'Analyzes video streams for facial artifacts and temporal inconsistencies.' },
              { img: 'icon-audio.png', title: 'Synthetic Audio Analysis', desc: 'Detects AI-generated voice cloning through frequency artifact analysis.' },
              { img: 'icon-phishing.png', title: 'Linguistic Phishing Engines', desc: 'Identifies manipulative language and semantic threats in raw text.' },
              { img: 'icon-domain.png', title: 'Dynamic Domain Intelligence', desc: 'Cross-references URLs against live databases of known malicious vectors.' },
              { img: 'icon-decision.png', title: 'Cognitive Decision Engine', desc: 'Fuses multi-modal risk scores into a single definitive threat probability.' }
            ].map((item, i) => (
              <div key={`set1-${i}`} className="flex flex-col items-center text-center w-64 sm:w-80 md:w-96 bg-gray-50 border border-gray-200 p-6 md:p-8 rounded-2xl shadow-sm hover:shadow-xl hover:border-cyan-300 hover:-translate-y-1 transition-all duration-300 group">
                <img src={`/${item.img}`} alt={item.title} className="w-12 h-12 md:w-16 md:h-16 object-contain mb-4 md:mb-6 group-hover:scale-110 transition-transform duration-300" />
                <div className="font-black text-lg md:text-2xl text-gray-800 mb-3 md:mb-4 group-hover:text-cyan-700 transition-colors">{item.title}</div>
                <div className="text-gray-500 font-medium text-sm md:text-base leading-relaxed">{item.desc}</div>
              </div>
            ))}

            {/* Duplicated Set for Infinite Scroll */}
            {[
              { img: 'icon-crypto.png', title: 'Zero-Trust Cryptography', desc: 'Verifies entity identities using RSA-2048 asymmetric keys to prevent spoofing.' },
              { img: 'icon-visual.png', title: 'Visual Deepfake Detection', desc: 'Analyzes video streams for facial artifacts and temporal inconsistencies.' },
              { img: 'icon-audio.png', title: 'Synthetic Audio Analysis', desc: 'Detects AI-generated voice cloning through frequency artifact analysis.' },
              { img: 'icon-phishing.png', title: 'Linguistic Phishing Engines', desc: 'Identifies manipulative language and semantic threats in raw text.' },
              { img: 'icon-domain.png', title: 'Dynamic Domain Intelligence', desc: 'Cross-references URLs against live databases of known malicious vectors.' },
              { img: 'icon-decision.png', title: 'Cognitive Decision Engine', desc: 'Fuses multi-modal risk scores into a single definitive threat probability.' }
            ].map((item, i) => (
              <div key={`set2-${i}`} className="flex flex-col items-center text-center w-64 sm:w-80 md:w-96 bg-gray-50 border border-gray-200 p-6 md:p-8 rounded-2xl shadow-sm hover:shadow-xl hover:border-cyan-300 hover:-translate-y-1 transition-all duration-300 group">
                <img src={`/${item.img}`} alt={item.title} className="w-12 h-12 md:w-16 md:h-16 object-contain mb-4 md:mb-6 group-hover:scale-110 transition-transform duration-300" />
                <div className="font-black text-lg md:text-2xl text-gray-800 mb-3 md:mb-4 group-hover:text-cyan-700 transition-colors">{item.title}</div>
                <div className="text-gray-500 font-medium text-sm md:text-base leading-relaxed">{item.desc}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="bg-black py-12 md:py-24 px-6 md:px-16 flex flex-col-reverse md:flex-row items-center justify-between gap-10 border-t border-gray-900">
        {/* Lock Image */}
        <div className="w-full md:w-5/12 flex items-center justify-center">
          <img src="/cta-lock.png" alt="Secure Lock" className="w-full max-w-sm md:max-w-md h-auto object-contain rounded-xl transform scale-110" />
        </div>

        <div className="w-full md:w-6/12 md:pl-8">
          <h2 className="text-3xl md:text-5xl font-bold mb-4 md:mb-6 leading-tight">Protect Your<br />Investments Today</h2>
          <ul className="text-gray-400 list-disc pl-5 mb-8 md:mb-10 space-y-3 font-medium text-base md:text-lg">
            <li>Don't let generative AI compromise your financial security.</li>
            <li>Experience the power of the PRISM Threat Detection engine live in your browser.</li>
          </ul>
          <div className="flex flex-wrap gap-3 md:gap-4">
            <Link to="/dashboard" className="bg-cyan-400 text-black px-6 py-3 font-bold text-sm tracking-widest hover:bg-cyan-300">
              ANALYSE
            </Link>
            <Link to="/portal" className="border border-cyan-400 text-cyan-400 px-6 py-3 font-bold text-sm tracking-widest hover:bg-cyan-900/30">
              ENTITY PORTAL
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}
