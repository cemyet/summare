interface FeatureCard {
  image: string;
  heading: string;
  description: string;
  imageOnRight?: boolean;
}

const features: FeatureCard[] = [
  {
    image: "/card1 copy.png",
    heading: "Djupsökning med AI förenklar för användaren",
    description: "Vårt smarta AI-verktyg gör en djupsökning i SIE-filerna hela vägen ner på verifikationsnivå och kan utifrån det bygga en detaljerad resultat- och balansräkning, samt bygga helt kompletta noter. Vår princip är enkel — vi frågar inte om det vi kan räkna ut eller ta reda på själva. Allt för att förenkla för dig som användare!",
    imageOnRight: false,
  },
  // Add more features here as needed
];

const FeatureCardComponent = ({ image, heading, description, imageOnRight = false }: FeatureCard) => {
  return (
    <div className={`grid grid-cols-1 lg:grid-cols-2 items-center gap-6 lg:gap-10 py-12 lg:py-20`}>
      {/* Image Section */}
      <div className={`${imageOnRight ? 'lg:order-2' : 'lg:order-1'}`}>
        <img
          src={image}
          alt={heading}
          className="w-full h-auto object-contain"
        />
      </div>

      {/* Text Section */}
      <div className={`space-y-4 px-4 lg:px-12 ${imageOnRight ? 'lg:order-1' : 'lg:order-2'}`}>
        <h3 
          className="text-xl md:text-2xl font-medium text-gray-900 leading-snug"
          style={{ fontFamily: "'Roboto', sans-serif" }}
        >
          {heading}
        </h3>
        <p 
          className="text-sm md:text-base text-gray-600 leading-relaxed"
          style={{ fontFamily: "'Roboto', sans-serif", fontWeight: 400 }}
        >
          {description}
        </p>
      </div>
    </div>
  );
};

const FeaturesSection = () => {
  return (
    <section className="bg-white">
      <div className="max-w-[1600px] mx-auto px-4 md:px-8 lg:px-12">
        {features.map((feature, index) => (
          <FeatureCardComponent
            key={index}
            {...feature}
            imageOnRight={index % 2 === 1}
          />
        ))}
      </div>
    </section>
  );
};

export default FeaturesSection;

