import { Button } from "@/components/ui/button";

const Header = () => {
  return (
    <header className="fixed top-0 w-full bg-white/95 backdrop-blur-sm border-b border-gray-200 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          {/* Logo */}
          <div className="flex items-center">
            <h1 className="text-2xl font-bold text-summare-navy">Summare</h1>
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
            <Button variant="ghost" className="hidden md:block text-summare-gray hover:text-summare-navy">
              Logga in
            </Button>
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
