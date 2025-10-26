// Force deployment trigger - v4
import React, { useState, useEffect, useRef } from 'react';
import { apiService } from '@/services/api';
import { ChatMessage } from './ChatMessage';
import { OptionButton } from './OptionButton';
import { FileUpload } from './FileUpload';
import { USE_EMBED } from '@/utils/flags';
// Force Vercel deployment - trigger

interface ChatStep {
  step_number: number;
  block?: string;
  question_text: string;
  question_icon?: string;
  question_type: string;
  input_type?: string;
  input_placeholder?: string;
  show_conditions?: any;
}

interface ChatOption {
  option_order: number;
  option_text: string | null;
  option_value: string;
  next_step?: number;
  action_type: string;
  action_data?: any;
}

interface ChatMessage {
  id: string;
  text: string;
  isBot: boolean;
  icon?: string;
  timestamp: Date;
}

interface ChatFlowProps {
  companyData: any;
  onDataUpdate: (updates: Partial<any>) => void;
}

interface ChatFlowResponse {
  success: boolean;
  step_number: number;
  block?: string;
  question_text: string;
  question_icon?: string;
  question_type: string;
  input_type?: string;
  input_placeholder?: string;
  show_conditions?: any;
  options: ChatOption[];
}

  const DatabaseDrivenChat: React.FC<ChatFlowProps> = ({ companyData, onDataUpdate }) => {
    // Helper: accepted SLP difference (positive) from ink2Data/companyData - Vercel revert deploy
    const getAcceptedSLP = (ink2Data: any[], cd: any) => {
      const by = (n: string) => ink2Data?.find((x: any) => x.variable_name === n);
      const manualPos = Number(by('justering_sarskild_loneskatt')?.amount) || Number(cd?.justeringSarskildLoneskatt) || 0;
      const signedInInk = Number(by('INK_sarskild_loneskatt')?.amount) || 0;
      
      // If we have manual adjustment, use it (it's already the difference)
      if (manualPos !== 0) {
        return Math.abs(manualPos);
      }
      
      // If we have INK value, it should be the difference amount (calculated - booked)
      // The INK value is the adjustment needed, not the total calculated amount
      return Math.abs(signedInInk);
    };
    // State to store the most recent calculated values
    const [globalInk2Data, setGlobalInk2Data] = useState<any[]>([]);

    // Handle tax update logic when approving calculated tax in chat flow
    const handleTaxUpdateForApproval = async () => {
      try {
        // Get current INK2 data
        const currentInk2Data = companyData.ink2Data || [];
        
        // Find INK_beraknad_skatt and INK_bokford_skatt values
        const beraknadSkattItem = currentInk2Data.find((item: any) => item.variable_name === 'INK_beraknad_skatt');
        const bokfordSkattItem = currentInk2Data.find((item: any) => item.variable_name === 'INK_bokford_skatt');
        
        if (!beraknadSkattItem || !bokfordSkattItem) {
          return;
        }

        const inkBeraknadSkatt = beraknadSkattItem.amount || 0;
        const inkBokfordSkatt = bokfordSkattItem.amount || 0;
        
        // Only proceed if there's a difference
        if (inkBeraknadSkatt === inkBokfordSkatt) {
          return;
        }

        const taxDifference = inkBeraknadSkatt - inkBokfordSkatt;

        // Call API to update RR/BR data
        
        // Accepted SLP (positive) via helper
        const inkSarskildLoneskatt = getAcceptedSLP(currentInk2Data, companyData);

        const requestData = {
          inkBeraknadSkatt,
          inkBokfordSkatt,
          taxDifference,
          rr_data: companyData.seFileData?.rr_data || [],
          br_data: companyData.seFileData?.br_data || [],
          organizationNumber: companyData.organizationNumber,
          fiscalYear: companyData.fiscalYear,
          // NEW: SLP amount
          inkSarskildLoneskatt,
        };
        
        const response = await fetch(`${import.meta.env.VITE_API_URL || 'https://api.summare.se'}/api/update-tax-in-financial-data`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(requestData),
        });

        if (!response.ok) {
          const errorText = await response.text();
          console.error('❌ API error response from chat:', errorText);
          
          if (response.status === 404) {
            // Don't throw error for 404, just log and continue
            return;
          }
          
          throw new Error(`HTTP error! status: ${response.status}, body: ${errorText}`);
        }

        const result = await response.json();
        
        if (result.success) {
          
          // Set default radio button values if not already set
          const currentAccepted = companyData.acceptedInk2Manuals || {};
          const needsDefaults = !currentAccepted['INK4.23a'] && !currentAccepted['INK4.23b'] && 
                                !currentAccepted['INK4.24a'] && !currentAccepted['INK4.24b'];
          
          const updatedAccepted = needsDefaults ? {
            ...currentAccepted,
            'INK4.23a': 0,
            'INK4.23b': 1,  // Default to "Nej"
            'INK4.24a': 0,
            'INK4.24b': 1   // Default to "Nej"
          } : currentAccepted;
          
          // Update company data with new RR/BR data and radio button defaults
          onDataUpdate({
            seFileData: {
              ...companyData.seFileData,
              rr_data: result.rr_data,
              br_data: result.br_data,
            },
            acceptedInk2Manuals: updatedAccepted
          });
        } else {
          console.error('❌ Failed to update RR/BR data from chat:', result.error);
        }
        
      } catch (error) {
        console.error('❌ Error in handleTaxUpdateForApproval:', error);
      }
    };
    const [globalInkBeraknadSkatt, setGlobalInkBeraknadSkatt] = useState<number>(0);
  const [currentStep, setCurrentStep] = useState<number>(101); // Start with introduction
  const [currentQuestion, setCurrentQuestion] = useState<ChatStep | null>(null);
  const [currentOptions, setCurrentOptions] = useState<ChatOption[]>([]);
  const [lastLoadedOptions, setLastLoadedOptions] = useState<ChatOption[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const messageCallbacks = useRef<Record<string, () => void>>({});
  const previousStepRef = useRef<number>(101); // Track previous step for conditional autoscroll
  const [showInput, setShowInput] = useState(false);
  const [inputValue, setInputValue] = useState('');
  const [inputType, setInputType] = useState('text');
  const [inputPlaceholder, setInputPlaceholder] = useState('');
  const [showFileUpload, setShowFileUpload] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isWaitingForUser, setIsWaitingForUser] = useState(false);
  const showSpinner = false; // 🚫 Disable blue waiting circle
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const chatContainerRef = useRef<HTMLDivElement>(null);
  const msgContainersRef = useRef<Record<string, HTMLDivElement | null>>({});

  // --- Keep-while-typing autoscroll state ---
  const typingMsgIdRef = useRef<string | null>(null);
  const typingObserverRef = useRef<ResizeObserver | null>(null);
  const lastNudgeTsRef = useRef<number>(0);

  // tuneables
  const BOTTOM_SAFETY_PX = 32;    // how much space under the bubble to keep
  const NEAR_BOTTOM_PX   = 160;   // only auto-nudge if we are this close to the bottom
  const THROTTLE_MS      = 80;    // nudge at most every 80ms

  // --- While-typing autoscroll (container-level, works for any typing impl) ---
  const NEAR_BOTTOM_PX_DOM = 160;   // consider auto-follow if this close to bottom
  const BOTTOM_SAFETY_PX_DOM = 24;  // keep at least this many pixels visible under the bubble

  // Compute message's offsetTop within the scroll container
  const getOffsetTopWithin = (el: HTMLElement, container: HTMLElement) => {
    let y = 0; let n: HTMLElement | null = el;
    while (n && n !== container) { y += n.offsetTop; n = n.offsetParent as HTMLElement | null; }
    return y;
  };

  // Are we already near the bottom of the container?
  const isNearBottom = (container: HTMLElement) => {
    const remaining = container.scrollHeight - (container.scrollTop + container.clientHeight);
    return remaining <= NEAR_BOTTOM_PX;
  };

  // Make sure given element's bottom is visible with padding, but don't over-scroll
  const nudgeToReveal = (el: HTMLElement) => {
    const container = chatContainerRef.current;
    if (!container) return;

    // throttle
    const now = performance.now();
    if (now - lastNudgeTsRef.current < THROTTLE_MS) return;
    lastNudgeTsRef.current = now;

    // only nudge when user is already reading near the bottom
    if (!isNearBottom(container)) return;

    const elTop = getOffsetTopWithin(el, container);
    const elBottom = elTop + el.offsetHeight;
    const desiredScrollTop = Math.max(0, elBottom - container.clientHeight + BOTTOM_SAFETY_PX);

    if (container.scrollTop < desiredScrollTop) {
      container.scrollTo({ top: desiredScrollTop, behavior: 'auto' });
    }
  };

  // Observe a message node while it grows (typing)
  const observeTyping = (messageId: string | null) => {
    // cleanup any previous observer
    typingObserverRef.current?.disconnect();
    typingObserverRef.current = null;
    typingMsgIdRef.current = messageId;

    if (!messageId) return;

    // attach when the DOM node is available
    const node = msgContainersRef.current[messageId];
    const container = chatContainerRef.current;
    if (!node || !container) return;

    const ro = new ResizeObserver(() => {
      // on every growth, nudge to keep visible
      nudgeToReveal(node);
    });
    ro.observe(node);
    typingObserverRef.current = ro;

    // do an initial nudge right away (useful if first line is already below bottom)
    nudgeToReveal(node);
  };


  // Auto-scroll to bottom
  const scrollToBottom = () => {
    setTimeout(() => {
      if (messagesEndRef.current) {
        messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
      }
    }, 100);
  };

  // Substitute variables in text
  const substituteVariables = (text: string, context: Record<string, any> = {}): string => {
    let result = text;
    
    // Create context from company data, but prioritize context values over companyData
    const fullContext = {
      ...companyData,
      ...context,  // Context values should override companyData values
      unusedTaxLossAmount: context.unusedTaxLossAmount || companyData.unusedTaxLossAmount || 0,
      inkBeraknadSkatt: context.inkBeraknadSkatt || companyData.inkBeraknadSkatt || 0,
      inkBokfordSkatt: context.inkBokfordSkatt || companyData.inkBokfordSkatt || 0,
      SkattAretsResultat: context.SkattAretsResultat || companyData.skattAretsResultat || 0,
      pension_premier: context.pension_premier || companyData.pensionPremier || 0,
      sarskild_loneskatt_pension: context.sarskild_loneskatt_pension || companyData.sarskildLoneskattPension || 0,
      sarskild_loneskatt_pension_calculated: context.sarskild_loneskatt_pension_calculated || companyData.sarskildLoneskattPensionCalculated || 0,
      arets_utdelning: context.arets_utdelning || companyData.arets_utdelning || 0,
      arets_balanseras_nyrakning: context.arets_balanseras_nyrakning || companyData.arets_balanseras_nyrakning || 0
    };

    // Replace variables
    for (const [key, value] of Object.entries(fullContext)) {
      const placeholder = `{${key}}`;
      if (result.includes(placeholder)) {
        if (typeof value === 'number') {
          const formatted = new Intl.NumberFormat('sv-SE', { 
            minimumFractionDigits: 0, 
            maximumFractionDigits: 0 
          }).format(value);
          result = result.replace(new RegExp(`\\{${key}\\}`, 'g'), formatted);
        } else {
          result = result.replace(new RegExp(`\\{${key}\\}`, 'g'), String(value || ''));
        }
      }
    }

    return result;
  };

  // Add message to chat
  const addMessage = (text: string, isBot: boolean = true, icon?: string, onDone?: () => void) => {
    // Prevent adding empty messages
    if (!text || text.trim() === '') {
      return;
    }
    
    const message: ChatMessage = {
      id: Date.now().toString(),
      text: substituteVariables(text),
      isBot,
      icon,
      timestamp: new Date()
    };
    
    setMessages(prev => [...prev, message]);
    
    // 👇 NEW: if this is a bot bubble that will type, observe it while it grows
    if (isBot) observeTyping(message.id);
    
    // Only scroll immediately for user messages (they don't animate)
    if (!isBot) {
      scrollToBottom();
    }

    if (onDone) {
      messageCallbacks.current[message.id] = () => {
        // 👇 NEW: stop observing when typing is done
        observeTyping(null);
        // your existing behavior:
        scrollToBottom();
        onDone();
      };
    } else if (isBot) {
      messageCallbacks.current[message.id] = () => {
        // 👇 NEW: stop observing when typing is done
        observeTyping(null);
        // your existing behavior:
        scrollToBottom();
      };
    }
  };

  // Load a chat step
  const loadChatStep = async (stepNumber: number, updatedInk2Data?: any[], tempCompanyData?: any) => {
    try {
      setIsLoading(true);
      setIsWaitingForUser(false);
      
      // Clear old options immediately when starting new step
      setCurrentOptions([]);
      
      // Use updated ink2Data if provided, otherwise use global data, otherwise use companyData.ink2Data
      const ink2DataToUse = updatedInk2Data || globalInk2Data || companyData.ink2Data;
      if (ink2DataToUse && ink2DataToUse.length > 0) {
        const inkBeraknadSkattItem = ink2DataToUse.find((item: any) => 
          item.variable_name === 'INK_beraknad_skatt'
        );
      }
      const response = await apiService.getChatFlowStep(stepNumber) as ChatFlowResponse;
      
      // Debug logging for step 506
      if (stepNumber === 506) {
      }
      
      if (response.success) {
        previousStepRef.current = currentStep; // Store previous step before updating
        setCurrentStep(stepNumber);
        onDataUpdate({ currentStep: stepNumber }); // 👉 expose step to the preview/right pane
        
        // Handle no_option automatically if it exists
        const noOption = response.options.find(opt => opt.option_order === 0);
        if (noOption) {
          // For message-type steps with no_option, show the message first, then execute the no_option
          if (response.question_type === 'message') {
            // Get the most recent inkBeraknadSkatt value from global data first, then INK2 data
            let mostRecentInkBeraknadSkatt = globalInkBeraknadSkatt || companyData.inkBeraknadSkatt;
            if (ink2DataToUse && ink2DataToUse.length > 0) {
              const inkBeraknadSkattItem = ink2DataToUse.find((item: any) => 
                item.variable_name === 'INK_beraknad_skatt'
              );
              if (inkBeraknadSkattItem && inkBeraknadSkattItem.amount !== undefined) {
                mostRecentInkBeraknadSkatt = inkBeraknadSkattItem.amount;
              }
            }
            
            // Substitute variables in question text (use temp data if available)
            const dataToUseForMessage = tempCompanyData || companyData;
            const questionText = substituteVariables(response.question_text, {
              SumAretsResultat: dataToUseForMessage.sumAretsResultat ? new Intl.NumberFormat('sv-SE').format(dataToUseForMessage.sumAretsResultat) : '0',
              SkattAretsResultat: dataToUseForMessage.skattAretsResultat ? new Intl.NumberFormat('sv-SE').format(dataToUseForMessage.skattAretsResultat) : '0',
              pension_premier: dataToUseForMessage.pensionPremier ? new Intl.NumberFormat('sv-SE').format(dataToUseForMessage.pensionPremier) : '0',
              sarskild_loneskatt_pension_calculated: dataToUseForMessage.sarskildLoneskattPensionCalculated ? new Intl.NumberFormat('sv-SE').format(dataToUseForMessage.sarskildLoneskattPensionCalculated) : '0',
              sarskild_loneskatt_pension: dataToUseForMessage.sarskildLoneskattPension ? new Intl.NumberFormat('sv-SE').format(dataToUseForMessage.sarskildLoneskattPension) : '0',
              inkBeraknadSkatt: mostRecentInkBeraknadSkatt ? new Intl.NumberFormat('sv-SE').format(mostRecentInkBeraknadSkatt) : '0',
              inkBokfordSkatt: dataToUseForMessage.inkBokfordSkatt ? new Intl.NumberFormat('sv-SE').format(dataToUseForMessage.inkBokfordSkatt) : '0',
              unusedTaxLossAmount: dataToUseForMessage.unusedTaxLossAmount ? new Intl.NumberFormat('sv-SE').format(dataToUseForMessage.unusedTaxLossAmount) : '0',
              arets_utdelning: dataToUseForMessage.arets_utdelning ? new Intl.NumberFormat('sv-SE', { minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(dataToUseForMessage.arets_utdelning) : '0',
              arets_balanseras_nyrakning: dataToUseForMessage.arets_balanseras_nyrakning ? new Intl.NumberFormat('sv-SE', { minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(dataToUseForMessage.arets_balanseras_nyrakning) : '0'
            });
            
            // Special handling for step 506: watch for actual Stripe payment content to be rendered
            if (stepNumber === 506) {
              const watchForPaymentContent = () => {
                const checkForContent = () => {
                  const paymentAnchor = document.getElementById("payment-section-anchor");
                  // Check if the anchor has actual payment content (not just empty)
                  const hasContent = paymentAnchor && 
                    paymentAnchor.children.length > 0 && 
                    paymentAnchor.offsetHeight > 100; // Stripe form should have substantial height
                  
                  if (hasContent) {
                    // Stripe payment content is now rendered, scroll to it immediately
                    setTimeout(() => {
                      const scrollContainer = document.querySelector('.overflow-auto');
                      if (paymentAnchor && scrollContainer) {
                        const containerRect = scrollContainer.getBoundingClientRect();
                        const paymentRect = paymentAnchor.getBoundingClientRect();
                        const scrollTop = scrollContainer.scrollTop + paymentRect.top - containerRect.top - 10;
                        scrollContainer.scrollTo({
                          top: scrollTop,
                          behavior: 'smooth'
                        });
                      }
                    }, 150); // Slightly longer delay for Stripe to fully render
                    return true; // Stop checking
                  }
                  return false; // Keep checking
                };

                // Start checking immediately, then every 150ms until found
                if (!checkForContent()) {
                  const intervalId = setInterval(() => {
                    if (checkForContent()) {
                      clearInterval(intervalId);
                    }
                  }, 150);
                  
                  // Safety timeout after 5 seconds (Stripe can be slow)
                  setTimeout(() => clearInterval(intervalId), 5000);
                }
              };
              
              // Start watching for Stripe content after a short delay
              setTimeout(watchForPaymentContent, 300);
            }

            // Add the message with onDone callback to wait for animation completion
            addMessage(questionText, true, response.question_icon, async () => {
              // After message is fully revealed, continue with no_option
              await handleOptionSelect(noOption, stepNumber, updatedInk2Data);
            });
            return; // Stop here, handled in callback
          }
          
          // Special handling for step 420: auto-scroll before no_option execution
          if (stepNumber === 420) {
            setTimeout(() => {
              const noterModule = document.querySelector('[data-section="noter"]');
              const scrollContainer = document.querySelector('.overflow-auto');
              
              if (noterModule && scrollContainer) {
                const containerRect = scrollContainer.getBoundingClientRect();
                const noterRect = noterModule.getBoundingClientRect();
                const scrollTop = scrollContainer.scrollTop + noterRect.top - containerRect.top - 80; // 80pt padding to show frame edge with space above
                
                scrollContainer.scrollTo({
                  top: scrollTop,
                  behavior: 'smooth'
                });
              }
            }, 200); // Shorter delay since we're about to navigate away
          }
          
          // For non-message steps, execute no_option immediately (no animation to wait for)
          if (response.question_type !== 'message') {
            await handleOptionSelect(noOption, stepNumber, updatedInk2Data);
            return; // Don't continue with normal flow since no_option handles navigation
          }
        }
        
        // Get the most recent inkBeraknadSkatt value from global data first, then INK2 data
        let mostRecentInkBeraknadSkatt = globalInkBeraknadSkatt || companyData.inkBeraknadSkatt;
        if (ink2DataToUse && ink2DataToUse.length > 0) {
          const inkBeraknadSkattItem = ink2DataToUse.find((item: any) => 
            item.variable_name === 'INK_beraknad_skatt'
          );
          if (inkBeraknadSkattItem && inkBeraknadSkattItem.amount !== undefined) {
            mostRecentInkBeraknadSkatt = inkBeraknadSkattItem.amount;
          }
        }
        
        // Substitute variables in question text (use temp data if available)
        const dataToUse = tempCompanyData || companyData;
        const substitutionVars = {
          SumAretsResultat: dataToUse.sumAretsResultat ? new Intl.NumberFormat('sv-SE', { minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(dataToUse.sumAretsResultat) : '0',
          SkattAretsResultat: dataToUse.skattAretsResultat ? new Intl.NumberFormat('sv-SE', { minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(dataToUse.skattAretsResultat) : '0',
          pension_premier: dataToUse.pensionPremier ? new Intl.NumberFormat('sv-SE', { minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(dataToUse.pensionPremier) : '0',
          sarskild_loneskatt_pension_calculated: dataToUse.sarskildLoneskattPensionCalculated ? new Intl.NumberFormat('sv-SE', { minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(dataToUse.sarskildLoneskattPensionCalculated) : '0',
          sarskild_loneskatt_pension: dataToUse.sarskildLoneskattPension ? new Intl.NumberFormat('sv-SE', { minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(dataToUse.sarskildLoneskattPension) : '0',
          inkBeraknadSkatt: mostRecentInkBeraknadSkatt ? new Intl.NumberFormat('sv-SE', { minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(mostRecentInkBeraknadSkatt) : '0',
          inkBokfordSkatt: dataToUse.inkBokfordSkatt ? new Intl.NumberFormat('sv-SE', { minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(dataToUse.inkBokfordSkatt) : '0',
          unusedTaxLossAmount: dataToUse.unusedTaxLossAmount ? new Intl.NumberFormat('sv-SE', { minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(dataToUse.unusedTaxLossAmount) : '0',
          SumFrittEgetKapital: dataToUse.sumFrittEgetKapital ? new Intl.NumberFormat('sv-SE', { minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(dataToUse.sumFrittEgetKapital) : '0',
          arets_utdelning: dataToUse.arets_utdelning ? new Intl.NumberFormat('sv-SE', { minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(dataToUse.arets_utdelning) : '0',
          arets_balanseras_nyrakning: dataToUse.arets_balanseras_nyrakning ? new Intl.NumberFormat('sv-SE', { minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(dataToUse.arets_balanseras_nyrakning) : '0'
        };
        const questionText = substituteVariables(response.question_text, substitutionVars);
        
        // Add the question message and show options only after it completes
        addMessage(questionText, true, response.question_icon, () => {
          // After message animation completes, show the filtered and substituted options
          if (response.options && response.options.length > 0) {
            const substitutedOptions = response.options
              .filter(opt => opt.option_order > 0 && opt.option_value !== 'submit') // Exclude no_option and submit options
              .map(option => ({
                ...option,
                option_text: option.option_text ? substituteVariables(option.option_text, substitutionVars) : option.option_text
              }));
            setCurrentOptions(substitutedOptions);
          }
          setIsLoading(false);
          setIsWaitingForUser(true);
        });

        // Special handling for manual editing step (402):
        // - Ensure editing is enabled in the preview
        // - Suppress chat options to avoid accidental auto-selection
        // - Scroll the preview into view so inputs are visible
        if (stepNumber === 402) {
          onDataUpdate({ taxEditingEnabled: true, editableAmounts: true, showTaxPreview: true });
          setCurrentOptions([]);
          setTimeout(() => {
            const taxModule = document.querySelector('[data-section="tax-calculation"]');
            if (taxModule) {
              taxModule.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
          }, 200);
        } 
        // Auto-scroll to Noter section for step 420
        else if (stepNumber === 420) {
          setTimeout(() => {
            const noterModule = document.querySelector('[data-section="noter"]');
            const scrollContainer = document.querySelector('.overflow-auto');
            
            if (noterModule && scrollContainer) {
              const containerRect = scrollContainer.getBoundingClientRect();
              const noterRect = noterModule.getBoundingClientRect();
              const scrollTop = scrollContainer.scrollTop + noterRect.top - containerRect.top - 40; // 40pt padding to show heading
              
              scrollContainer.scrollTo({
                top: scrollTop,
                behavior: 'smooth'
              });
            }
          }, 500);
        }
        // Auto-scroll to Resultatdisposition section for step 501
        else if (stepNumber === 501) {
          setTimeout(() => {
            const fbModule = document.querySelector('[data-section="forvaltningsberattelse"]');
            const scrollContainer = document.querySelector('.overflow-auto');
            
            if (fbModule && scrollContainer) {
              // Scroll to bottom of förvaltningsberättelse to show Resultatdisposition
              const containerRect = scrollContainer.getBoundingClientRect();
              const fbRect = fbModule.getBoundingClientRect();
              const fbHeight = fbModule.scrollHeight || fbRect.height;
              const scrollTop = scrollContainer.scrollTop + fbRect.top - containerRect.top + fbHeight - containerRect.height + 50;
              
              scrollContainer.scrollTo({
                top: Math.max(0, scrollTop), // Ensure non-negative scroll position
                behavior: 'smooth'
              });
            }
          }, 500);
        }
        // Auto-scroll to Signering section for step 515
        else if (stepNumber === 515) {
          setTimeout(() => {
            const signeringModule = document.querySelector('[data-section="signering"]');
            const scrollContainer = document.querySelector('.overflow-auto');
            
            if (signeringModule && scrollContainer) {
              const containerRect = scrollContainer.getBoundingClientRect();
              const signeringRect = signeringModule.getBoundingClientRect();
              const scrollTop = scrollContainer.scrollTop + signeringRect.top - containerRect.top - 10;
              
              scrollContainer.scrollTo({
                top: scrollTop,
                behavior: 'smooth'
              });
            }
          }, 500);
        }
        
        if (stepNumber !== 402) {
          // Store all options (unfiltered) for submit logic
          setLastLoadedOptions(response.options);
          
          // Store filtered options for display with variable substitution
          const substitutedOptions = response.options
            .filter(opt => opt.option_order > 0 && opt.option_value !== 'submit') // Exclude no_option and submit options
            .map(option => ({
              ...option,
              option_text: option.option_text ? substituteVariables(option.option_text, substitutionVars) : option.option_text
            }));
          // setCurrentOptions(substitutedOptions); // 🚫 DISABLED - Options now set after message completes
        }
        
        // Check if we should show input instead of options
        if (response.question_type === 'input') {
          setShowInput(true);
          setInputType(response.input_type || 'text');
          setInputPlaceholder(response.input_placeholder || '');
        } else {
          // Ensure input is hidden for non-input steps
          setShowInput(false);
          setInputValue('');
        }
      }
    } catch (error) {
      console.error('❌ Error loading chat step:', error);
      addMessage('Något gick fel vid laddning av chatten. Försök ladda om sidan.', true, '❌');
    }
  };

  // Helper: safe auto-scroll to Download module
  const scrollToDownload = () => {
    try {
      const downloadModule = document.querySelector('[data-section="download"]') as HTMLElement | null;
      // Anpassa selektor nedan till din scroll-container om du har en annan klass
      const scrollContainer =
        (document.querySelector('.overflow-auto') as HTMLElement | null) ||
        (document.querySelector('[data-scroll-container="chat"]') as HTMLElement | null);

      if (!downloadModule || !scrollContainer) {
        return;
      }

      const containerRect = scrollContainer.getBoundingClientRect();
      const downloadRect = downloadModule.getBoundingClientRect();
      const scrollTop = scrollContainer.scrollTop + downloadRect.top - containerRect.top - 24;

      scrollContainer.scrollTo({
        top: scrollTop,
        behavior: 'smooth'
      });
    } catch (error) {
      console.error('❌ Error scrolling to Download:', error);
    }
  };

  // Helper: safe auto-scroll to Signering module
  const scrollToSignering = () => {
    try {
      const signeringModule = document.querySelector('[data-section="signering"]') as HTMLElement | null;
      // Anpassa selektor nedan till din scroll-container om du har en annan klass
      const scrollContainer =
        (document.querySelector('.overflow-auto') as HTMLElement | null) ||
        (document.querySelector('[data-scroll-container="chat"]') as HTMLElement | null);

      if (!signeringModule || !scrollContainer) {
        return;
      }

      const containerRect = scrollContainer.getBoundingClientRect();
      const signeringRect = signeringModule.getBoundingClientRect();
      const scrollTop = scrollContainer.scrollTop + signeringRect.top - containerRect.top - 24;

      scrollContainer.scrollTo({
        top: scrollTop,
        behavior: 'smooth'
      });
    } catch (error) {
      console.error('❌ Error scrolling to Signering:', error);
    }
  };

  // Evaluate conditions for showing a step
  const evaluateConditions = (conditions: any): boolean => {
    if (!conditions) return true;

    try {
      // Parse JSON conditions if string
      const parsedConditions = typeof conditions === 'string' ? JSON.parse(conditions) : conditions;
      
      // Check for complex mathematical conditions  
      if (parsedConditions.formula) {
        // For step 201: Should show if sarskild_loneskatt_pension_calculated > sarskild_loneskatt_pension
        // The calculated amount is already computed by backend using the correct global rate
        const pensionPremier = companyData.pensionPremier || 0;
        const sarskildLoneskattPension = companyData.sarskildLoneskattPension || 0;
        const sarskildLoneskattPensionCalculated = companyData.sarskildLoneskattPensionCalculated || 0;
        
        
        // Show step 201 if there are pension premiums AND calculated tax > booked tax
        const shouldShow = pensionPremier > 0 && sarskildLoneskattPensionCalculated > sarskildLoneskattPension;
        
        return shouldShow;
      }

      // Simple condition evaluation for backward compatibility
      for (const [key, condition] of Object.entries(parsedConditions)) {
        const value = (companyData as any)[key];
        
        if (typeof condition === 'object' && condition !== null) {
          if ('gt' in condition) {
            const compareValue = typeof condition.gt === 'string' 
              ? (companyData as any)[condition.gt] 
              : condition.gt;
            if (!(value > compareValue)) return false;
          }
          // Add more condition types as needed
        }
      }

      return true;
    } catch (e) {
      console.error('Error parsing conditions:', e);
      return true; // Default to showing step if condition parsing fails
    }
  };

  // Handle option selection
  const handleOptionSelect = async (option: ChatOption, explicitStepNumber?: number, updatedInk2Data?: any[]) => {
    try {
      setIsWaitingForUser(false); // User took action, stop waiting
      
      // Add user message only if there's actual text
      const optionText = option.option_text || '';
      if (optionText && optionText.trim() !== '') {
        addMessage(optionText, false);
      }

      // Immediate scroll to Signering when clicking "Fortsätt till signering" at step 510
      if (currentStep === 510 && option.option_value === 'continue' && option.next_step === 515) {
        scrollToSignering();
      }

      // Handle special cases first
      // Handle custom tax options to bypass API call
      if (option.option_value === 'approve_tax') {
        // Hide tax preview and go to next step based on SQL or fallback
        
        // Set default radio button values if not already set
        const currentAccepted = companyData.acceptedInk2Manuals || {};
        const needsDefaults = !currentAccepted['INK4.23a'] && !currentAccepted['INK4.23b'] && 
                              !currentAccepted['INK4.24a'] && !currentAccepted['INK4.24b'];
        
        const updatedAccepted = needsDefaults ? {
          ...currentAccepted,
          'INK4.23a': 0,
          'INK4.23b': 1,  // Default to "Nej"
          'INK4.24a': 0,
          'INK4.24b': 1   // Default to "Nej"
        } : currentAccepted;
        
        onDataUpdate({ 
          showTaxPreview: false,
          acceptedInk2Manuals: updatedAccepted
        });
        
        const nextStep = option.next_step || 420; // Use SQL next_step or fallback to 420
        
        // Auto-scroll to Noter section when going to step 420
        if (nextStep === 420) {
          setTimeout(() => {
            const noterModule = document.querySelector('[data-section="noter"]');
            const scrollContainer = document.querySelector('.overflow-auto');
            
            if (noterModule && scrollContainer) {
              const containerRect = scrollContainer.getBoundingClientRect();
              const noterRect = noterModule.getBoundingClientRect();
              const scrollTop = scrollContainer.scrollTop + noterRect.top - containerRect.top - 40; // 40pt padding to show heading
              
              scrollContainer.scrollTo({
                top: scrollTop,
                behavior: 'smooth'
              });
            }
          }, 200);
        }
        
        setTimeout(() => {
          loadChatStep(nextStep);
        }, 1000);
        return;
      }
      
      // Handle approve_calculated - trigger tax update logic
      if (option.option_value === 'approve_calculated') {
        try {
          await handleTaxUpdateForApproval();
        } catch (error) {
          console.error('🎯 Error calling handleTaxUpdateForApproval:', error);
        }
      }
      
      if (option.option_value === 'review_adjustments') {
        // Show tax module using the flag
        onDataUpdate({ showTaxPreview: true });
        // Auto-scroll to tax module after a short delay
        setTimeout(() => {
          const taxModule = document.querySelector('[data-section="tax-calculation"]');
          const scrollContainer = document.querySelector('.overflow-auto');
          if (taxModule && scrollContainer) {
            const containerRect = scrollContainer.getBoundingClientRect();
            const taxRect = taxModule.getBoundingClientRect();
            const scrollTop = scrollContainer.scrollTop + taxRect.top - containerRect.top - 10; // 5-7pt padding from top
            
            scrollContainer.scrollTo({
              top: scrollTop,
              behavior: 'smooth'
            });
          }
        }, 500);
        
        // Check conditions for step 201 before navigating
        setTimeout(async () => {
          try {
            const step201Response = await apiService.getChatFlowStep(201) as ChatFlowResponse;
            if (step201Response.success && step201Response.show_conditions) {
              const shouldShow = evaluateConditions(step201Response.show_conditions);
              
              if (shouldShow) {
                loadChatStep(201);
              } else {
                // Skip to step 301 if condition not met
                loadChatStep(301);
              }
            } else {
              // No conditions, proceed normally
              loadChatStep(201);
            }
          } catch (error) {
            console.error('Error checking step 201 conditions:', error);
            // Fallback to normal navigation
            loadChatStep(201);
          }
        }, 1000);
        return;
      }
      
      // Handle pension tax adjustments
      if (option.option_value === 'adjust_calculated') {
        const delta = (companyData.sarskildLoneskattPensionCalculated || 0)
                    - (companyData.sarskildLoneskattPension || 0);
        await applyChatOverrides({ sarskild: delta });
        
        try {
          const step202Response = await apiService.getChatFlowStep(202) as ChatFlowResponse;
          addMessage(step202Response.question_text, true, step202Response.question_icon, () => {
            // Wait for message animation to complete before loading next step
            setTimeout(() => loadChatStep(301), 500);
          });
        } catch (error) {
          console.error('❌ Error fetching step 202:', error);
          addMessage('Perfekt, nu är den särskilda löneskatten justerad som du kan se i skatteuträkningen till höger.', true, '✅', () => {
            setTimeout(() => loadChatStep(301), 500);
          });
        }
        return;
      }
      
      if (option.option_value === 'keep_current') {
        // Keep current pension tax
        onDataUpdate({ justeringSarskildLoneskatt: 'current' });
        setTimeout(() => loadChatStep(301), 1000); // Go to underskott question
        return;
      }
      
      // Handle "no unused tax loss" from step 301
      if (option.option_value === 'none' && (explicitStepNumber || currentStep) === 301) {
        onDataUpdate({ unusedTaxLossAmount: 0 });
        await loadChatStep(401, globalInk2Data);
        return;
      }

      // Note: enter_custom is now handled by database-driven flow (show_input action)

      // Get the most recent inkBeraknadSkatt value from global data first, then INK2 data
      let mostRecentInkBeraknadSkatt = globalInkBeraknadSkatt || companyData.inkBeraknadSkatt;
      const ink2DataToUse = updatedInk2Data || globalInk2Data || companyData.ink2Data;
      if (ink2DataToUse && ink2DataToUse.length > 0) {
        const inkBeraknadSkattItem = ink2DataToUse.find((item: any) => 
          item.variable_name === 'INK_beraknad_skatt'
        );
        if (inkBeraknadSkattItem && inkBeraknadSkattItem.amount !== undefined) {
          mostRecentInkBeraknadSkatt = inkBeraknadSkattItem.amount;
        }
      }
      
      // Process the choice through the API
      // Use the most recent inkBeraknadSkatt value if available
      const context = {
        unusedTaxLossAmount: companyData.unusedTaxLossAmount || 0,
        inkBeraknadSkatt: mostRecentInkBeraknadSkatt || 0,
        inkBokfordSkatt: companyData.inkBokfordSkatt || 0,
        SkattAretsResultat: companyData.skattAretsResultat || 0
      };
      

      const response = await apiService.processChatChoice({
        step_number: explicitStepNumber || currentStep,
        option_value: option.option_value,
        context
      });

      if (response.success) {
        const { action_type, action_data, next_step } = response.result;
        

        // Embedded checkout interception logic
        const isPaymentChoice = option?.option_value === "stripe_payment";
        let interceptedExternalRedirect = false;

        // Process the action
        
        // Special option handling moved to earlier section
        
        switch (action_type) {
          case 'set_variable':
            // Handle variable setting while preserving existing data
            if (action_data?.variable && action_data?.value !== undefined) {
              // Preserve existing ink2Data when setting variables to prevent data loss
              const updateData: any = { [action_data.variable]: action_data.value };
              if (companyData.ink2Data && companyData.ink2Data.length > 0) {
                updateData.ink2Data = companyData.ink2Data;
              }
              if (globalInk2Data && globalInk2Data.length > 0) {
                updateData.ink2Data = globalInk2Data;
              }
              
              // Special handling for dividend: calculate balanseras amount for message substitution
              if (action_data.variable === 'arets_utdelning') {
                const dividendAmount = Number(action_data.value) || 0;
                const maxDividend = companyData.sumFrittEgetKapital || 0;
                const balancerasAmount = maxDividend - dividendAmount;
                
                // Store both values for message substitution
                updateData.arets_balanseras_nyrakning = balancerasAmount;
                
                // Special navigation for dividend with temp data
                if (next_step) {
                  onDataUpdate(updateData);
                  // Pass temporary data with calculated values for immediate substitution
                  const tempData = {
                    ...companyData,
                    arets_utdelning: dividendAmount,
                    arets_balanseras_nyrakning: balancerasAmount
                  };
                  setTimeout(() => loadChatStep(next_step, updatedInk2Data, tempData), 500);
                  return; // Skip normal navigation
                }
              }
              
              onDataUpdate(updateData);
            }
            break;
            
          case 'api_call':
            await handleApiCall(action_data);
            // CRITICAL FIX: Return early to prevent navigation until validation passes
            // The api_call handler (like signing) will navigate when ready
            return;
            
          case 'enable_editing':
            // Enable tax editing mode immediately
            onDataUpdate({ taxEditingEnabled: true, editableAmounts: true, showTaxPreview: true });
            // Ensure we land on the manual editing step 402
            const targetStep = next_step || 402;
            setTimeout(() => loadChatStep(targetStep), 200);
            return; // Stop further navigation below

          case 'show_input':
            // Prefer explicit navigation to the input step if provided
            if (next_step) {
              setTimeout(() => loadChatStep(next_step, updatedInk2Data), 300);
              return; // Avoid double-navigation by skipping general nav below
            }
            // Fallback: show inline input on current step if no next_step
            setShowInput(true);
            setInputType(action_data?.input_type || 'amount');
            setInputPlaceholder(action_data?.input_placeholder || 'Ange belopp i kr...');
            break;
            
          case 'show_file_upload':
            setShowFileUpload(true);
            return; // Don't navigate to next step yet
            
          case 'navigate':
            // Simple navigation to next step
            // Show tax module for tax-related steps
            if (next_step === 201 || next_step === 202 || next_step === 203 || 
                next_step === 301 || next_step === 302 || next_step === 303 || 
                next_step === 401 || next_step === 402 || next_step === 405) {
              onDataUpdate({ showTaxPreview: true });
            }
            break;

          case "show_payment_module":
            window.dispatchEvent(new Event("summare:showPayment"));
            // Auto-scroll is now handled by step 506 watcher for better timing
            break;
            
          case "external_redirect": {
            const forceEmbed = (explicitStepNumber || currentStep) === 505 && isPaymentChoice;

            if (forceEmbed) {
              loadChatStep(506); // Load payment loading message from database
              // IMPORTANT: return here so we don't fall through to general navigation
              return;
            }

            if (action_data?.url) {
              window.open(action_data.url, action_data.target || "_blank");
            }
            break;
          }
            
          case 'process_input':
            // Handle input processing
            if (action_data?.variable) {
              // The input value should already be stored in companyData
              // This action type is mainly for navigation
            }
            break;
            
          case 'save_manual_tax':
            // CRITICAL FIX: Trigger the INK2 approve logic to save changes and ripple to RR/BR
            // This ensures the chat flow button has the same behavior as the blue button
            // The INK2 approval will handle navigation to step 405, so we return early to prevent
            // the chat flow from navigating naturally (which would cause duplicate messages)
            onDataUpdate({ triggerInk2Approve: true });
            return; // Exit early to prevent duplicate navigation
            
          case 'reset_tax_edits':
            // Reset tax editing mode
            onDataUpdate({ taxEditingEnabled: false, editableAmounts: false });
            break;
            
          case 'generate_pdf':
            // Handle PDF generation
            break;
            
          case 'complete_session':
            // Handle session completion
            break;
            
          case 'show_periodiseringsfonder':
            // Show periodiseringsfonder module
            onDataUpdate({ showPeriodiseringsfonder: true });
            break;
        }

        // 🔔 Instant UX for chat-driven edit mode (step 401 -> 402 or explicit edit_mode)
        if (
          // 1) explicit SQL signal
          action_data?.edit_mode === 'enable'
          // 2) OR the common 401 -> 402 flow used in your script
          || (currentStep === 401 && (next_step === 402))
        ) {
          // Open manual edit + show all rows (including zeros) immediately
          onDataUpdate({ taxEditingEnabled: true, editableAmounts: true, showAllTax: true });
        }

        if (action_data?.edit_mode === 'disable') {
          onDataUpdate({ taxEditingEnabled: false, editableAmounts: false, showAllTax: false });
        }

        // Navigate to next step
        
        // IMPORTANT: Prevent re-navigation to step 405 after first time
        // After user has seen step 405 once, manual edits should update silently
        if (next_step === 405 && companyData.taxButtonClickedBefore) {
          // Don't navigate, just stay at current step
          return;
        }
        
        if (next_step && !interceptedExternalRedirect) {
          
          // Auto-scroll to noter section for step 420
          if (next_step === 420) {
            setTimeout(() => {
              const noterModule = document.querySelector('[data-section="noter"]');
              const scrollContainer = document.querySelector('.overflow-auto');
              
              if (noterModule && scrollContainer) {
                const containerRect = scrollContainer.getBoundingClientRect();
                const noterRect = noterModule.getBoundingClientRect();
                
                // Determine padding based on previous step:
                // - From 101, 401 (approve tax): -10pt padding for clean scroll to top
                // - From 402, 405 (after manual edits): -80pt padding to show frame edge
                let padding = -10; // Default for direct approval
                if (previousStepRef.current === 402 || previousStepRef.current === 405) {
                  padding = -80; // More padding when coming from manual edits
                }
                
                const scrollTop = scrollContainer.scrollTop + noterRect.top - containerRect.top + padding;
                
                scrollContainer.scrollTo({
                  top: scrollTop,
                  behavior: 'smooth'
                });
              }
            }, 500);
          }
          
          // Auto-scroll to förvaltningsberättelse section for step 422
          if (next_step === 422) {
            setTimeout(() => {
              const fbModule = document.querySelector('[data-section="forvaltningsberattelse"]');
              const scrollContainer = document.querySelector('.overflow-auto');
              
              if (fbModule && scrollContainer) {
                const containerRect = scrollContainer.getBoundingClientRect();
                const fbRect = fbModule.getBoundingClientRect();
                const scrollTop = scrollContainer.scrollTop + fbRect.top - containerRect.top - 10; // 10pt padding from top
                
                scrollContainer.scrollTo({
                  top: scrollTop,
                  behavior: 'smooth'
                });
              }
            }, 500);
          }
          
          // Auto-scroll to Förvaltningsberättelse (Resultatdisposition) on step 424
          // User clicked "Utdelning" in step 423, now entering dividend amount
          if (next_step === 424) {
            setTimeout(() => {
              const fbModule = document.querySelector('[data-section="forvaltningsberattelse"]') as HTMLElement | null;
              const scrollContainer = 
                (document.querySelector('.overflow-auto') as HTMLElement | null) ||
                (document.querySelector('[data-scroll-container="chat"]') as HTMLElement | null);
              
              if (fbModule && scrollContainer) {
                const containerRect = scrollContainer.getBoundingClientRect();
                const fbRect = fbModule.getBoundingClientRect();
                // Scroll to bottom of Förvaltningsberättelse section with extra padding
                const scrollTop = scrollContainer.scrollTop + fbRect.top - containerRect.top + fbRect.height - containerRect.height + 150;
                
                scrollContainer.scrollTo({
                  top: scrollTop,
                  behavior: 'smooth'
                });
              }
            }, 500);
          }
          
          // Auto-scroll after dividend entry at step 501 to show Styrelsen text
          if (next_step === 501) {
            setTimeout(() => {
              const fbModule = document.querySelector('[data-section="forvaltningsberattelse"]') as HTMLElement | null;
              const scrollContainer = 
                (document.querySelector('.overflow-auto') as HTMLElement | null) ||
                (document.querySelector('[data-scroll-container="chat"]') as HTMLElement | null);
              
              if (fbModule && scrollContainer) {
                const containerRect = scrollContainer.getBoundingClientRect();
                const fbRect = fbModule.getBoundingClientRect();
                // Scroll to show the full Styrelsen text after Resultatdisposition
                const scrollTop = scrollContainer.scrollTop + fbRect.top - containerRect.top + fbRect.height - containerRect.height + 200;
                
                scrollContainer.scrollTo({
                  top: scrollTop,
                  behavior: 'smooth'
                });
              }
            }, 800);
          }
          
          // Auto-scroll to Download on step 510
          if (next_step === 510) {
            setTimeout(() => scrollToDownload(), 500);
          }
          
          setTimeout(() => loadChatStep(next_step, updatedInk2Data), 1000);
        } else if (interceptedExternalRedirect) {
        } else {
        }
      }
    } catch (error) {
      console.error('Error handling option:', error);
      addMessage('Något gick fel. Försök igen.', true, '❌');
    }
  };

  // Robust number coercion helper
  const toNumber = (v: any) => {
    if (typeof v === 'number') return v;
    if (typeof v !== 'string') return NaN;
    // keep minus, digits, dot/comma; normalize comma -> dot; strip spaces
    const cleaned = v.replace(/[^\d\-,.]/g, '').replace(/\s+/g, '').replace(',', '.');
    const n = Number(cleaned);
    return Number.isFinite(n) ? n : NaN;
  };

  const isNonZeroNumber = (v: any): v is number =>
    typeof v === 'number' && Number.isFinite(v) && v !== 0;

  // Normalizes SQL action_data.variable into the canonical tax keys we use for overrides
  const normalizeSqlVar = (v?: string): 'INK4.14a' | 'justering_sarskild_loneskatt' | undefined => {
    if (!v) return undefined;
    const s = v.trim().toLowerCase();

    // --- Unused tax loss -> INK4.14a ---
    // Handles: unusedTaxLossAmount, ink4_14a, ink4.14a, ink4_14a_outnyttjat_underskott, outnyttjat_underskott
    if (
      s === 'unusedtaxlossamount' ||
      s === 'ink4_14a' ||
      s === 'ink4.14a' ||
      s === 'ink4_14a_outnyttjat_underskott' ||
      s === 'outnyttjat_underskott'
    ) return 'INK4.14a';

    // --- Pension LSS adjustment -> justering_sarskild_loneskatt ---
    // Handles: sarskildLoneskattCustom, justering_sarskild_loneskatt, sarskild_loneskatt
    if (
      s === 'sarskildloneskattcustom' ||
      s === 'justering_sarskild_loneskatt' ||
      s === 'sarskild_loneskatt'
    ) return 'justering_sarskild_loneskatt';

    return undefined;
  };

/* =====================  INK2 LOGIC (Chat)  ===================== */

// Same CALC_ONLY as preview
const CALC_ONLY = new Set<string>([
  "INK_skattemassigt_resultat",
  "INK_beraknad_skatt",
  "INK4.15",
  "INK4.16",
  "Arets_resultat_justerat",
  "INK4.1",  // Injected from Årets resultat (justerat)
  "INK4.2",  // Injected from Årets resultat (justerat)  
  "INK4.3a", // Injected from INK_beraknad_skatt
]);

const isHeader = (n?: string) => !!n && /_header$/i.test(n || "");
const isCalculated = (n?: string) => !!n && CALC_ONLY.has(n);

/** Build baseline manuals from current visible rows */
const buildBaselineManualsFromCurrent = (rows: any[]): Record<string, number> => {
  const out: Record<string, number> = {};
  for (const r of rows || []) {
    const v = r.variable_name;
    if (!isHeader(v) && !isCalculated(v)) {
      const n = typeof r.amount === "number" ? r.amount : Number(r.amount || 0);
      if (Number.isFinite(n)) out[v] = n;
    }
  }
  return out;
};

/** Selective merge: include manual keys; only CALC_ONLY from server */
const selectiveMergeInk2 = (
  prevRows: any[],
  newRows: any[],
  manuals: Record<string, number>
) => {
  const prevBy = new Map(prevRows.map((r: any) => [r.variable_name, r]));
  const nextBy = new Map(newRows.map((r: any) => [r.variable_name, r]));
  const manualNames = Object.keys(manuals);

  const names = new Set<string>([
    ...prevBy.keys(),
    ...nextBy.keys(),
    ...manualNames,
  ]);

  const out: any[] = [];
  for (const name of names) {
    const prev = prevBy.get(name);
    const next = nextBy.get(name);
    const base =
      prev ??
      next ?? {
        variable_name: name,
        row_title: name,
        amount: 0,
        always_show: true,
        show_tag: true,
        style: "TNORMAL",
      };
    let amount = base.amount;
    if (Object.prototype.hasOwnProperty.call(manuals, name)) amount = manuals[name];
    else if (CALC_ONLY.has(name) && next) amount = next.amount;
    out.push({ ...base, amount });
  }

  out.sort((a, b) => (a.order_index ?? 0) - (b.order_index ?? 0));
  return out;
};

  // Chat override helper (call this whenever chat injects values)
  const applyChatOverrides = async ({
    underskott,   // INK4.14a
    sarskild      // justering_sarskild_loneskatt
  }: { underskott?: number; sarskild?: number }) => {

    const prevRows = companyData.ink2Data || [];
    const baseline = buildBaselineManualsFromCurrent(prevRows);

    const manuals: Record<string, number> = {
      ...baseline,
      ...(companyData.acceptedInk2Manuals || {}),
    };

    if (typeof underskott === 'number') {
      onDataUpdate({ unusedTaxLossAmount: underskott });
      if (underskott !== 0) manuals['INK4.14a'] = underskott;
    }

    if (typeof sarskild === 'number') {
      onDataUpdate({ justeringSarskildLoneskatt: sarskild });
      if (sarskild !== 0) manuals['justering_sarskild_loneskatt'] = sarskild;
    }

    // If both are zero/undefined and there are no accepted manuals, nothing to send
    if (Object.keys(manuals).length === 0) return;

    // Optional: Skip backend call when nothing actually changed
    const acceptedManuals = companyData.acceptedInk2Manuals || {};
    const before = Object.keys(acceptedManuals).sort().join('|');
    const after = Object.keys(manuals).sort().join('|');
    if (before === after) {
      // No new chat values were added; nothing to recalc
      return;
    }

    // For chat injections, we need to:
    // 1. Use original baseline RR/BR data (so INK4.1/INK4.2 calculate from clean values)
    // 2. But include the accepted SLP amount in manual_amounts (so it's in the formula)
    
    // Get original baseline RR/BR data if available
    const originalRrData = (window as any).__originalRrData || companyData.seFileData?.rr_data || [];
    const originalBrData = (window as any).__originalBrData || companyData.seFileData?.br_data || [];
    
    // Include accepted SLP in manual_amounts for chat injections
    // CRITICAL FIX: Only include SLP if it's a number, not a string like 'current' or 'calculated'
    const chatManuals = { ...manuals };
    const slpValue = companyData.justeringSarskildLoneskatt;
    if (typeof slpValue === 'number' && slpValue !== 0) {
      chatManuals['justering_sarskild_loneskatt'] = Math.abs(slpValue);
    }

    const resp = await apiService.recalculateInk2({
      current_accounts: companyData.seFileData?.current_accounts || {},
      fiscal_year: companyData.fiscalYear,
      rr_data: originalRrData,
      br_data: originalBrData,
      manual_amounts: chatManuals, // CHAT ONLY with SLP included
      // @ts-ignore - Backend safely ignores unknown properties
      is_chat_injection: true, // Flag to preserve SLP in calculation
      // @ts-ignore - Optional optimization hint; safe if backend ignores it
      recalc_only_vars: [
        'INK_skattemassigt_resultat',
        'INK_beraknad_skatt',
        'INK4.15',
        'INK4.16',
        'Arets_resultat_justerat',
      ]
    });

    const prev = companyData.ink2Data || [];
    if (resp?.success) {
      // For UI merge, translate backend pension key → UI row name so it shows immediately
      const displayManuals = { ...manuals };
      if (Object.prototype.hasOwnProperty.call(displayManuals, 'justering_sarskild_loneskatt')) {
        const v = Math.abs(displayManuals['justering_sarskild_loneskatt'] || 0);
        displayManuals['INK_sarskild_loneskatt'] = -v; // UI row shows (-)
        delete displayManuals['justering_sarskild_loneskatt'];
      }
      // client-side selective merge to enforce calc-only updates
      const merged = selectiveMergeInk2(prev, resp.ink2_data, displayManuals);
      const skatt = merged.find((i:any)=>i.variable_name==='INK_beraknad_skatt')?.amount || 0;
      onDataUpdate({ ink2Data: merged, inkBeraknadSkatt: skatt });
      setGlobalInk2Data?.(merged);
      setGlobalInkBeraknadSkatt?.(skatt);
      
      // If SLP was injected (including when set to 0), immediately update RR/BR with the SLP changes
      // This ensures previous SLP effects are reversed when SLP becomes 0
      if (typeof sarskild === 'number') {
        await updateRrBrWithSlp(merged);
      }
      
      // Return the updated values for immediate use
      return { ink2Data: merged, inkBeraknadSkatt: skatt };
    }
    
    // Return null if no response
    return null;
  };

  // Helper function to update RR/BR with SLP changes immediately (SLP only, no tax changes)
  const updateRrBrWithSlp = async (ink2Data: any[]) => {
    try {
      
      // Get INK_bokford_skatt value - we'll use this for both beraknad and bokford
      // so that taxDifference = 0 (only SLP will be injected, not tax changes)
      const bokfordSkattItem = ink2Data.find((item: any) => item.variable_name === 'INK_bokford_skatt');
      
      if (!bokfordSkattItem) {
        return;
      }

      const inkBokfordSkatt = bokfordSkattItem.amount || 0;
      
      // Get SLP amount
      const inkSarskildLoneskatt = getAcceptedSLP(ink2Data, companyData);
      
      // IMPORTANT: Set inkBeraknadSkatt = inkBokfordSkatt so taxDifference = 0
      // This ensures ONLY SLP is injected, not the calculated tax changes
      const requestData = {
        inkBeraknadSkatt: inkBokfordSkatt,  // Same as booked, so no tax change
        inkBokfordSkatt,
        taxDifference: 0,  // Explicitly 0 - only SLP should be applied
        rr_data: companyData.seFileData?.rr_data || [],
        br_data: companyData.seFileData?.br_data || [],
        organizationNumber: companyData.organizationNumber,
        fiscalYear: companyData.fiscalYear,
        inkSarskildLoneskatt,
        slpOnly: true,  // Flag to indicate this is SLP-only injection
      };
      
      const response = await fetch(`${import.meta.env.VITE_API_URL || 'https://api.summare.se'}/api/update-tax-in-financial-data`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestData),
      });

      if (!response.ok) {
        const errorText = await response.text();
        console.error('❌ API error response:', errorText);
        
        if (response.status === 404) {
          return;
        }
        
        throw new Error(`HTTP error! status: ${response.status}, body: ${errorText}`);
      }

      const result = await response.json();
      
      if (result.success) {
        
        // Update company data with new RR/BR data
        onDataUpdate({
          seFileData: {
            ...companyData.seFileData,
            rr_data: result.rr_data,
            br_data: result.br_data,
          }
        });
      } else {
        console.error('❌ Failed to update RR/BR data:', result.error);
      }
      
    } catch (error) {
      console.error('❌ Error in updateRrBrWithSlp:', error);
    }
  };

  // Handle API calls triggered by chat actions
  const handleApiCall = async (actionData: any) => {
    if (actionData?.endpoint === 'recalculate_ink2') {
      try {
        const params = actionData.params || {};
        const substitutedParams: any = { ...params };

        // Substitute placeholders AND coerce to numbers if possible
        for (const [key, value] of Object.entries(substitutedParams)) {
          if (typeof value === 'string' && value.includes('{')) {
            const substituted = value.replace(/{(\w+)}/g, (match, varName) => {
              if (varName === 'unusedTaxLossAmount') {
                const pending = companyData.unusedTaxLossAmount;
                if (pending && pending > 0) return String(pending);
              }
              const repl = (companyData as any)[varName];
              return (repl ?? match).toString();
            });
            const asNum = toNumber(substituted);
            substitutedParams[key] = Number.isFinite(asNum) ? asNum : substituted;
          }
        }

        // Coerce known numeric params
        ['justering_sarskild_loneskatt', 'ink4_14a_outnyttjat_underskott'].forEach(k => {
          if (k in substitutedParams) {
            const coerced = toNumber(substitutedParams[k]);
            if (Number.isFinite(coerced)) substitutedParams[k] = coerced;
          }
        });

        if (companyData.seFileData) {
          const result = await apiService.recalculateInk2({
            current_accounts: companyData.seFileData.current_accounts || {},
            fiscal_year: companyData.fiscalYear,
            rr_data: companyData.seFileData.rr_data || [],
            br_data: companyData.seFileData.br_data || [],
            ...substitutedParams
          });

          if (result?.success) {
            onDataUpdate({
              ink2Data: result.ink2_data,
              inkBeraknadSkatt:
                result.ink2_data.find((i: any) => i.variable_name === 'INK_beraknad_skatt')?.amount
                ?? companyData.inkBeraknadSkatt,
            });
            setGlobalInk2Data(result.ink2_data);
          }
        }
      } catch (error) {
        console.error('API call failed:', error);
      }
    } else if (actionData?.endpoint === 'send_for_digital_signing') {
      // CRITICAL FIX: Trigger the Signering module's own send logic to get exact same behavior
      // This ensures validation popups and success messages appear in the Signering module, not in chat
      onDataUpdate({ triggerSigneringSend: true });
    }
  };

  // Handle input submission
  const handleInputSubmit = async () => {
    if (!inputValue.trim()) return;

    const value = inputType === 'amount' 
      ? parseFloat(inputValue.replace(/\s/g, '').replace(/,/g, '.')) || 0
      : inputValue.trim();
    
    
    // Find the submit option to check if this is dividend input
    const submitOption = lastLoadedOptions?.find(opt => opt.option_value === 'submit');
    
    // Validate dividend amount (step 424: arets_utdelning)
    if (submitOption?.action_data?.variable === 'arets_utdelning' && inputType === 'amount') {
      const dividendAmount = value as number;
      const maxDividend = companyData.sumFrittEgetKapital || 0;
      
      if (dividendAmount < 0) {
        addMessage('Utdelningen kan inte vara negativ. Vänligen försök igen.', true, '🤖');
        setInputValue(''); // Clear the input field
        setShowInput(true); // Keep input visible
        return;
      }
      
      if (dividendAmount > maxDividend) {
        const maxFormatted = new Intl.NumberFormat('sv-SE', { minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(maxDividend);
        addMessage(`Utdelningen kan inte överstiga fritt eget kapital ${maxFormatted} kr. Vänligen försök igen.`, true, '🤖');
        setInputValue(''); // Clear the input field
        setShowInput(true); // Keep input visible
        return;
      }
    }
    
    // Hide input immediately to prevent UI flash
    setShowInput(false);

    // Add user message
    const displayValue = inputType === 'amount' 
      ? new Intl.NumberFormat('sv-SE', { minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(value as number) + ' kr'
      : value;
    addMessage(String(displayValue), false);

    if (submitOption) {
        // Store the input value based on action data
        if (submitOption.action_data?.variable) {
          // Store dividend input and calculate balanseras for substitution
          if (submitOption.action_data.variable === 'arets_utdelning' && inputType === 'amount') {
            // Use absolute value only after validation passes
            const dividendAmount = Math.abs(value as number);
            const maxDividend = companyData.sumFrittEgetKapital || 0;
            const balancerasAmount = maxDividend - dividendAmount;
            
            // Store only dividend amount (positive)
            onDataUpdate({ arets_utdelning: dividendAmount });
            
            // Special handling for dividend: pass temp data for immediate substitution
            if (submitOption.next_step) {
              setShowInput(false);
              setInputValue('');
              // Pass temporary data with calculated balanseras amount for substitution
              const tempData = {
                ...companyData,
                arets_utdelning: dividendAmount,
                arets_balanseras_nyrakning: balancerasAmount // Only for message substitution
              };
              setTimeout(() => loadChatStep(submitOption.next_step!, undefined, tempData), 500);
              return; // Don't continue to normal navigation
            }
          } else {
            // For other variables, store normally
            onDataUpdate({ [submitOption.action_data.variable]: value });
          }

        // Handle chat override variables (driven by SQL action_data.variable)
        const opt = submitOption; // from SQL
        const varFromSql = normalizeSqlVar(opt?.action_data?.variable);

        // Preserve existing value parsing
        const numericValue = inputType === 'amount' 
          ? Math.abs(parseFloat(inputValue.replace(/\s/g, '').replace(/,/g, '.')) || 0)
          : (typeof value === 'number' ? value : Number(String(value).replace(/\s/g, '').replace(',', '.')));

        // Route into overrides for our two supported variables, regardless of action_type
        if (varFromSql) {
          // Route to our chat override helper and get updated values
          const updatedData = await applyChatOverrides({
            underskott: varFromSql === 'INK4.14a' ? numericValue : undefined,
            sarskild: varFromSql === 'justering_sarskild_loneskatt' ? numericValue : undefined,
          });

          // ✅ ALWAYS continue the SQL flow after injection
          const next = opt.next_step
            // Safe fallbacks if SQL forgot next_step:
            ?? (currentStep === 302 ? 303 : undefined)
            ?? (currentStep === 201 ? 202 : undefined)
            ?? currentStep + 1; // conservative fallback

          setShowInput(false);
          setInputValue('');
          // Pass the updated ink2Data to ensure step 401 gets the latest inkBeraknadSkatt
          setTimeout(() => loadChatStep(next, updatedData?.ink2Data || globalInk2Data), 300);
          return; // ← Important: we handled it, don't continue to legacy paths
        }

        // Note: Unused tax loss recalculation happens in step 303 via api_call, not here
        
        // Special handling for custom pension tax amount
        if (submitOption.action_data.variable === 'sarskildLoneskattCustom') {
          const amount = value as number;
          const sarskildLoneskattPension = companyData.sarskildLoneskattPension || 0;
          const adjustment = amount - sarskildLoneskattPension;
          
          onDataUpdate({ 
            justeringSarskildLoneskatt: 'custom',
            sarskildLoneskattPensionSubmitted: amount 
          });
          
          await applyChatOverrides({ sarskild: adjustment });
          
          try {
            const step202Response = await apiService.getChatFlowStep(202) as ChatFlowResponse;
            addMessage(step202Response.question_text, true, step202Response.question_icon, () => {
              // Wait for message animation to complete before loading next step
              setShowInput(false);
              setInputValue('');
              setTimeout(() => loadChatStep(202), 500);
            });
          } catch (error) {
            console.error('❌ Error fetching step 202:', error);
            addMessage('Perfekt, nu är den särskilda löneskatten justerad som du kan se i skatteuträkningen till höger.', true, '✅', () => {
              setShowInput(false);
              setInputValue('');
              setTimeout(() => loadChatStep(202), 500);
            });
          }
          return;
        }
      }

      // Navigate to next step (unless we're handling special cases)
      if (submitOption.next_step && 
          submitOption.action_data?.variable !== 'sarskildLoneskattCustom') {
        setShowInput(false);
        setInputValue('');
        setTimeout(() => loadChatStep(submitOption.next_step!), 500);
      }
    }
  };

  // Handle file upload
  const handleFileProcessed = async (fileData: any) => {
    // Extract data from the uploaded file (same logic as old system)
    let extractedResults = null;
    let sumAretsResultat = null;
    let sumFrittEgetKapital = null;
    let skattAretsResultat = null;
    
    // Try to extract net result from RR data
    if (fileData.data?.rr_data) {
      const netResultItem = fileData.data.rr_data.find((item: any) => 
        item.id === 'ÅR' || item.label?.toLowerCase().includes('årets resultat')
      );
      if (netResultItem && netResultItem.current_amount !== null) {
        extractedResults = netResultItem.current_amount.toString();
      }
      
            // Extract SumAretsResultat for chat options (check RR first, then BR)
      // First try to find exact variable name match in RR data
      let sumAretsResultatItem = fileData.data.rr_data.find((item: any) => 
        item.variable_name === 'SumAretsResultat'
      );
      
      // If not found in RR, try ID match in RR
      if (!sumAretsResultatItem) {
        sumAretsResultatItem = fileData.data.rr_data.find((item: any) => 
          item.id === 'ÅR'
        );
      }
      
      // If still not found in RR, try label match but exclude SkattAretsResultat
      if (!sumAretsResultatItem) {
        sumAretsResultatItem = fileData.data.rr_data.find((item: any) => 
          item.label?.toLowerCase().includes('årets resultat') &&
          item.variable_name !== 'SkattAretsResultat'
        );
      }
      
      // If not found in RR, try BR data
      if (!sumAretsResultatItem && fileData.data?.br_data) {
        sumAretsResultatItem = fileData.data.br_data.find((item: any) => 
          item.variable_name === 'SumAretsResultat'
        );
      }
      
      // If still not found in BR, try ID match in BR
      if (!sumAretsResultatItem && fileData.data?.br_data) {
        sumAretsResultatItem = fileData.data.br_data.find((item: any) => 
          item.id === 'ÅR'
        );
      }
      
      // If still not found in BR, try label match but exclude SkattAretsResultat
      if (!sumAretsResultatItem && fileData.data?.br_data) {
        sumAretsResultatItem = fileData.data.br_data.find((item: any) => 
          item.label?.toLowerCase().includes('årets resultat') &&
          item.variable_name !== 'SkattAretsResultat'
        );
      }
      if (sumAretsResultatItem && sumAretsResultatItem.current_amount !== null) {
        sumAretsResultat = Math.round(sumAretsResultatItem.current_amount);
      } else {
        // Try to find any result item as fallback
        const fallbackItem = fileData.data.rr_data?.find((item: any) => 
          item.current_amount !== null && item.current_amount !== 0 && 
          (item.label?.toLowerCase().includes('resultat') || item.id?.includes('RES'))
        );
        if (fallbackItem) {
          sumAretsResultat = Math.round(fallbackItem.current_amount);
        }
      }
      
      // Extract SkattAretsResultat for tax confirmation
      // First try to find exact variable name match
      let skattAretsResultatItem = fileData.data.rr_data.find((item: any) => 
        item.variable_name === 'SkattAretsResultat'
      );
      
      // If not found, try ID match
      if (!skattAretsResultatItem) {
        skattAretsResultatItem = fileData.data.rr_data.find((item: any) => 
          item.id === 'SKATT'
        );
      }
      
      // If still not found, try label match but exclude SumResultatForeSkatt
      if (!skattAretsResultatItem) {
        skattAretsResultatItem = fileData.data.rr_data.find((item: any) => 
          item.label?.toLowerCase().includes('skatt') && 
          item.variable_name !== 'SumResultatForeSkatt' &&
          item.variable_name !== 'SumResultatEfterFinansiellaPoster'
        );
      }
      if (skattAretsResultatItem && skattAretsResultatItem.current_amount !== null) {
        skattAretsResultat = Math.round(skattAretsResultatItem.current_amount);
        // Fix negative zero issue
        if (skattAretsResultat === -0) skattAretsResultat = 0;
      }
    }
    
    // Extract SumFrittEgetKapital from BR data  
    if (fileData.data?.br_data) {
      const sumFrittEgetKapitalItem = fileData.data.br_data.find((item: any) => 
        item.variable_name === 'SumFrittEgetKapital'
      );
      if (sumFrittEgetKapitalItem && sumFrittEgetKapitalItem.current_amount !== null) {
        sumFrittEgetKapital = Math.abs(sumFrittEgetKapitalItem.current_amount);
      }
    }
    
    // Extract calculated tax amounts from INK2 data
    let inkBeraknadSkatt = null;
    let inkBokfordSkatt = null;
    if (fileData.data?.ink2_data) {
      const beraknadItem = fileData.data.ink2_data.find((item: any) => 
        item.variable_name === 'INK_beraknad_skatt'
      );
      if (beraknadItem && beraknadItem.amount !== null) {
        inkBeraknadSkatt = Math.abs(beraknadItem.amount);
      }
      
      const bokfordItem = fileData.data.ink2_data.find((item: any) => 
        item.variable_name === 'INK_bokford_skatt'
      );
      if (bokfordItem && bokfordItem.amount !== null) {
        inkBokfordSkatt = Math.abs(bokfordItem.amount);
      }
    }
    
    // Extract pension tax variables from response
    let pensionPremier = fileData.data?.pension_premier || null;
    let sarskildLoneskattPension = fileData.data?.sarskild_loneskatt_pension || null;
    let sarskildLoneskattPensionCalculated = fileData.data?.sarskild_loneskatt_pension_calculated || null;
    
    // Fallback to legacy extraction if needed
    if (!extractedResults && fileData.data?.accountBalances) {
      const resultAccounts = ['8999', '8910'];
      for (const account of resultAccounts) {
        if (fileData.data.accountBalances[account]) {
          extractedResults = Math.abs(fileData.data.accountBalances[account]).toString();
          break;
        }
      }
    }
    
    // Update company data with all extracted information
    // Priority: SE file org number > scraped org number
    const orgNumber = fileData.data?.company_info?.organization_number || 
                      fileData.data?.scraped_company_data?.orgnr || 
                      '';
    
    onDataUpdate({ 
      seFileData: fileData.data,
      scraped_company_data: fileData.data?.scraped_company_data, // Add scraped company data
      results: extractedResults,
      sumAretsResultat: sumAretsResultat,
      sumFrittEgetKapital: sumFrittEgetKapital,
      skattAretsResultat: skattAretsResultat,
      ink2Data: fileData.data?.ink2_data || [],
      noterData: fileData.data?.noter_data || [],
      fbTable: fileData.data?.fb_table || [],
      fbVariables: fileData.data?.fb_variables || {},
      inkBeraknadSkatt: inkBeraknadSkatt,
      inkBokfordSkatt: inkBokfordSkatt,
      pensionPremier: pensionPremier,
      sarskildLoneskattPension: sarskildLoneskattPension,
      sarskildLoneskattPensionCalculated: sarskildLoneskattPensionCalculated,
      fiscalYear: fileData.data?.company_info?.fiscal_year || new Date().getFullYear(),
      companyName: fileData.data?.company_info?.company_name || fileData.data?.scraped_company_data?.company_name || 'Företag AB',
      organizationNumber: orgNumber,
      showRRBR: true // Show RR and BR data in preview
    });
    
    // Update global state so subsequent steps have access to calculated values
    setGlobalInk2Data(fileData.data?.ink2_data || []);
    setGlobalInkBeraknadSkatt(inkBeraknadSkatt);
    
    setShowFileUpload(false);
    
    // Add the result overview message from database (step 103) - with variable substitution
    try {
      const step103Response = await apiService.getChatFlowStep(103) as ChatFlowResponse;
      const resultText = substituteVariables(
        step103Response.question_text,
        {
          SumAretsResultat: sumAretsResultat ? new Intl.NumberFormat('sv-SE').format(sumAretsResultat) : '0'
        }
      );
      addMessage(resultText, true, step103Response.question_icon, () => {
        // Wait for step 103 message to complete before starting tax flow
        continueTaxFlow();
      });
    } catch (error) {
      console.error('❌ Error fetching step 103:', error);
      const resultText = substituteVariables(
        'Årets resultat är: {SumAretsResultat} kr. Se fullständig resultat- och balans rapport i preview fönstret till höger.',
        {
          SumAretsResultat: sumAretsResultat ? new Intl.NumberFormat('sv-SE').format(sumAretsResultat) : '0'
        }
      );
      addMessage(resultText, true, '💰', () => {
        continueTaxFlow();
      });
    }
    
    const continueTaxFlow = async () => {
      // Add debugging for tax amount
      // Show tax question if we have tax data (including 0)
      if (skattAretsResultat !== null) {
        try {
          const step110Response = await apiService.getChatFlowStep(110) as ChatFlowResponse;
          const taxAmount = new Intl.NumberFormat('sv-SE').format(skattAretsResultat);
          const beraknadSkattAmount = new Intl.NumberFormat('sv-SE').format(inkBeraknadSkatt);
          const taxText = substituteVariables(
            step110Response.question_text,
            {
              SkattAretsResultat: taxAmount,
              inkBeraknadSkatt: beraknadSkattAmount
            }
          );
          addMessage(taxText, true, step110Response.question_icon, () => {
            // Show tax preview
            onDataUpdate({ showTaxPreview: true });
            
            // Auto-scroll to tax module after message is displayed
            setTimeout(() => {
              const taxModule = document.querySelector('[data-section="tax-calculation"]');
              const scrollContainer = document.querySelector('.overflow-auto');
              
              if (taxModule && scrollContainer) {
                const containerRect = scrollContainer.getBoundingClientRect();
                const taxRect = taxModule.getBoundingClientRect();
                // Add 20px padding above INK2 module for better visual spacing
                const scrollTop = scrollContainer.scrollTop + taxRect.top - containerRect.top - 20;
                
                scrollContainer.scrollTo({
                  top: scrollTop,
                  behavior: 'smooth'
                });
              } else {
                console.log('⚠️ Step 110 autoscroll: tax module or scroll container not found');
              }
            }, 500);
            
            // Check if there's a "continue" option that should auto-navigate
            const continueOption = step110Response.options.find((opt: any) => 
              opt.option_value === 'continue' || opt.option_order === 0
            );
            
            if (continueOption && continueOption.next_step) {
              // Prepare temp data with all calculated values to pass to next step
              const tempData = {
                sumAretsResultat,
                skattAretsResultat,
                inkBeraknadSkatt,
                inkBokfordSkatt,
                pensionPremier,
                sarskildLoneskattPension,
                sarskildLoneskattPensionCalculated,
                sumFrittEgetKapital
              };
              
              // Auto-navigate to next step after showing message and scrolling
              // Pass both ink2Data and tempData so variable substitution works
              // Increased delay to allow autoscroll to fully "land" before next message
              setTimeout(() => {
                const ink2DataToPass = fileData.data?.ink2_data || companyData.ink2Data || [];
                loadChatStep(continueOption.next_step, ink2DataToPass, tempData);
              }, 2000); // Wait 2s total (1.5s after autoscroll starts at 500ms)
            } else {
              // No auto-continue, show options for user to select
              setCurrentOptions(step110Response.options);
            }
          });
        } catch (error) {
          console.error('❌ Error fetching step 110:', error);
          const taxAmount = new Intl.NumberFormat('sv-SE').format(skattAretsResultat);
          addMessage(`Den bokförda skatten är ${taxAmount} kr. Låt oss först se över skatteberäkningen tillsammans och se om du vill göra några justeringar.`, true, '🏛️', () => {
            setCurrentOptions([]);
            onDataUpdate({ showTaxPreview: true });
          });
        }
      } else {
        // No tax data found, go directly to dividends
        loadChatStep(501);
      }
    };
  };


  // Initialize chat on mount
  useEffect(() => {
    // Only start if we have basic setup
    const initializeChat = async () => {
      try {
        // Fetch step 101 from database for consistency
        const response = await apiService.getChatFlowStep(101) as ChatFlowResponse;
        addMessage(response.question_text, true, response.question_icon);
        setShowFileUpload(true);
      } catch (error) {
        console.error('❌ Error initializing chat:', error);
        // Fallback to hardcoded message
        addMessage('Välkommen till Raketrapport! Ladda upp din SE-fil så börjar vi analysera din årsredovisning.', true, '👋');
        setShowFileUpload(true);
      }
    };
    
    initializeChat();
  }, []);

  // Auto-scroll when new messages arrive (only for user messages)
  useEffect(() => {
    // Only auto-scroll for user messages or when no FluentMessage is active
    const lastMessage = messages[messages.length - 1];
    if (!lastMessage || !lastMessage.isBot) {
      scrollToBottom();
    }
  }, [messages]);

  // Watch for triggerChatStep requests from components
  useEffect(() => {
    if (companyData.triggerChatStep && companyData.triggerChatStep > 0) {
      // CRITICAL FIX: Always navigate when triggerChatStep is explicitly set
      // The component setting the trigger is responsible for deciding whether to navigate
      // (e.g., handleApproveChanges only sets it on first click)
      loadChatStep(companyData.triggerChatStep);
      // Clear the trigger to prevent repeated navigation
      onDataUpdate({ triggerChatStep: null });
    }
  }, [companyData.triggerChatStep]);

  // Listen for payment success and failure events
  useEffect(() => {
    const onPaymentSuccess = () => {
      loadChatStep(510); // Payment success step
    };
    
    const onPaymentFailure = () => {
      loadChatStep(508); // Payment failure step
    };
    
    window.addEventListener("summare:paymentSuccess", onPaymentSuccess);
    window.addEventListener("summare:paymentFailure", onPaymentFailure);
    
    return () => {
      window.removeEventListener("summare:paymentSuccess", onPaymentSuccess);
      window.removeEventListener("summare:paymentFailure", onPaymentFailure);
    };
  }, []);

  // Handle payment completion URLs (in case of redirect)
  useEffect(() => {
    const handlePaymentCompletionURL = async () => {
      const urlParams = new URLSearchParams(window.location.search);
      const sessionId = urlParams.get('session_id');
      const paymentParam = urlParams.get('payment');
      
      if (sessionId && paymentParam === 'embedded_complete') {
        
        try {
          const response = await fetch(`${import.meta.env.VITE_API_URL || 'https://api.summare.se'}/api/stripe/verify?session_id=${sessionId}`);
          const result = await response.json();
          
          if (result?.paid) {
            loadChatStep(510);
          } else {
            loadChatStep(508);
          }
          
          // Clean up URL without reloading
          window.history.replaceState({}, document.title, window.location.pathname);
        } catch (error) {
          console.error("🔥 Error verifying payment from URL:", error);
          loadChatStep(508); // Default to failure step
        }
      }
    };
    
    handlePaymentCompletionURL();
  }, []);

  // While-typing autoscroll (container-level, works for any typing impl)
  useEffect(() => {
    const container = chatContainerRef.current;
    if (!container) return;

    let rafId: number | null = null;
    let lastScrollHeight = container.scrollHeight;

    const nearBottom = () => {
      const remaining = container.scrollHeight - (container.scrollTop + container.clientHeight);
      return remaining <= NEAR_BOTTOM_PX_DOM;
    };

    const clampToBottom = () => {
      // keep a tiny safety margin so the last line isn't flush with the edge
      const target = Math.max(
        0,
        container.scrollHeight - container.clientHeight - BOTTOM_SAFETY_PX_DOM
      );
      if (container.scrollTop < target) {
        container.scrollTo({ top: target, behavior: 'auto' });
      }
    };

    const schedule = () => {
      if (rafId) return;
      rafId = requestAnimationFrame(() => {
        rafId = null;
        // only auto-follow if user is already near the bottom (avoid hijacking manual scroll)
        if (!nearBottom()) return;

        // scroll only when content actually grew
        if (container.scrollHeight !== lastScrollHeight) {
          lastScrollHeight = container.scrollHeight;
          clampToBottom();
        }
      });
    };

    // Observe text growth while typing (characterData) + added nodes
    const mo = new MutationObserver(() => schedule());
    mo.observe(container, {
      subtree: true,
      childList: true,
      characterData: true,
    });

    // In case fonts/images shift heights slightly after mount
    const ro = new ResizeObserver(() => schedule());
    ro.observe(container);

    // Initial "snap to bottom" if we start near the bottom
    lastScrollHeight = container.scrollHeight;
    if (nearBottom()) clampToBottom();

    return () => {
      mo.disconnect();
      ro.disconnect();
      if (rafId) cancelAnimationFrame(rafId);
    };
  }, []);

  return (
    <div className="flex flex-col h-full">
      {/* Chat Messages */}
      <div 
        ref={chatContainerRef}
        className="flex-1 overflow-y-auto p-4 space-y-4 font-sans pt-20"
        style={{ fontFamily: 'Inter, ui-sans-serif, system-ui, sans-serif' }}
      >
        {messages.map((message) => (
          <div
            key={message.id}
            ref={el => { msgContainersRef.current[message.id] = el; }}
          >
            <ChatMessage
              message={message.text}
              isBot={message.isBot}
              emoji={message.icon}
              onDone={messageCallbacks.current[message.id]}
            />
          </div>
        ))}
        
        {/* Loading indicator - only show when genuinely waiting for user input */}
        {isWaitingForUser && showSpinner && (
          <div className="flex justify-center py-4">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="border-t bg-white p-4">
        {showFileUpload ? (
          <div className="space-y-4">
            <div className="text-center text-gray-600 mb-4">
              <span className="font-semibold">Ladda upp SIE-filer här</span>
            </div>
            <FileUpload onFileProcessed={handleFileProcessed} allowTwoFiles={true} />
          </div>
        ) : showInput ? (
          <div className="flex gap-2">
            <input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleInputSubmit()}
              placeholder={inputPlaceholder}
              className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              autoFocus
            />
            <button
              onClick={handleInputSubmit}
              disabled={!inputValue.trim()}
              className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-md disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Skicka
            </button>
          </div>
        ) : (
          /* Option Buttons */
          <div className="space-y-2">
            {currentOptions.map((option) => (
              <OptionButton
                key={option.option_order}
                onClick={() => handleOptionSelect(option)}
              >
                {option.option_text || ''}
              </OptionButton>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default DatabaseDrivenChat;
