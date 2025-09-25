// src/components/FluentMessage.tsx
import { useEffect, useState } from "react";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";

interface FluentMessageProps {
  text: string;
  onDone?: () => void;
}

export const FluentMessage: React.FC<FluentMessageProps> = ({ text, onDone }) => {
  const [visibleText, setVisibleText] = useState("");

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
    const chars = text.split(''); // character-by-character for ultra-smooth flow
    let timeoutId: NodeJS.Timeout;

    const typeNextChar = (index: number) => {
      if (index >= chars.length) {
        if (onDone) onDone();
        return;
      }

      setVisibleText(chars.slice(0, index + 1).join(''));

      // Variable speed for more natural rhythm
      const currentChar = chars[index];
      let nextDelay = 20; // base speed (ultra-smooth)
      
      // Pause after punctuation for natural rhythm
      if (currentChar === '.' || currentChar === '!' || currentChar === '?') {
        nextDelay = 300; // longer pause after sentences
      } else if (currentChar === ',' || currentChar === ';') {
        nextDelay = 150; // medium pause after clauses
      } else if (currentChar === ' ') {
        nextDelay = 10; // faster through spaces
      } else if (currentChar === '\n') {
        nextDelay = 200; // pause at line breaks
      }
      
      // Schedule next character with variable timing
      timeoutId = setTimeout(() => typeNextChar(index + 1), nextDelay);
    };

    // Start typing
    typeNextChar(0);

    return () => {
      if (timeoutId) clearTimeout(timeoutId);
    };
  }, [text, onDone]);

  // Process the visible text with tooltips and formatting
  return <span>{processMessageWithTooltips(visibleText)}</span>;
};
