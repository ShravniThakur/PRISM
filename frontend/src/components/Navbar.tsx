import { Link } from 'react-router-dom';

export default function Navbar() {
  return (
    <nav className="w-full flex items-center justify-between px-8 py-6 bg-black border-b border-gray-800 z-50 relative">
      <Link to="/" className="text-cyan-400 font-bold text-xl tracking-widest hover:text-cyan-300 transition">PRISM</Link>
      <Link to="/dashboard" className="text-cyan-400 font-bold text-sm tracking-widest hover:text-cyan-300">
        ANALYSE
      </Link>
    </nav>
  );
}
