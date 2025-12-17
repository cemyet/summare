import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useNavigate } from "react-router-dom";
import { API_BASE_URL } from "@/config/api";

interface LoginPopupProps {
  isOpen: boolean;
  onClose: () => void;
  buttonRef: React.RefObject<HTMLButtonElement>;
}

const LoginPopup = ({ isOpen, onClose, buttonRef }: LoginPopupProps) => {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const popupRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  // Close popup when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        popupRef.current &&
        !popupRef.current.contains(event.target as Node) &&
        buttonRef.current &&
        !buttonRef.current.contains(event.target as Node)
      ) {
        onClose();
      }
    };

    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }

    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isOpen, onClose, buttonRef]);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setIsLoading(true);

    try {
      const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ email, password }),
      });

      const data = await response.json();

      if (data.success) {
        // Store user session in localStorage
        localStorage.setItem("summare_user", JSON.stringify({
          userId: data.user_id,
          username: data.username,
          organizations: data.organizations,
        }));
        
        // Navigate to Mina Sidor
        navigate("/mina-sidor");
        onClose();
      } else {
        setError(data.message || "Inloggningen misslyckades");
      }
    } catch (err) {
      console.error("Login error:", err);
      setError("Ett fel uppstod. Försök igen.");
    } finally {
      setIsLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div
      ref={popupRef}
      className="absolute top-full right-0 mt-2 w-80 bg-white border border-gray-200 rounded-lg shadow-xl z-50 animate-in slide-in-from-top-2 duration-200"
      style={{ transformOrigin: "top right" }}
    >
      <div className="p-5">
        <h3 className="text-lg font-semibold text-summare-navy mb-4">Logga in</h3>
        
        <form onSubmit={handleLogin} className="space-y-4">
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">
              Email
            </label>
            <Input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="din@email.se"
              className="w-full"
              required
              autoFocus
            />
          </div>
          
          <div>
            <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">
              Lösenord
            </label>
            <Input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••"
              className="w-full"
              required
            />
          </div>

          {error && (
            <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 rounded-md">
              <svg className="w-4 h-4 text-red-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
              </svg>
              <p className="text-sm text-red-600">{error}</p>
            </div>
          )}

          <Button
            type="submit"
            className="w-full bg-summare-navy hover:bg-summare-navy/90 text-white"
            disabled={isLoading}
          >
            {isLoading ? (
              <span className="flex items-center gap-2">
                <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Loggar in...
              </span>
            ) : (
              "Logga in"
            )}
          </Button>
        </form>

        <p className="mt-4 text-xs text-gray-500 text-center">
          Lösenordet skickades till din email vid betalning
        </p>
      </div>
    </div>
  );
};

const Header = () => {
  const [isLoginOpen, setIsLoginOpen] = useState(false);
  const loginButtonRef = useRef<HTMLButtonElement>(null);
  const navigate = useNavigate();

  // Check if user is already logged in
  const user = localStorage.getItem("summare_user");
  const isLoggedIn = !!user;

  const handleLogout = () => {
    localStorage.removeItem("summare_user");
    navigate("/");
  };

  return (
    <header className="fixed top-0 w-full bg-white/95 backdrop-blur-sm border-b border-gray-200 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          {/* Logo */}
          <div className="flex items-center">
            <a href="/" className="text-3xl font-bold text-summare-navy hover:opacity-80 transition-opacity">
              Summare
            </a>
          </div>

          {/* Navigation - Centered */}
          <nav className="hidden md:flex space-x-8 absolute left-1/2 transform -translate-x-1/2">
            <a href="#" className="text-summare-gray hover:text-summare-navy transition-colors">
              Priser
            </a>
            <a href="#" className="text-summare-gray hover:text-summare-navy transition-colors">
              AI verktyg
            </a>
            <a href="#" className="text-summare-gray hover:text-summare-navy transition-colors">
              Support
            </a>
          </nav>

          {/* CTA Buttons */}
          <div className="flex items-center space-x-4">
            {isLoggedIn ? (
              <>
                <Button
                  variant="ghost"
                  className="hidden md:flex items-center gap-2 text-summare-gray hover:text-summare-navy"
                  onClick={() => navigate("/mina-sidor")}
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                  </svg>
                  Mina sidor
                </Button>
                <Button
                  variant="ghost"
                  className="hidden md:block text-summare-gray hover:text-summare-navy"
                  onClick={handleLogout}
                >
                  Logga ut
                </Button>
              </>
            ) : (
              <div className="relative">
                <Button
                  ref={loginButtonRef}
                  variant="ghost"
                  className="hidden md:block text-summare-gray hover:text-summare-navy"
                  onClick={() => setIsLoginOpen(!isLoginOpen)}
                >
                  Logga in
                </Button>
                <LoginPopup
                  isOpen={isLoginOpen}
                  onClose={() => setIsLoginOpen(false)}
                  buttonRef={loginButtonRef}
                />
              </div>
            )}
            <Button className="btn-hero" asChild>
              <a href="/app">Kom igång</a>
            </Button>
          </div>
        </div>
      </div>
    </header>
  );
};

export default Header;
