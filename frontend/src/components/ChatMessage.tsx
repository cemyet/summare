import { cn } from "@/lib/utils";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";

// 🔧 TOGGLE: Switch between emoji and customer agent image
const USE_CUSTOMER_AGENT_IMAGE = false; // Set to true to use customer_agent_small.png

interface ChatMessageProps {
  message: string;
  isBot?: boolean;
  emoji?: string;
  className?: string;
}

export function ChatMessage({ message, isBot = false, emoji, className }: ChatMessageProps) {
  // Process message to add tooltips for info icons
  const processMessageWithTooltips = (text: string) => {
    // Replace info icons with hover tooltips
    let processedText = text.replace(/(\[i1\])/g, '<span class="info-hover" data-gif="ink2_fortryckt_outnyttjat_underskott.gif">ⓘ</span>');
    processedText = processedText.replace(/(\[i2\])/g, '<span class="info-hover" data-gif="ink2_inlamnad_outnyttjat_underskott.gif">ⓘ</span>');
    
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
        return <span key={index}>{part}</span>;
      }
    });
  };

  if (isBot) {
    // Bot messages without bubbles, clean like Lovable
    return (
      <div className={cn("flex w-full mb-6 animate-fade-in", className)}>
        <div className="flex items-start space-x-3 max-w-[90%]">
          {emoji && (
            USE_CUSTOMER_AGENT_IMAGE ? (
              <img 
                src="/customer_agent_small.png" 
                alt="Customer Service Agent"
                className="w-4 h-4 mt-1 flex-shrink-0 rounded-full object-cover"
                style={{ width: '60%', height: 'auto' }}
              />
            ) : (
              <span className="text-base mt-1 flex-shrink-0">{emoji}</span>
            )
          )}
          <div className="text-sm text-foreground leading-relaxed font-light font-inter chat-message">
            {processMessageWithTooltips(message)}
          </div>
        </div>
      </div>
    );
  }

  // User messages with soft beige bubbles
  return (
    <div className={cn("flex w-full mb-6 justify-end animate-fade-in", className)}>
      <div className="max-w-[75%] px-3 py-2 bg-muted text-foreground rounded-lg text-sm leading-relaxed font-light font-inter chat-message">
        {message}
      </div>
    </div>
  );
}