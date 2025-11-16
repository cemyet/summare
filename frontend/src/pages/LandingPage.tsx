import Header from "@/components/Header";
import HeroSection from "@/components/HeroSection";
// TEMPORARILY PAUSED - uncomment to re-enable
// import TestimonialsSection from "@/components/TestimonialsSection";

const LandingPage = () => {
  return (
    <div className="min-h-screen">
      <Header />
      <HeroSection />
      {/* TEMPORARILY PAUSED - uncomment to re-enable */}
      {/* <TestimonialsSection /> */}
    </div>
  );
};

export default LandingPage;
