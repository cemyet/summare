// src/components/FluentMessage.tsx - Clean stable version - Updated for smooth chat experience
import { useEffect, useState } from "react";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";

interface FluentMessageProps {
  text: string;
  onDone?: () => void;
}

export const FluentMessage: React.FC<FluentMessageProps> = ({ text, onDone }) => {
  const [visibleText, setVisibleText] = useState("");
  const [isComplete, setIsComplete] = useState(false);

  // Convert text to characters for character-by-character animation (Unicode-safe)
  const characters = Array.from(text);

  // Process message to add tooltips for info icons and format keywords
  const processMessageWithTooltips = (text: string) => {
    // Split by info icons to create JSX elements
    const parts = text.split(/(\[i1\]|\[i2\])/);
    
    return parts.map((part, index) => {
      if (part === '[i1]') {
        return (
          <TooltipProvider key={index}>
            <Tooltip>
              <TooltipTrigger asChild>
                <span className="inline-flex items-center justify-center w-4 h-4 bg-blue-500 hover:bg-blue-600 text-white text-xs rounded-full cursor-pointer mx-1">i</span>
              </TooltipTrigger>
              <TooltipContent side="top" className="p-0 border-0 bg-transparent shadow-lg">
                <img 
                  src="/ink2_fortryckt_outnyttjat_underskott.gif" 
                  alt="Förtryckt underskott guide"
                  className="max-w-lg rounded-lg"
                />
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        );
      } else if (part === '[i2]') {
        return (
          <TooltipProvider key={index}>
            <Tooltip>
              <TooltipTrigger asChild>
                <span className="inline-flex items-center justify-center w-4 h-4 bg-blue-500 hover:bg-blue-600 text-white text-xs rounded-full cursor-pointer mx-1">i</span>
              </TooltipTrigger>
              <TooltipContent side="top" className="p-0 border-0 bg-transparent shadow-lg">
                <img 
                  src="/ink2_inlamnad_outnyttjat_underskott.gif" 
                  alt="Inlämnad underskott guide"
                  className="max-w-lg rounded-lg"
                />
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        );
      } else {
        // Process formatting tags from SQL messages
        const formatText = (text: string) => {
          // Process <b>text</b> tags for semibold formatting
          const boldParts = text.split(/(<b>.*?<\/b>)/);
          return boldParts.map((textPart, textIndex) => {
            if (textPart.startsWith('<b>') && textPart.endsWith('</b>')) {
              const boldText = textPart.slice(3, -4); // Remove <b> and </b>
              return <span key={textIndex} className="font-semibold">{boldText}</span>;
            }
            return <span key={textIndex}>{textPart}</span>;
          });
        };
        
        return <span key={index}>{formatText(part)}</span>;
      }
    });
  };

  useEffect(() => {
    let timeoutId: NodeJS.Timeout;
    let currentIndex = 0;

    const typeNextCharacter = () => {
      if (currentIndex >= characters.length) {
        setIsComplete(true);
        if (onDone) onDone();
        return;
      }

      // Get current character before incrementing
      const currentChar = characters[currentIndex];
      
      // Add character to visible text (preserves special characters like åäö)
      setVisibleText(prev => prev + currentChar);
      currentIndex++;

      // 6x speed: Base delay of 8ms (was 12ms, originally 50ms for words)
      let delay = 8;
      
      // Pause after punctuation for natural rhythm
      if (currentChar === '.' || currentChar === '!' || currentChar === '?') {
        delay = 50; // Pause after sentences
      } else if (currentChar === ',' || currentChar === ';') {
        delay = 25; // Pause after clauses
      } else if (currentChar === '\n') {
        delay = 15; // Pause after line breaks
      }
      
      timeoutId = setTimeout(typeNextCharacter, delay);
    };

    // Start typing with initial delay to ensure image loads first
    timeoutId = setTimeout(typeNextCharacter, 500);

    return () => {
      if (timeoutId) clearTimeout(timeoutId);
    };
  }, [text, onDone, characters.length]);

  const full = processMessageWithTooltips(text);
  const partial = processMessageWithTooltips(visibleText);

  return (
    <span style={{ display: "inline-block", whiteSpace: "pre-wrap" }}>
      {isComplete ? full : partial}
    </span>
  );
};
