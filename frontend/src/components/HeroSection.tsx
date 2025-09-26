import { Button } from "@/components/ui/button";

const HeroSection = () => {
  return (
    <section 
      className="min-h-screen flex items-center justify-center relative overflow-hidden"
      style={{
        backgroundImage: `url('/lovable-uploads/bakgrund.gif')`,
        backgroundSize: 'cover',
        backgroundPosition: 'center',
        backgroundRepeat: 'no-repeat'
      }}
    >
      
      {/* Overlay for better text readability */}
      <div className="absolute inset-0 bg-white/40"></div>
      
      <div className="relative z-10 text-center max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Logo/Brand */}
        <div className="mb-8">
          <h1 className="text-5xl md:text-6xl font-bold text-summare-navy mb-4">
            Summare
          </h1>
        </div>

        {/* Main Heading */}
        <h2 className="text-hero mb-6 animate-fade-in">
          Digitala årsredovisningar för egenföretagare
        </h2>

        {/* Subtitle */}
        <p className="text-subtitle mb-8 max-w-2xl mx-auto animate-fade-in">
          Enkelt. Snabbt. Pålitligt. Skapa professionella årsredovisningar på minuter, inte dagar.
        </p>

        {/* CTA Button */}
        <div className="animate-fade-in">
          <Button className="btn-hero text-lg" asChild>
            <a href="/app">Skapa årsredovisning nu</a>
          </Button>
        </div>

        {/* Trust indicators */}
        <div className="mt-12 text-sm text-summare-gray">
          <p>Betrodd av över 10,000+ egenföretagare i Sverige</p>
        </div>
      </div>
    </section>
  );
};

export default HeroSection;
