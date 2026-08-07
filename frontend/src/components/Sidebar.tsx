import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Activity, Clock, LogOut } from 'lucide-react';

export default function Sidebar() {
  const location = useLocation();
  const navigate = useNavigate();
  const currentPath = location.pathname;

  const handleSignOut = () => {
      localStorage.removeItem('prism_token');
      localStorage.removeItem('prism_user');
      navigate('/login');
  };

  return (
    <>
      {/* Top Navbar */}
      <div className="w-full h-[60px] md:h-[72px] bg-black border-b border-gray-800 fixed top-0 left-0 z-50 flex items-center px-4 md:px-8">
        <Link to="/" className="text-cyan-400 font-bold text-lg md:text-xl tracking-widest hover:text-cyan-300 transition">
          PRISM
        </Link>
      </div>

      {/* Sidebar — hidden on mobile, visible on md+ */}
      <div className="hidden md:flex w-56 h-[calc(100vh-72px)] bg-black border-r border-gray-800 flex-col text-white fixed top-[72px] left-0 z-40 pt-4 justify-between pb-8">
        <div>
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

        <div>
            <button
                onClick={handleSignOut}
                className="w-full flex items-center gap-4 px-8 py-5 text-sm font-bold tracking-widest text-gray-400 hover:text-red-400 transition"
            >
                <LogOut size={20} />
                SIGN OUT
            </button>
        </div>
      </div>

      {/* Mobile Bottom Navigation — visible only on mobile */}
      <div className="md:hidden fixed bottom-0 left-0 right-0 z-50 bg-black border-t border-gray-800 flex items-center justify-around h-16">
        <Link
          to="/dashboard"
          className={`flex flex-col items-center gap-1 flex-1 py-2 text-[10px] font-black tracking-widest transition ${
            currentPath === '/dashboard' ? 'text-cyan-400' : 'text-gray-500'
          }`}
        >
          <Activity size={20} />
          ANALYSE
        </Link>
        <Link
          to="/history"
          className={`flex flex-col items-center gap-1 flex-1 py-2 text-[10px] font-black tracking-widest transition ${
            currentPath === '/history' ? 'text-cyan-400' : 'text-gray-500'
          }`}
        >
          <Clock size={20} />
          HISTORY
        </Link>
        <button
          onClick={handleSignOut}
          className="flex flex-col items-center gap-1 flex-1 py-2 text-[10px] font-black tracking-widest text-gray-500 hover:text-red-400 transition"
        >
          <LogOut size={20} />
          SIGN OUT
        </button>
      </div>
    </>
  );
}
