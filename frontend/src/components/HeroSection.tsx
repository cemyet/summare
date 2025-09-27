import { Button } from "@/components/ui/button";

const HeroSection = () => {
  return (
    <section 
      className="min-h-screen flex items-center justify-center relative overflow-hidden"
      style={{
        backgroundImage: `url('/lovable-uploads/bakgrund.gif')`,
        backgroundSize: 'cover',
        backgroundPosition: 'center',
        backgroundRepeat: 'no-repeat',
        animation: 'backgroundSpeed 0.8s ease-in-out infinite'
      }}
    >
      
      {/* Radial gradient overlay for better text readability */}
      <div className="absolute inset-0" style={{
        background: 'radial-gradient(circle at center, rgba(255,255,255,0.8) 0%, rgba(255,255,255,0.25) 50%, rgba(255,255,255,0) 100%)'
      }}></div>
      
      <div className="relative z-10 text-center max-w-4xl mx-auto px-4 sm:px-6 lg:px-8" style={{ transform: 'translateY(-16px)' }}>
        {/* Logo/Brand */}
        <div className="mb-8">
          <h1 className="text-6xl md:text-7xl font-bold text-summare-navy mb-4">
            Summare
          </h1>
        </div>

        {/* Main Heading */}
        <h2 className="text-hero mb-8 animate-fade-in">
          Digitala årsredovisningar<br />
          för egenföretagare
        </h2>

        {/* Subtitle */}
        <p className="text-subtitle mb-8 max-w-2xl mx-auto animate-fade-in">
          Enkelt. Pålitligt. Prisvärt. Skapa en professionell<br />
          årsredovisning och skattedeklaration med<br />
          vårt AI verktyg på bara ett par minuter
        </p>

        {/* CTA Button */}
        <div className="animate-fade-in">
          <Button className="btn-hero text-lg" asChild>
            <a href="/app">Prova gratis nu</a>
          </Button>
        </div>

        {/* Trust indicators */}
        <div className="mt-12 text-base text-summare-gray">
          <p>Betrodd av 5,000+ företag</p>
        </div>
      </div>
    </section>
  );
};

export default HeroSection;
