// src/components/FluentMessage.tsx
import { useEffect, useState } from "react";

interface FluentMessageProps {
  text: string;
  onDone?: () => void;
}

export const FluentMessage: React.FC<FluentMessageProps> = ({ text, onDone }) => {
  const [visibleText, setVisibleText] = useState("");

  useEffect(() => {
    let i = 0;
    const words = text.split(/(\s+)/); // keep spaces intact

    const interval = setInterval(() => {
      i++;
      setVisibleText(words.slice(0, i).join(""));
      if (i >= words.length) {
        clearInterval(interval);
        if (onDone) onDone();
      }
    }, 40); // speed: 30–50ms feels smooth

    return () => clearInterval(interval);
  }, [text, onDone]);

  return <span>{visibleText}</span>;
};
