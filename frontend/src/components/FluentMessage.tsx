// src/components/FluentMessage.tsx
import { useEffect, useState } from "react";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";

interface FluentMessageProps {
  text: string;
  onDone?: () => void;
}

export const FluentMessage: React.FC<FluentMessageProps> = ({ text, onDone }) => {
  const [visibleWords, setVisibleWords] = useState(0);
  const [isComplete, setIsComplete] = useState(false);

  // Split text into words while preserving formatting
  const words = text.split(/(\s+)/); // keep spaces intact

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

    const typeNextWord = (wordIndex: number) => {
      if (wordIndex >= words.length) {
        setIsComplete(true);
        if (onDone) onDone();
        return;
      }

      setVisibleWords(wordIndex + 1);

      // Variable speed for more natural rhythm (faster and more fluent)
      const currentWord = words[wordIndex];
      let nextDelay = 50; // much faster base speed for words
      
      // Pause after punctuation for natural rhythm (shorter pauses)
      if (currentWord && (currentWord.includes('.') || currentWord.includes('!') || currentWord.includes('?'))) {
        nextDelay = 250; // shorter pause after sentences
      } else if (currentWord && (currentWord.includes(',') || currentWord.includes(';'))) {
        nextDelay = 120; // shorter pause after clauses
      } else if (currentWord && currentWord.trim() === '') {
        nextDelay = 20; // much faster through spaces
      }
      
      // Schedule next word
      timeoutId = setTimeout(() => typeNextWord(wordIndex + 1), nextDelay);
    };

    // Start typing
    typeNextWord(0);

    return () => {
      if (timeoutId) clearTimeout(timeoutId);
    };
  }, [text, onDone, words.length]);

  // Render invisible full text for layout, then visible portion with opacity
  return (
    <>
      {/* Invisible full text to establish proper layout */}
      <span className="invisible absolute">{processMessageWithTooltips(text)}</span>
      
      {/* Visible progressive text */}
      <span className={isComplete ? "" : ""}>{processMessageWithTooltips(words.slice(0, visibleWords).join(''))}</span>
    </>
  );
};
