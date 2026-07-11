import { Link, useLocation } from 'react-router-dom';
import { Activity, Clock } from 'lucide-react';

export default function Sidebar() {
  const location = useLocation();
  const currentPath = location.pathname;

  return (
    <>
      {/* Top Navbar */}
      <div className="w-full h-[72px] bg-black border-b border-gray-800 fixed top-0 left-0 z-50 flex items-center px-8">
        <Link to="/" className="text-cyan-400 font-bold text-xl tracking-widest hover:text-cyan-300 transition">
          PRISM
        </Link>
      </div>

      {/* Sidebar */}
      <div className="w-56 h-[calc(100vh-72px)] bg-black border-r border-gray-800 flex flex-col text-white fixed top-[72px] left-0 z-40 pt-4">
        <Link 
          to="/dashboard" 
          className={`flex items-center gap-4 px-8 py-5 text-sm font-bold tracking-widest ${currentPath === '/dashboard' ? 'text-cyan-400 border-l-2 border-cyan-400 bg-gray-900/50' : 'text-gray-400 hover:text-white'}`}
        >
          <Activity size={20} />
          ANALYSE
        </Link>
        <Link 
          to="/history" 
          className={`flex items-center gap-4 px-8 py-5 text-sm font-bold tracking-widest ${currentPath === '/history' ? 'text-cyan-400 border-l-2 border-cyan-400 bg-gray-900/50' : 'text-gray-400 hover:text-white'}`}
        >
          <Clock size={20} />
          HISTORY
        </Link>
      </div>
    </>
  );
}
