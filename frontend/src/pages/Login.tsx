import { useNavigate, Link } from 'react-router-dom';
import { GoogleLogin } from '@react-oauth/google';
import { api } from '../api';

export default function Login() {
    const navigate = useNavigate();

    const handleSuccess = async (credentialResponse: any) => {
        try {
            if (credentialResponse.credential) {
                const data = await api.googleLogin(credentialResponse.credential);
                localStorage.setItem('prism_token', data.access_token);
                localStorage.setItem('prism_user', JSON.stringify(data.user));
                navigate('/dashboard');
            }
        } catch (error) {
            console.error("Login failed:", error);
            alert("Login failed. Please try again.");
        }
    };

    return (
        <div className="flex h-screen bg-black text-white font-sans overflow-hidden">
            
            {/* Left Column - Login Details */}
            <div className="w-full md:w-1/2 flex flex-col items-center justify-center p-12 bg-black z-10 relative overflow-hidden">
                
                {/* Cybersecurity Grid Background - Top Left */}
                <div className="absolute top-0 left-0 w-full h-full bg-[url('https://transparenttextures.com/patterns/cubes.png')] opacity-100 animate-pulse [mask-image:radial-gradient(circle_at_top_left,black_20%,transparent_60%)] pointer-events-none -z-10"></div>
                
                {/* Cybersecurity Grid Background - Bottom Right */}
                <div className="absolute bottom-0 right-0 w-full h-full bg-[url('https://transparenttextures.com/patterns/cubes.png')] opacity-100 animate-pulse [mask-image:radial-gradient(circle_at_bottom_right,black_20%,transparent_60%)] pointer-events-none -z-10"></div>
                
                <Link to="/" className="text-4xl sm:text-6xl font-black bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text text-transparent mb-6 sm:mb-8 tracking-wider uppercase hover:opacity-80 transition-opacity hover:scale-105 transform inline-block">
                    PRISM
                </Link>
                
                <p className="text-white text-center text-base sm:text-xl font-medium mb-8 sm:mb-12 max-w-lg">
                    Zero-Trust AI Threat Detection.<br/>
                    Sign in to access your analysis portal.
                </p>

                <div className="w-full max-w-md flex justify-center mb-12 transform scale-[1.15] md:scale-[1.2]">
                    <GoogleLogin
                        onSuccess={handleSuccess}
                        onError={() => {
                            console.log('Login Failed');
                            alert('Login Failed');
                        }}
                        theme="outline"
                        shape="pill"
                        text="continue_with"
                        size="large"
                        width="320"
                    />
                </div>
                
                <p className="text-white text-center text-base sm:text-lg font-medium opacity-90 max-w-md mb-8 sm:mb-12">
                    Authorized personnel only. All access is monitored.
                </p>
                
                <Link 
                    to="/portal" 
                    className="w-full max-w-md text-center border-2 border-cyan-400 text-cyan-400 font-black tracking-widest text-xl py-4 rounded-xl hover:bg-cyan-900/30 transition-colors"
                >
                    ENTITY PORTAL
                </Link>
                
            </div>

            {/* Right Column - Image */}
            <div className="hidden md:flex md:w-1/2 h-full bg-black items-center justify-start p-12">
                <img 
                    src="/login.png" 
                    alt="PRISM Login Security" 
                    className="w-full max-w-xl object-contain rounded-2xl shadow-[0_0_50px_rgba(34,211,238,0.15)]"
                />
            </div>

        </div>
    );
}
