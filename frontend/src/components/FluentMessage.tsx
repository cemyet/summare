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
    // Split by info icons, VISA button, arrow button, and edit button to create JSX elements
    const parts = text.split(/(\[i1\]|\[i2\]|\[VISA\]|\[PILEN\]|\[EDIT\])/);
    
    return parts.map((part, index) => {
      if (part === '[EDIT]') {
        // Render inline edit/pencil button - matches the manual edit button next to headings
        return (
          <span 
            key={index}
            className="inline-flex items-center justify-center w-5 h-5 mx-0.5 rounded-full bg-gray-200"
            style={{ verticalAlign: 'middle' }}
          >
            <svg className="w-3 h-3" fill="none" stroke="#4b5563" strokeWidth="2" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" 
                    d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/>
            </svg>
          </span>
        );
      } else if (part === '[PILEN]') {
        // Render inline blue arrow - matches exactly the popup arrow style
        return (
          <svg 
            key={index}
            className="w-4 h-4 inline-block mx-0.5" 
            fill="none" 
            stroke="#3b82f6" 
            strokeWidth="2" 
            viewBox="0 0 24 24"
            style={{ verticalAlign: 'middle' }}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
          </svg>
        );
      } else if (part === '[VISA]') {
        // Render inline VISA button styling (non-interactive, just visual)
        return (
          <span 
            key={index} 
            className="inline-flex items-center justify-center px-2 py-0.5 mx-0.5 text-xs font-medium border border-gray-300 rounded-full bg-white text-gray-700"
            style={{ fontSize: '0.7rem', lineHeight: '1.2' }}
          >
            VISA
          </span>
        );
      } else if (part === '[i1]') {
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
          // Process <b>, <btn>, <brown>, <beige> tags for styled text
          const parts = text.split(/(<b>.*?<\/b>|<btn>.*?<\/btn>|<brown>.*?<\/brown>|<beige>.*?<\/beige>)/);
          return parts.map((textPart, textIndex) => {
            if (textPart.startsWith('<b>') && textPart.endsWith('</b>')) {
              const boldText = textPart.slice(3, -4); // Remove <b> and </b>
              return <span key={textIndex} className="font-semibold">{boldText}</span>;
            }
            if (textPart.startsWith('<btn>') && textPart.endsWith('</btn>')) {
              const btnText = textPart.slice(5, -6); // Remove <btn> and </btn>
              return <span key={textIndex} className="font-semibold" style={{ color: '#3662E3' }}>{btnText}</span>;
            }
            if (textPart.startsWith('<brown>') && textPart.endsWith('</brown>')) {
              const brownText = textPart.slice(7, -8); // Remove <brown> and </brown>
              return <span key={textIndex} className="font-semibold" style={{ color: '#957451' }}>{brownText}</span>;
            }
            if (textPart.startsWith('<beige>') && textPart.endsWith('</beige>')) {
              const beigeText = textPart.slice(7, -8); // Remove <beige> and </beige>
              return <span key={textIndex} className="font-semibold" style={{ color: '#D0C8BF' }}>{beigeText}</span>;
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
