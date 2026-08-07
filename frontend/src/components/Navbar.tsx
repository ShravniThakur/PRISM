import { Link } from 'react-router-dom';

export default function Navbar() {
  return (
    <nav className="w-full flex items-center justify-between px-4 sm:px-8 py-4 sm:py-6 bg-black border-b border-gray-800 z-50 relative">
      <Link to="/" className="text-cyan-400 font-bold text-lg sm:text-xl tracking-widest hover:text-cyan-300 transition">PRISM</Link>
      <div className="flex items-center gap-4">
        <Link to="/portal" className="text-gray-400 font-bold text-xs tracking-widest hover:text-cyan-300 hidden sm:block">
          ENTITY PORTAL
        </Link>
        <Link to="/dashboard" className="text-cyan-400 font-bold text-xs sm:text-sm tracking-widest hover:text-cyan-300">
          ANALYSE
        </Link>
      </div>
    </nav>
  );
}
