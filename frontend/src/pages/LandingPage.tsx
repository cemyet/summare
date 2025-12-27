import Header from "@/components/Header";
import HeroSection from "@/components/HeroSection";
import FeaturesSection from "@/components/FeaturesSection";
// TEMPORARILY PAUSED - uncomment to re-enable
// import TestimonialsSection from "@/components/TestimonialsSection";

const LandingPage = () => {
  return (
    <div className="min-h-screen">
      <Header />
      <HeroSection />
      <FeaturesSection />
      {/* TEMPORARILY PAUSED - uncomment to re-enable */}
      {/* <TestimonialsSection /> */}
    </div>
  );
};

export default LandingPage;
