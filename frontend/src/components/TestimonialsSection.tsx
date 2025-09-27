import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Star } from "lucide-react";
import {
  Carousel,
  CarouselContent,
  CarouselItem,
} from "@/components/ui/carousel";
// @ts-ignore
import Autoplay from "embla-carousel-autoplay";

const testimonials = [
  {
    name: "Erik Andersson",
    username: "@erikbuilds",
    text: "Summare gjorde min årsredovisning till en barnlek. Det som brukade ta mig veckor tog bara några timmar. Fantastiskt verktyg för oss egenföretagare!",
    rating: 5
  },
  {
    name: "Maria Lindström", 
    username: "@maria_design",
    text: "Efter att ha använt Summare i två år kan jag säga att det här är det bästa verktyget för digitala årsredovisningar. Support är också fantastisk.",
    rating: 5
  },
  {
    name: "Johan Svensson",
    username: "@johan_tech", 
    text: "Enkelt att använda, professionella resultat och sparar massor av tid. Kan varmt rekommendera Summare till alla egenföretagare!",
    rating: 5
  },
  {
    name: "Anna Karlsson",
    username: "@anna_konsult",
    text: "Som ny egenföretagare var jag nervös för min första årsredovisning. Summare guidade mig genom allt steg för steg. Perfekt!",
    rating: 5
  }
];

const TestimonialsSection = () => {
  return (
    <section className="section-padding bg-summare-gray-light">
      <div className="max-w-7xl mx-auto">
        {/* Section Header */}
        <div className="text-center mb-16">
          <h2 className="text-3xl md:text-4xl font-bold text-summare-navy mb-4">
            Vad våra kunder säger
          </h2>
          <p className="text-subtitle max-w-2xl mx-auto">
            Tusentals nöjda egenföretagare har redan<br />
            förenklat sin administration med Summare
          </p>
          
          {/* Star Rating Display */}
          <div className="flex justify-center items-center mt-8 mb-12">
            <div className="flex space-x-1 mr-4">
              {[...Array(5)].map((_, i) => (
                <Star 
                  key={i} 
                  className="w-8 h-8 fill-summare-magenta text-summare-magenta" 
                />
              ))}
            </div>
            <div className="text-left">
              <p className="text-lg font-semibold text-summare-navy">4.9 av 5 stjärnor</p>
              <p className="text-sm text-summare-gray">Baserat på 1,247 recensioner</p>
            </div>
          </div>
        </div>

        {/* Testimonials Carousel */}
        <Carousel
          opts={{
            align: "start",
            loop: true,
          }}
          plugins={[
            Autoplay({
              delay: 3000,
            }),
          ]}
          className="w-full"
        >
          <CarouselContent className="-ml-2 md:-ml-4">
            {testimonials.map((testimonial, index) => (
              <CarouselItem key={index} className="pl-2 md:pl-4 md:basis-1/2 lg:basis-1/3">
                <Card className="p-6 bg-white border-0 shadow-lg hover:shadow-xl transition-all duration-300 transform hover:-translate-y-1 h-full">
                  {/* Stars */}
                  <div className="flex space-x-1 mb-4">
                    {[...Array(testimonial.rating)].map((_, i) => (
                      <Star 
                        key={i} 
                        className="w-4 h-4 fill-summare-magenta text-summare-magenta" 
                      />
                    ))}
                  </div>
                  
                  {/* Review Text */}
                  <p className="text-summare-gray mb-6 text-sm leading-relaxed">
                    {testimonial.text}
                  </p>
                  
                  {/* Author */}
                  <div>
                    <p className="font-semibold text-summare-navy">
                      {testimonial.name}
                    </p>
                    <p className="text-sm text-summare-magenta">
                      {testimonial.username}
                    </p>
                  </div>
                </Card>
              </CarouselItem>
            ))}
          </CarouselContent>
        </Carousel>

        {/* Bottom CTA */}
        <div className="text-center mt-16">
          <Button className="btn-hero" asChild>
            <a href="/app">Bli nästa nöjda kund</a>
          </Button>
        </div>
      </div>
    </section>
  );
};

export default TestimonialsSection;
