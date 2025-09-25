import React, { useState, useEffect, useRef } from 'react';
import { apiService } from '@/services/api';
import { ChatMessage } from './ChatMessage';
import { OptionButton } from './OptionButton';
import { FileUpload } from './FileUpload';

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
    // Helper: accepted SLP difference (positive) from ink2Data/companyData
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
        console.log('🔍 Starting handleTaxUpdateForApproval in chat flow...');
        
        // Get current INK2 data
        const currentInk2Data = companyData.ink2Data || [];
        
        console.log('📊 Current INK2 data in chat:', {
          ink2DataLength: currentInk2Data.length
        });
        
        // Debug: Log all variable names in the data
        const variableNames = currentInk2Data.map((item: any) => item.variable_name).filter(Boolean);
        console.log('📋 Available variable names in chat:', variableNames);
        
        // Find INK_beraknad_skatt and INK_bokford_skatt values
        const beraknadSkattItem = currentInk2Data.find((item: any) => item.variable_name === 'INK_beraknad_skatt');
        const bokfordSkattItem = currentInk2Data.find((item: any) => item.variable_name === 'INK_bokford_skatt');
        
        console.log('🔍 Tax items found in chat:', {
          beraknadSkattItem: beraknadSkattItem ? {
            variable_name: beraknadSkattItem.variable_name,
            amount: beraknadSkattItem.amount,
            row_title: beraknadSkattItem.row_title
          } : null,
          bokfordSkattItem: bokfordSkattItem ? {
            variable_name: bokfordSkattItem.variable_name,
            amount: bokfordSkattItem.amount,
            row_title: bokfordSkattItem.row_title
          } : null
        });
        
        if (!beraknadSkattItem || !bokfordSkattItem) {
          console.log('❌ Could not find INK_beraknad_skatt or INK_bokford_skatt items in chat');
          return;
        }

        const inkBeraknadSkatt = beraknadSkattItem.amount || 0;
        const inkBokfordSkatt = bokfordSkattItem.amount || 0;
        
        console.log('💰 Tax comparison in chat:', { inkBeraknadSkatt, inkBokfordSkatt });
        
        // Only proceed if there's a difference
        if (inkBeraknadSkatt === inkBokfordSkatt) {
          console.log('✅ No tax difference in chat, skipping RR/BR updates');
          return;
        }

        const taxDifference = inkBeraknadSkatt - inkBokfordSkatt;
        console.log('🚨 Tax difference detected in chat:', taxDifference);

        // Call API to update RR/BR data
        console.log('🌐 Calling API to update RR/BR data from chat...');
        
        // First test if the endpoint is available
        try {
          const testResponse = await fetch(`${import.meta.env.VITE_API_URL || 'https://api.summare.se'}/api/test-tax-endpoint`);
          console.log('🧪 Test endpoint response:', testResponse.status);
          if (testResponse.ok) {
            const testResult = await testResponse.json();
            console.log('✅ Test endpoint working:', testResult);
          }
        } catch (testError) {
          console.log('❌ Test endpoint failed:', testError);
        }
        
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
        
        console.log('📤 API request data from chat:', {
          inkBeraknadSkatt,
          inkBokfordSkatt,
          taxDifference,
          inkSarskildLoneskatt,
          rr_data_length: requestData.rr_data.length,
          br_data_length: requestData.br_data.length,
          organizationNumber: companyData.organizationNumber,
          fiscalYear: companyData.fiscalYear
        });
        
        const response = await fetch(`${import.meta.env.VITE_API_URL || 'https://api.summare.se'}/api/update-tax-in-financial-data`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(requestData),
        });

        console.log('📥 API response status from chat:', response.status);

        if (!response.ok) {
          const errorText = await response.text();
          console.error('❌ API error response from chat:', errorText);
          
          if (response.status === 404) {
            console.log('⚠️ Tax update endpoint not available yet - deployment in progress');
            // Don't throw error for 404, just log and continue
            return;
          }
          
          throw new Error(`HTTP error! status: ${response.status}, body: ${errorText}`);
        }

        const result = await response.json();
        console.log('✅ API response result from chat:', result);
        
        if (result.success) {
          console.log('🎉 Successfully updated RR/BR data with tax changes from chat');
          console.log('📊 Changes made from chat:', result.changes);
          
          // Update company data with new RR/BR data
          onDataUpdate({
            seFileData: {
              ...companyData.seFileData,
              rr_data: result.rr_data,
              br_data: result.br_data,
            }
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
  const [showInput, setShowInput] = useState(false);
  const [inputValue, setInputValue] = useState('');
  const [inputType, setInputType] = useState('text');
  const [inputPlaceholder, setInputPlaceholder] = useState('');
  const [showFileUpload, setShowFileUpload] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const chatContainerRef = useRef<HTMLDivElement>(null);


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
      sarskild_loneskatt_pension_calculated: context.sarskild_loneskatt_pension_calculated || companyData.sarskildLoneskattPensionCalculated || 0
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
      console.log('🚫 Skipping empty message');
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
    scrollToBottom();

    if (onDone) {
      messageCallbacks.current[message.id] = onDone;
    }
  };

  // Load a chat step
  const loadChatStep = async (stepNumber: number, updatedInk2Data?: any[], tempCompanyData?: any) => {
    try {
      console.log(`🔄 Loading step ${stepNumber}...`);
      
      // Use updated ink2Data if provided, otherwise use global data, otherwise use companyData.ink2Data
      const ink2DataToUse = updatedInk2Data || globalInk2Data || companyData.ink2Data;
      if (ink2DataToUse && ink2DataToUse.length > 0) {
        const inkBeraknadSkattItem = ink2DataToUse.find((item: any) => 
          item.variable_name === 'INK_beraknad_skatt'
        );
      }
      const response = await apiService.getChatFlowStep(stepNumber) as ChatFlowResponse;
      
      if (response.success) {
        setCurrentStep(stepNumber);
        
        // Handle no_option automatically if it exists
        const noOption = response.options.find(opt => opt.option_order === 0);
        if (noOption) {
          console.log('🚀 Auto-executing no_option:', noOption);
          console.log('No option details:', {
            option_value: noOption.option_value,
            next_step: noOption.next_step,
            action_type: noOption.action_type,
            action_data: noOption.action_data
          });
          
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
                console.log('💰 Using most recent inkBeraknadSkatt from INK2 data for message step:', mostRecentInkBeraknadSkatt);
              }
            }
            
            // Substitute variables in question text
            const questionText = substituteVariables(response.question_text, {
              SumAretsResultat: companyData.sumAretsResultat ? new Intl.NumberFormat('sv-SE').format(companyData.sumAretsResultat) : '0',
              SkattAretsResultat: companyData.skattAretsResultat ? new Intl.NumberFormat('sv-SE').format(companyData.skattAretsResultat) : '0',
              pension_premier: companyData.pensionPremier ? new Intl.NumberFormat('sv-SE').format(companyData.pensionPremier) : '0',
              sarskild_loneskatt_pension_calculated: companyData.sarskildLoneskattPensionCalculated ? new Intl.NumberFormat('sv-SE').format(companyData.sarskildLoneskattPensionCalculated) : '0',
              sarskild_loneskatt_pension: companyData.sarskildLoneskattPension ? new Intl.NumberFormat('sv-SE').format(companyData.sarskildLoneskattPension) : '0',
              inkBeraknadSkatt: mostRecentInkBeraknadSkatt ? new Intl.NumberFormat('sv-SE').format(mostRecentInkBeraknadSkatt) : '0',
              inkBokfordSkatt: companyData.inkBokfordSkatt ? new Intl.NumberFormat('sv-SE').format(companyData.inkBokfordSkatt) : '0',
              unusedTaxLossAmount: companyData.unusedTaxLossAmount ? new Intl.NumberFormat('sv-SE').format(companyData.unusedTaxLossAmount) : '0'
            });
            
            // Add the message with onDone callback to wait for animation completion
            addMessage(questionText, true, response.question_icon, async () => {
              // After message is fully revealed, continue with no_option
              await handleOptionSelect(noOption, stepNumber, updatedInk2Data);
            });
            return; // Stop here, handled in callback
          }
          
          // Special handling for step 420: auto-scroll before no_option execution
          if (stepNumber === 420) {
            console.log('🔥 STEP 420 NO_OPTION - Auto-scrolling to Noter before continuing');
            setTimeout(() => {
              const noterModule = document.querySelector('[data-section="noter"]');
              const scrollContainer = document.querySelector('.overflow-auto');
              console.log('🔍 No-option scroll elements found:', {
                noterModule: !!noterModule,
                scrollContainer: !!scrollContainer
              });
              
              if (noterModule && scrollContainer) {
                const containerRect = scrollContainer.getBoundingClientRect();
                const noterRect = noterModule.getBoundingClientRect();
                const scrollTop = scrollContainer.scrollTop + noterRect.top - containerRect.top - 10;
                
                console.log('📍 No-option scroll calculation:', {
                  currentScrollTop: scrollContainer.scrollTop,
                  targetScrollTop: scrollTop
                });
                
                scrollContainer.scrollTo({
                  top: scrollTop,
                  behavior: 'smooth'
                });
              } else {
                console.log('❌ No-option auto-scroll failed: Missing elements');
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
            console.log('💰 Using most recent inkBeraknadSkatt from INK2 data:', mostRecentInkBeraknadSkatt);
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
        
        // Add the question message
        addMessage(questionText, true, response.question_icon);

        // Special handling for manual editing step (402):
        // - Ensure editing is enabled in the preview
        // - Suppress chat options to avoid accidental auto-selection
        // - Scroll the preview into view so inputs are visible
        if (stepNumber === 402) {
          console.log('🔥 STEP 402 TRIGGERED - Calling onDataUpdate with flags');
          onDataUpdate({ taxEditingEnabled: true, editableAmounts: true, showTaxPreview: true });
          console.log('🔥 STEP 402 onDataUpdate called successfully');
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
          console.log('🔥 STEP 420 TRIGGERED - Auto-scrolling to Noter');
          setTimeout(() => {
            const noterModule = document.querySelector('[data-section="noter"]');
            const scrollContainer = document.querySelector('.overflow-auto');
            console.log('🔍 Scroll elements found:', {
              noterModule: !!noterModule,
              scrollContainer: !!scrollContainer,
              noterModuleRect: noterModule?.getBoundingClientRect(),
              scrollContainerRect: scrollContainer?.getBoundingClientRect()
            });
            
            if (noterModule && scrollContainer) {
              const containerRect = scrollContainer.getBoundingClientRect();
              const noterRect = noterModule.getBoundingClientRect();
              const scrollTop = scrollContainer.scrollTop + noterRect.top - containerRect.top - 10;
              
              console.log('📍 Scroll calculation:', {
                currentScrollTop: scrollContainer.scrollTop,
                targetScrollTop: scrollTop,
                noterTop: noterRect.top,
                containerTop: containerRect.top
              });
              
              scrollContainer.scrollTo({
                top: scrollTop,
                behavior: 'smooth'
              });
            } else {
              console.log('❌ Auto-scroll failed: Missing elements');
            }
          }, 500);
        }
        // Auto-scroll to Resultatdisposition section for step 501
        else if (stepNumber === 501) {
          console.log('🔥 STEP 501 TRIGGERED - Auto-scrolling to Resultatdisposition');
          setTimeout(() => {
            const fbModule = document.querySelector('[data-section="forvaltningsberattelse"]');
            const scrollContainer = document.querySelector('.overflow-auto');
            console.log('🔍 Resultatdisposition scroll elements found:', {
              fbModule: !!fbModule,
              scrollContainer: !!scrollContainer
            });
            
            if (fbModule && scrollContainer) {
              // Scroll to bottom of förvaltningsberättelse to show Resultatdisposition
              const containerRect = scrollContainer.getBoundingClientRect();
              const fbRect = fbModule.getBoundingClientRect();
              const fbHeight = fbModule.scrollHeight || fbRect.height;
              const scrollTop = scrollContainer.scrollTop + fbRect.top - containerRect.top + fbHeight - containerRect.height + 50;
              
              console.log('📍 Resultatdisposition scroll calculation:', {
                currentScrollTop: scrollContainer.scrollTop,
                targetScrollTop: scrollTop,
                fbHeight: fbHeight,
                containerHeight: containerRect.height
              });
              
              scrollContainer.scrollTo({
                top: Math.max(0, scrollTop), // Ensure non-negative scroll position
                behavior: 'smooth'
              });
            } else {
              console.log('❌ Resultatdisposition auto-scroll failed: Missing elements');
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
          setCurrentOptions(substitutedOptions);
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
        
        console.log('🔍 Step 201 condition debug:');
        console.log('📊 pension_premier:', pensionPremier);
        console.log('📊 sarskild_loneskatt_pension (booked):', sarskildLoneskattPension);
        console.log('📊 sarskild_loneskatt_pension_calculated:', sarskildLoneskattPensionCalculated);
        
        // Show step 201 if there are pension premiums AND calculated tax > booked tax
        const shouldShow = pensionPremier > 0 && sarskildLoneskattPensionCalculated > sarskildLoneskattPension;
        console.log('💡 Should show step 201?', shouldShow);
        
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
      console.log('🚀 handleOptionSelect called with option:', option.option_value);
      
      // Add user message only if there's actual text
      const optionText = option.option_text || '';
      if (optionText && optionText.trim() !== '') {
        addMessage(optionText, false);
      }

      // Handle special cases first
      // Handle custom tax options to bypass API call
      if (option.option_value === 'approve_tax') {
        // Hide tax preview and go to next step based on SQL or fallback
        console.log('🏛️ APPROVE_TAX clicked - hiding tax preview and navigating to step 420');
        onDataUpdate({ showTaxPreview: false });
        const nextStep = option.next_step || 420; // Use SQL next_step or fallback to 420
        console.log('🚀 APPROVE_TAX will navigate to step:', nextStep);
        setTimeout(() => {
          console.log('🚀 APPROVE_TAX calling loadChatStep with step:', nextStep);
          loadChatStep(nextStep);
        }, 1000);
        return;
      }
      
      // Handle approve_calculated - trigger tax update logic
      if (option.option_value === 'approve_calculated') {
        console.log('🎯 Processing approve_calculated - triggering tax update logic');
        console.log('🎯 About to call handleTaxUpdateForApproval...');
        try {
          await handleTaxUpdateForApproval();
          console.log('🎯 handleTaxUpdateForApproval completed successfully');
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
              console.log('🔍 Step 201 condition evaluation:', shouldShow);
              
              if (shouldShow) {
                loadChatStep(201);
              } else {
                // Skip to step 301 if condition not met
                console.log('⏭️ Skipping step 201, going to 301');
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
          console.log('💰 Using most recent inkBeraknadSkatt from INK2 data for context:', mostRecentInkBeraknadSkatt);
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
      
      console.log('🔍 Processing choice with context:', context);

      const response = await apiService.processChatChoice({
        step_number: explicitStepNumber || currentStep,
        option_value: option.option_value,
        context
      });

      if (response.success) {
        const { action_type, action_data, next_step } = response.result;
        
        console.log('🔍 API Response:', { action_type, action_data, next_step });

        // Process the action
        console.log('🔍 Processing action:', action_type, 'with data:', action_data);
        
        // Special option handling moved to earlier section
        
        switch (action_type) {
          case 'set_variable':
            // Handle variable setting while preserving existing data
            if (action_data?.variable && action_data?.value !== undefined) {
              console.log('🔧 Setting variable:', action_data.variable, 'to:', action_data.value);
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
                
                console.log('💰 Dividend set via option:', {
                  arets_utdelning: dividendAmount,
                  sumFrittEgetKapital: maxDividend,
                  arets_balanseras_nyrakning: balancerasAmount
                });
                
                // Store both values for message substitution
                updateData.arets_balanseras_nyrakning = balancerasAmount;
                
                // Special navigation for dividend with temp data
                if (next_step) {
                  onDataUpdate(updateData);
                  console.log('🚀 Dividend option navigating to step:', next_step);
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
            break;
            
          case 'enable_editing':
            // Enable tax editing mode immediately
            console.log('🔧 ENABLE_EDITING ACTION TRIGGERED - Setting editableAmounts to true');
            onDataUpdate({ taxEditingEnabled: true, editableAmounts: true, showTaxPreview: true });
            console.log('🔧 onDataUpdate called with:', { taxEditingEnabled: true, editableAmounts: true, showTaxPreview: true });
            // Ensure we land on the manual editing step 402
            const targetStep = next_step || 402;
            setTimeout(() => loadChatStep(targetStep), 200);
            return; // Stop further navigation below

          case 'show_input':
            // Prefer explicit navigation to the input step if provided
            if (next_step) {
              console.log('🧭 show_input: navigating to input step', next_step);
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
            
          case 'process_input':
            // Handle input processing
            if (action_data?.variable) {
              // The input value should already be stored in companyData
              // This action type is mainly for navigation
            }
            break;
            
          case 'save_manual_tax':
            // Save manual tax changes
            onDataUpdate({ taxEditingEnabled: false, editableAmounts: false });
            break;
            
          case 'reset_tax_edits':
            // Reset tax editing mode
            onDataUpdate({ taxEditingEnabled: false, editableAmounts: false });
            break;
            
          case 'generate_pdf':
            // Handle PDF generation
            console.log('PDF generation requested');
            break;
            
          case 'complete_session':
            // Handle session completion
            console.log('Session completion requested');
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
        console.log('🔍 General navigation check:', { next_step, action_type });
        if (next_step) {
          console.log('🚀 Navigating to step:', next_step);
          
          // Auto-scroll to noter section for step 420
          if (next_step === 420) {
            console.log('🔥 NAVIGATION TO STEP 420 - Auto-scrolling to Noter');
            setTimeout(() => {
              const noterModule = document.querySelector('[data-section="noter"]');
              const scrollContainer = document.querySelector('.overflow-auto');
              console.log('🔍 Navigation scroll elements found:', {
                noterModule: !!noterModule,
                scrollContainer: !!scrollContainer
              });
              
              if (noterModule && scrollContainer) {
                const containerRect = scrollContainer.getBoundingClientRect();
                const noterRect = noterModule.getBoundingClientRect();
                const scrollTop = scrollContainer.scrollTop + noterRect.top - containerRect.top - 10;
                
                console.log('📍 Navigation scroll calculation:', {
                  currentScrollTop: scrollContainer.scrollTop,
                  targetScrollTop: scrollTop
                });
                
                scrollContainer.scrollTo({
                  top: scrollTop,
                  behavior: 'smooth'
                });
              } else {
                console.log('❌ Navigation auto-scroll failed: Missing elements');
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
                const scrollTop = scrollContainer.scrollTop + fbRect.top - containerRect.top - 10; // 5-7pt padding from top
                
                scrollContainer.scrollTo({
                  top: scrollTop,
                  behavior: 'smooth'
                });
              }
            }, 500);
          }
          
          setTimeout(() => loadChatStep(next_step, updatedInk2Data), 1000);
        } else {
          console.log('❌ No next_step specified');
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
]);

const isHeader = (n?: string) => !!n && /_header$/i.test(n || "");
const isCalculated = (n?: string) =>
  !!n && (CALC_ONLY.has(n) || n === "INK4.1" || n === "INK4.2" || n === "INK4.3a");

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
    const chatManuals = { ...manuals };
    if (companyData.justeringSarskildLoneskatt) {
      chatManuals['justering_sarskild_loneskatt'] = Math.abs(companyData.justeringSarskildLoneskatt);
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
      
      // Return the updated values for immediate use
      return { ink2Data: merged, inkBeraknadSkatt: skatt };
    }
    
    // Return null if no response
    return null;
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
    }
  };

  // Handle input submission
  const handleInputSubmit = async () => {
    if (!inputValue.trim()) return;

    const value = inputType === 'amount' 
      ? parseFloat(inputValue.replace(/\s/g, '').replace(/,/g, '.')) || 0
      : inputValue.trim();
    
    console.log('📤 Input submit - Current step:', currentStep, 'Options:', currentOptions);
    
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
          
          console.log('💾 Storing input value:', {
            variable: submitOption.action_data.variable,
            value: value,
            inputValue: inputValue,
            parsedValue: inputType === 'amount' ? parseFloat(inputValue.replace(/\s/g, '').replace(/,/g, '.')) || 0 : inputValue.trim()
          });

          // Store dividend input and calculate balanseras for substitution
          if (submitOption.action_data.variable === 'arets_utdelning' && inputType === 'amount') {
            // Use absolute value only after validation passes
            const dividendAmount = Math.abs(value as number);
            const maxDividend = companyData.sumFrittEgetKapital || 0;
            const balancerasAmount = maxDividend - dividendAmount;
            
            console.log('💰 Dividend calculation:', {
              sumFrittEgetKapital: maxDividend,
              arets_utdelning: dividendAmount,
              balanseras_amount: balancerasAmount
            });
            
            // Store only dividend amount (positive)
            onDataUpdate({ arets_utdelning: dividendAmount });
            
            // Special handling for dividend: pass temp data for immediate substitution
            if (submitOption.next_step) {
              console.log('🚀 Navigating to dividend next step:', submitOption.next_step);
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
      console.log('🔍 Navigation check:', {
        hasNextStep: !!submitOption.next_step,
        nextStep: submitOption.next_step,
        variable: submitOption.action_data?.variable,
        willNavigate: submitOption.next_step && submitOption.action_data?.variable !== 'sarskildLoneskattCustom'
      });
      
      if (submitOption.next_step && 
          submitOption.action_data?.variable !== 'sarskildLoneskattCustom') {
        console.log('🚀 Navigating to step:', submitOption.next_step);
        setShowInput(false);
        setInputValue('');
        setTimeout(() => loadChatStep(submitOption.next_step!), 500);
      } else {
        console.log('❌ Navigation blocked or no next step');
      }
    }
  };

  // Handle file upload
  const handleFileProcessed = async (fileData: any) => {
    console.log('📁 File processed:', fileData);
    
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
        console.log('📊 Found SumAretsResultat:', sumAretsResultat, 'from item:', sumAretsResultatItem);
      } else {
        console.log('❌ Could not find SumAretsResultat in RR or BR data');
        console.log('RR data keys:', fileData.data.rr_data?.map((item: any) => ({ id: item.id, variable_name: item.variable_name, label: item.label, current_amount: item.current_amount })));
        
        // Try to find any result item as fallback
        const fallbackItem = fileData.data.rr_data?.find((item: any) => 
          item.current_amount !== null && item.current_amount !== 0 && 
          (item.label?.toLowerCase().includes('resultat') || item.id?.includes('RES'))
        );
        if (fallbackItem) {
          sumAretsResultat = Math.round(fallbackItem.current_amount);
          console.log('📊 Using fallback SumAretsResultat:', sumAretsResultat, 'from item:', fallbackItem);
        }
      }
      
      // Extract SkattAretsResultat for tax confirmation
      console.log('🔍 Searching for SkattAretsResultat in RR data...');
      console.log('🔍 Available RR items:', fileData.data.rr_data.map((item: any) => ({
        variable_name: item.variable_name,
        id: item.id,
        label: item.label,
        current_amount: item.current_amount
      })));
      
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
        console.log('💰 Found SkattAretsResultat:', skattAretsResultat, 'from item:', skattAretsResultatItem);
      } else {
        console.log('❌ Could not find SkattAretsResultat in RR data');
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
      companyName: fileData.data?.company_info?.company_name || 'Företag AB',
      showRRBR: true // Show RR and BR data in preview
    });
    
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
      console.log('🏛️ Tax amount for step 104:', skattAretsResultat);
      console.log('📊 Annual result for step 103:', sumAretsResultat);
      // Show tax question if we have tax data (including 0)
      if (skattAretsResultat !== null) {
        try {
          const step104Response = await apiService.getChatFlowStep(104) as ChatFlowResponse;
          const taxAmount = new Intl.NumberFormat('sv-SE').format(skattAretsResultat);
          const taxText = substituteVariables(
            step104Response.question_text,
            {
              SkattAretsResultat: taxAmount
            }
          );
          addMessage(taxText, true, step104Response.question_icon, () => {
            // Set options after tax message completes
            setCurrentOptions(step104Response.options);
            onDataUpdate({ showTaxPreview: true });
          });
        } catch (error) {
          console.error('❌ Error fetching step 104:', error);
          const taxAmount = new Intl.NumberFormat('sv-SE').format(skattAretsResultat);
          addMessage(`Den bokförda skatten är ${taxAmount} kr. Vill du godkänna den eller vill du se över de skattemässiga justeringarna?`, true, '🏛️', () => {
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
    console.log('🚀 DatabaseDrivenChat initializing...');
    console.log('CompanyData:', companyData);
    
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

  // Auto-scroll when new messages arrive
  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Watch for triggerChatStep requests from components
  useEffect(() => {
    if (companyData.triggerChatStep && companyData.triggerChatStep > 0) {
      console.log('🎯 Triggering navigation to step:', companyData.triggerChatStep);
      loadChatStep(companyData.triggerChatStep);
      // Clear the trigger to prevent repeated navigation
      onDataUpdate({ triggerChatStep: null });
    }
  }, [companyData.triggerChatStep]);

  return (
    <div className="flex flex-col h-full">
      {/* Chat Messages */}
      <div 
        ref={chatContainerRef}
        className="flex-1 overflow-y-auto p-4 space-y-4 font-sans pt-20"
        style={{ fontFamily: 'Inter, ui-sans-serif, system-ui, sans-serif' }}
      >
        {messages.map((message) => (
          <ChatMessage
            key={message.id}
            message={message.text}
            isBot={message.isBot}
            emoji={message.icon}
            onDone={messageCallbacks.current[message.id]}
          />
        ))}
        
        {/* Loading indicator */}
        {isLoading && (
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
