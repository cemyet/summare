import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Plus, Minus, Download } from 'lucide-react';

// Types based on CSV variable mapping
interface UnderskriftForetradare {
  UnderskriftHandlingTilltalsnamn: string;
  UnderskriftHandlingEfternamn: string;
  UnderskriftHandlingPersonnummer: string;
  UnderskriftHandlingEmail: string;
  UnderskriftHandlingRoll: string;
  UnderskriftArsredovisningForetradareAvvikandemening?: string;
  UndertecknandeDatum?: string;
  fromBolagsverket?: boolean; // Flag to mark prefilled data
}

interface UnderskriftAvRevisor {
  UnderskriftHandlingTilltalsnamn: string;
  UnderskriftHandlingEfternamn: string;
  UnderskriftHandlingPersonnummer: string;
  UnderskriftHandlingEmail: string;
  UnderskriftHandlingTitel: string;
  UnderskriftRevisorspateckningRevisorHuvudansvarig: boolean;
  RevisionsberattelseTyp?: string;
  RevisionsberattelseDatum?: string;
  fromBolagsverket?: boolean; // Flag to mark prefilled data
}

interface SigneringData {
  // Företrädare tuple array
  UnderskriftForetradare: UnderskriftForetradare[];
  
  // Revisor data
  ValtRevisionsbolag?: string;
  UnderskriftAvRevisor: UnderskriftAvRevisor[];
  
  // Signing date for annual report
  UndertecknandeArsredovisningDatum?: string;
}

interface SigneringProps {
  signeringData?: SigneringData;
  onDataUpdate: (updates: any) => void;
  companyData?: any;
}

const roleOptions = [
  'VD',
  'VD & styrelseledamot',
  'VD & styrelseordförande',
  'Styrelseordförande',
  'Styrelseledamot'
];

export function Signering({ signeringData, onDataUpdate, companyData }: SigneringProps) {
  const [data, setData] = useState<SigneringData>(signeringData || {
    UnderskriftForetradare: [
      {
        UnderskriftHandlingTilltalsnamn: '',
        UnderskriftHandlingEfternamn: '',
        UnderskriftHandlingPersonnummer: '',
        UnderskriftHandlingEmail: '',
        UnderskriftHandlingRoll: '',
      },
      {
        UnderskriftHandlingTilltalsnamn: '',
        UnderskriftHandlingEfternamn: '',
        UnderskriftHandlingPersonnummer: '',
        UnderskriftHandlingEmail: '',
        UnderskriftHandlingRoll: '',
      }
    ],
    UnderskriftAvRevisor: []
  });

  const [loading, setLoading] = useState(false);
  const [hasPrefilledData, setHasPrefilledData] = useState(false);
  const [showValidationMessage, setShowValidationMessage] = useState(false);
  const [validationErrors, setValidationErrors] = useState<string[]>([]);
  const [originalData, setOriginalData] = useState<SigneringData | null>(null);

  const updateData = (newData: SigneringData) => {
    setData(newData);
    onDataUpdate({ signeringData: newData });
  };

  // Fetch officers from Bolagsverket on component mount
  useEffect(() => {
    const fetchOfficers = async () => {
      console.log('🔍 Signering: Checking if should fetch from Bolagsverket...', {
        orgNumber: companyData?.organizationNumber,
        hasPrefilledData,
        companyData
      });

      if (!companyData?.organizationNumber || hasPrefilledData) {
        console.log('⏭️ Skipping Bolagsverket fetch:', {
          noOrgNumber: !companyData?.organizationNumber,
          alreadyPrefilled: hasPrefilledData
        });
        return;
      }

      console.log('📥 Fetching officers from Bolagsverket for:', companyData.organizationNumber);
      setLoading(true);
      
      try {
        // ✅ Robust API base detection (prod > dev), always prefer HTTPS in browser
        const envBase =
          (typeof window !== 'undefined' && (import.meta.env?.VITE_API_URL || (process as any)?.env?.NEXT_PUBLIC_API_BASE)) ||
          'https://api.summare.se';
        const API_BASE = envBase.replace(/^http:\/\/(.*)$/i, 'https://$1'); // force https if someone put http

        // ✅ Normalisera orgnr: backend brukar föredra siffror utan bindestreck
        const normalizedOrg = String(companyData.organizationNumber).replace(/\D/g, '');
        const url = `${API_BASE}/api/bolagsverket/officers/${normalizedOrg}`;
        console.log('🌐 API URL:', url);

        const response = await fetch(url, { credentials: 'omit' });
        
        console.log('📡 Response status:', response.status);
        
        if (!response.ok) {
          console.error('❌ Failed to fetch officers from Bolagsverket:', response.status, response.statusText);
          return;
        }

        const result = await response.json();
        console.log('✅ Bolagsverket response:', result);
        
        if (result.success && result.officers) {
          const officers = result.officers;
          console.log('👥 Officers found:', {
            företrädare: officers.UnderskriftForetradare.length,
            revisorer: officers.UnderskriftAvRevisor.length
          });
          
          // Mark all fetched data as from Bolagsverket
          const företrädare = officers.UnderskriftForetradare.map((o: any) => ({
            ...o,
            fromBolagsverket: true
          }));
          
          const revisorer = officers.UnderskriftAvRevisor.map((r: any) => ({
            ...r,
            fromBolagsverket: true
          }));

          console.log('📋 Formatted data:', { företrädare, revisorer });

          // If we have officers, prefill the data
          if (företrädare.length > 0) {
            const newData = {
              ...data,
              UnderskriftForetradare: företrädare,
              UnderskriftAvRevisor: revisorer,
              ValtRevisionsbolag: officers.ValtRevisionsbolag || data.ValtRevisionsbolag || ''
            };
            console.log('💾 Updating component data with:', newData);
            updateData(newData);
            setOriginalData(newData); // Save original state for Ångra button
            setHasPrefilledData(true);
          } else {
            console.log('⚠️ No företrädare found, keeping default rows');
          }
        } else {
          console.log('⚠️ Response not successful or no officers:', result);
        }
      } catch (error) {
        console.error('💥 Error fetching officers from Bolagsverket:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchOfficers();
  }, [companyData?.organizationNumber]);

  const addForetradare = () => {
    const newData = {
      ...data,
      UnderskriftForetradare: [
        ...data.UnderskriftForetradare,
        {
          UnderskriftHandlingTilltalsnamn: '',
          UnderskriftHandlingEfternamn: '',
          UnderskriftHandlingPersonnummer: '',
          UnderskriftHandlingEmail: '',
          UnderskriftHandlingRoll: '',
          fromBolagsverket: false, // Manually added rows are editable
        }
      ]
    };
    updateData(newData);
  };

  const removeForetradare = (index: number) => {
    if (data.UnderskriftForetradare.length > 1) {
      const newData = {
        ...data,
        UnderskriftForetradare: data.UnderskriftForetradare.filter((_, i) => i !== index)
      };
      updateData(newData);
    }
  };

  const updateForetradare = (index: number, field: keyof UnderskriftForetradare, value: string) => {
    const newData = {
      ...data,
      UnderskriftForetradare: data.UnderskriftForetradare.map((item, i) => 
        i === index ? { ...item, [field]: value } : item
      )
    };
    updateData(newData);
  };

  const addRevisor = () => {
    const newData = {
      ...data,
      UnderskriftAvRevisor: [
        ...data.UnderskriftAvRevisor,
        {
          UnderskriftHandlingTilltalsnamn: '',
          UnderskriftHandlingEfternamn: '',
          UnderskriftHandlingPersonnummer: '',
          UnderskriftHandlingEmail: '',
          UnderskriftHandlingTitel: '',
          UnderskriftRevisorspateckningRevisorHuvudansvarig: false,
          fromBolagsverket: false, // Manually added rows are editable
        }
      ]
    };
    updateData(newData);
  };

  const removeRevisor = (index: number) => {
    const newData = {
      ...data,
      UnderskriftAvRevisor: data.UnderskriftAvRevisor.filter((_, i) => i !== index)
    };
    updateData(newData);
  };

  const updateRevisor = (index: number, field: keyof UnderskriftAvRevisor, value: string | boolean) => {
    const newData = {
      ...data,
      UnderskriftAvRevisor: data.UnderskriftAvRevisor.map((item, i) => 
        i === index ? { ...item, [field]: value } : item
      )
    };
    updateData(newData);
  };

  const handleUndoChanges = () => {
    if (originalData) {
      setData(originalData);
      onDataUpdate({ signeringData: originalData });
      console.log('↩️ Restored original data from Bolagsverket');
    }
  };

  const validateEmails = (): boolean => {
    const errors: string[] = [];
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

    // Validate företrädare emails
    data.UnderskriftForetradare.forEach((foretradare) => {
      const email = foretradare.UnderskriftHandlingEmail?.trim();
      const fullName = `${foretradare.UnderskriftHandlingTilltalsnamn} ${foretradare.UnderskriftHandlingEfternamn}`.trim();
      
      if (!email) {
        errors.push(`Email saknas för ${fullName}. Vänligen kontrollera och försök igen.`);
      } else if (!emailRegex.test(email)) {
        errors.push(`Ogiltig emailadress för ${fullName}. Vänligen kontrollera och försök igen.`);
      }
    });

    // Validate revisor emails
    data.UnderskriftAvRevisor.forEach((revisor) => {
      const email = revisor.UnderskriftHandlingEmail?.trim();
      const fullName = `${revisor.UnderskriftHandlingTilltalsnamn} ${revisor.UnderskriftHandlingEfternamn}`.trim();
      
      if (!email) {
        errors.push(`Email saknas för ${fullName}. Vänligen kontrollera och försök igen.`);
      } else if (!emailRegex.test(email)) {
        errors.push(`Ogiltig emailadress för ${fullName}. Vänligen kontrollera och försök igen.`);
      }
    });

    if (errors.length > 0) {
      setValidationErrors(errors);
      setShowValidationMessage(true);
      
      // Auto-hide after 6 seconds
      setTimeout(() => {
        setShowValidationMessage(false);
      }, 6000);
      
      return false;
    }
    
    return true;
  };

  const handleSendForSigning = async () => {
    // Validate emails before sending
    if (!validateEmails()) {
      return;
    }

    try {
      console.log('🖊️ Sending for digital signing...', data);
      
      const response = await fetch(`${import.meta.env.VITE_API_URL || 'https://api.summare.se'}/api/send-for-digital-signing`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          signeringData: data,
          organizationNumber: companyData?.organizationNumber
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const result = await response.json();
      
      if (result.success) {
        console.log('✅ Signing invitations sent successfully:', result);
        // You could show a success message or navigate to next step here
        alert('Signering-invitationer har skickats! Du kommer att få bekräftelse via e-post när alla har signerat.');
      } else {
        throw new Error(result.message || 'Failed to send signing invitations');
      }
    } catch (error) {
      console.error('❌ Error sending for signing:', error);
      alert('Ett fel uppstod när signeringsinvitationerna skulle skickas. Försök igen.');
    }
  };

  return (
    <div data-section="signering" className="space-y-8">
      <Card>
        <CardHeader>
          <CardTitle className="text-2xl font-bold">Signering</CardTitle>
        </CardHeader>
        <CardContent className="space-y-8">
          
          {/* Befattningshavare Section */}
          <div>
            <h2 className="text-xl font-semibold mb-4">Befattningshavare</h2>
            <p className="text-sm text-muted-foreground mb-6">
              {loading ? (
                'Hämtar företagsinformation från Bolagsverket...'
              ) : hasPrefilledData ? (
                'VD, styrelseledamöter och eventuell revisor har hämtats från Bolagsverket. Förnamn, efternamn, personnummer och roll är redan ifyllda och låsta. Du ska bara uppdatera emailadresser och kan lägga till fler befattningshavare om det skulle behövas.'
              ) : (
                'Fyll i information om befattningshavare som ska signera årsredovisningen. Du kan lägga till eller ta bort rader vid behov.'
              )}
            </p>
            
            <div className="space-y-3">
              <div className="grid grid-cols-12 gap-4 text-sm font-medium text-muted-foreground">
                <div className="col-span-2">Förnamn</div>
                <div className="col-span-2">Efternamn</div>
                <div className="col-span-2">Personnummer</div>
                <div className="col-span-2">Roll</div>
                <div className="col-span-3 ml-4">Email</div>
                <div className="col-span-1"></div>
              </div>

              {data.UnderskriftForetradare.map((foretradare, index) => (
                <div key={index} className="grid grid-cols-12 gap-4 items-center">
                  <div className="col-span-2">
                    <Input
                      value={foretradare.UnderskriftHandlingTilltalsnamn}
                      onChange={(e) => updateForetradare(index, 'UnderskriftHandlingTilltalsnamn', e.target.value)}
                      placeholder="Förnamn"
                      disabled={foretradare.fromBolagsverket}
                      className={`h-9 rounded-sm placeholder:text-muted-foreground/40 ${foretradare.fromBolagsverket ? 'bg-muted cursor-not-allowed opacity-90' : ''}`}
                    />
                  </div>
                  
                  <div className="col-span-2">
                    <Input
                      value={foretradare.UnderskriftHandlingEfternamn}
                      onChange={(e) => updateForetradare(index, 'UnderskriftHandlingEfternamn', e.target.value)}
                      placeholder="Efternamn"
                      disabled={foretradare.fromBolagsverket}
                      className={`h-9 rounded-sm placeholder:text-muted-foreground/40 ${foretradare.fromBolagsverket ? 'bg-muted cursor-not-allowed opacity-90' : ''}`}
                    />
                  </div>
                  
                  <div className="col-span-2">
                    <Input
                      value={foretradare.UnderskriftHandlingPersonnummer}
                      onChange={(e) => updateForetradare(index, 'UnderskriftHandlingPersonnummer', e.target.value)}
                      placeholder="Personnummer"
                      disabled={foretradare.fromBolagsverket}
                      className={`h-9 rounded-sm placeholder:text-muted-foreground/40 ${foretradare.fromBolagsverket ? 'bg-muted cursor-not-allowed opacity-90' : ''}`}
                    />
                  </div>
                  
                  <div className="col-span-2">
                    <Select
                      value={foretradare.UnderskriftHandlingRoll}
                      onValueChange={(value) => updateForetradare(index, 'UnderskriftHandlingRoll', value)}
                      disabled={foretradare.fromBolagsverket}
                    >
                      <SelectTrigger className={`h-9 rounded-sm w-[110%] text-left [&>span]:text-left [&>span]:overflow-hidden [&>span]:whitespace-nowrap ${foretradare.fromBolagsverket ? 'bg-muted cursor-not-allowed opacity-90' : ''}`}>
                        <SelectValue placeholder="Välj roll" className="text-muted-foreground/40" />
                      </SelectTrigger>
                      <SelectContent className="p-1">
                        {roleOptions.map((role) => (
                          <SelectItem key={role} value={role} className="pl-2 pr-2">
                            {role}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  
                  <div className="col-span-3">
                    <Input
                      value={foretradare.UnderskriftHandlingEmail}
                      onChange={(e) => updateForetradare(index, 'UnderskriftHandlingEmail', e.target.value)}
                      placeholder="Email" 
                      className="h-9 rounded-sm placeholder:text-muted-foreground/40 ml-4 w-[calc(100%-1rem)]"
                    />
                  </div>
                  
                  <div className="col-span-1 flex gap-1">
                    {index === data.UnderskriftForetradare.length - 1 && (
                      <>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={addForetradare}
                          className="h-9 w-9 p-0 rounded-sm"
                        >
                          <Plus className="h-4 w-4" />
                        </Button>
                        {data.UnderskriftForetradare.length > 1 && !foretradare.fromBolagsverket && (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => removeForetradare(index)}
                            className="h-9 w-9 p-0 rounded-sm"
                          >
                            <Minus className="h-4 w-4" />
                          </Button>
                        )}
                      </>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Revisor Section */}
          <div>
            <h2 className="text-xl font-semibold mb-4">Revisor</h2>

            <div className="space-y-3">
              <div className="grid grid-cols-12 gap-4 text-sm font-medium text-muted-foreground">
                <div className="col-span-2">Förnamn</div>
                <div className="col-span-2">Efternamn</div>
                <div className="col-span-2">Personnummer</div>
                <div className="col-span-2">Revisionsbolag</div>
                <div className="col-span-3 ml-4">Email</div>
                <div className="col-span-1"></div>
              </div>

              {data.UnderskriftAvRevisor.length === 0 ? (
                <div className="grid grid-cols-12 gap-4 items-start">
                  <div className="col-span-2">
                    <Input
                      value=""
                      onChange={(e) => {
                        const newRevisor = {
                          UnderskriftHandlingTilltalsnamn: e.target.value,
                          UnderskriftHandlingEfternamn: '',
                          UnderskriftHandlingPersonnummer: '',
                          UnderskriftHandlingEmail: '',
                          UnderskriftHandlingTitel: '',
                          UnderskriftRevisorspateckningRevisorHuvudansvarig: false,
                          fromBolagsverket: false
                        };
                        updateData({
                          ...data,
                          UnderskriftAvRevisor: [newRevisor]
                        });
                      }}
                      placeholder="Förnamn"
                      className="h-9 rounded-sm placeholder:text-muted-foreground/40"
                    />
                  </div>
                  
                  <div className="col-span-2">
                    <Input
                      value=""
                      placeholder="Efternamn"
                      className="h-9 rounded-sm placeholder:text-muted-foreground/40"
                      disabled
                    />
                  </div>
                  
                  <div className="col-span-2">
                    <Input
                      value=""
                      placeholder="Personnummer"
                      className="h-9 rounded-sm placeholder:text-muted-foreground/40"
                      disabled
                    />
                  </div>
                  
                  <div className="col-span-2">
                    <Input
                      value=""
                      placeholder="Revisionsbolag"
                      className="h-9 rounded-sm placeholder:text-muted-foreground/40 w-[110%]"
                      disabled
                    />
                  </div>
                  
                  <div className="col-span-3">
                    <Input
                      value=""
                      placeholder="Email"
                      className="h-9 rounded-sm placeholder:text-muted-foreground/40 ml-4 w-[calc(100%-1rem)]"
                      disabled
                    />
                  </div>
                  
                  <div className="col-span-1 flex gap-1">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={addRevisor}
                      className="h-9 w-9 p-0 rounded-sm"
                    >
                      <Plus className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ) : (
                data.UnderskriftAvRevisor.map((revisor, index) => (
                  <div key={index} className="grid grid-cols-12 gap-4 items-start">
                    <div className="col-span-2">
                      <Input
                        value={revisor.UnderskriftHandlingTilltalsnamn}
                        onChange={(e) => updateRevisor(index, 'UnderskriftHandlingTilltalsnamn', e.target.value)}
                        placeholder="Förnamn"
                        disabled={revisor.fromBolagsverket}
                        className={`h-9 rounded-sm placeholder:text-muted-foreground/40 ${revisor.fromBolagsverket ? 'bg-muted cursor-not-allowed opacity-90' : ''}`}
                      />
                    </div>
                    
                    <div className="col-span-2">
                      <Input
                        value={revisor.UnderskriftHandlingEfternamn}
                        onChange={(e) => updateRevisor(index, 'UnderskriftHandlingEfternamn', e.target.value)}
                        placeholder="Efternamn"
                        disabled={revisor.fromBolagsverket}
                        className={`h-9 rounded-sm placeholder:text-muted-foreground/40 ${revisor.fromBolagsverket ? 'bg-muted cursor-not-allowed opacity-90' : ''}`}
                      />
                    </div>
                    
                    <div className="col-span-2">
                      <Input
                        value={revisor.UnderskriftHandlingPersonnummer}
                        onChange={(e) => updateRevisor(index, 'UnderskriftHandlingPersonnummer', e.target.value)}
                        placeholder="Personnummer"
                        disabled={revisor.fromBolagsverket}
                        className={`h-9 rounded-sm placeholder:text-muted-foreground/40 ${revisor.fromBolagsverket ? 'bg-muted cursor-not-allowed opacity-90' : ''}`}
                      />
                    </div>
                    
                    <div className="col-span-2">
                      <Input
                        value={revisor.UnderskriftHandlingTitel}
                        onChange={(e) => updateRevisor(index, 'UnderskriftHandlingTitel', e.target.value)}
                        placeholder="Revisionsbolag"
                        disabled={revisor.fromBolagsverket}
                        className={`h-9 rounded-sm placeholder:text-muted-foreground/40 w-[110%] ${revisor.fromBolagsverket ? 'bg-muted cursor-not-allowed opacity-90' : ''}`}
                      />
                    </div>
                    
                    <div className="col-span-3">
                      <Input
                        value={revisor.UnderskriftHandlingEmail}
                        onChange={(e) => updateRevisor(index, 'UnderskriftHandlingEmail', e.target.value)}
                        placeholder="Email"
                        className="h-9 rounded-sm placeholder:text-muted-foreground/40 ml-4 w-[calc(100%-1rem)]"
                      />
                    </div>
                    
                    <div className="col-span-1 flex gap-1">
                      {index === data.UnderskriftAvRevisor.length - 1 && (
                        <>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={addRevisor}
                            className="h-9 w-9 p-0 rounded-sm"
                          >
                            <Plus className="h-4 w-4" />
                          </Button>
                          {data.UnderskriftAvRevisor.length > 1 && !revisor.fromBolagsverket && (
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => removeRevisor(index)}
                              className="h-9 w-9 p-0 rounded-sm"
                            >
                              <Minus className="h-4 w-4" />
                            </Button>
                          )}
                        </>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Underskrifter Section */}
          <div>
            <h2 className="text-xl font-semibold mb-4">Underskrifter</h2>
            <p className="text-sm text-muted-foreground mb-6">
              När du har fyllt i emailadresserna kan årsredovisningen skickas till samtliga företrädare för digital signering med BankID. Klicka på knappen Skicka när du är klar, så skickas ett mail till alla som ska skriva under med instruktioner om hur de ska göra. Du kommer att få en bekräftelse på mail när alla signerat och kan också logga in under Mina Sidor för att följa processen och se vilka som har signerat.
            </p>
            
            <div className="flex justify-between items-center gap-4">
              {originalData && (
                <Button 
                  variant="outline"
                  onClick={handleUndoChanges}
                  className="flex items-center gap-2"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M3 7v6h6"/>
                    <path d="M21 17a9 9 0 0 0-9-9 9 9 0 0 0-6 2.3L3 13"/>
                  </svg>
                  Ångra ändringar
                </Button>
              )}
              <Button 
                className="bg-blue-600 hover:bg-blue-700 text-white flex items-center gap-2 ml-auto"
                onClick={handleSendForSigning}
              >
                Skicka
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 10h-10a8 8 0 00-8 8v2M21 10l-6 6m6-6l-6-6"/>
                </svg>
              </Button>
            </div>
          </div>

        </CardContent>
      </Card>

      {/* Email Validation Toast Notification */}
      {showValidationMessage && (
        <div className="fixed bottom-4 right-4 z-50 bg-white rounded-lg shadow-lg p-4 max-w-sm animate-in slide-in-from-bottom-2">
          <div className="flex items-start">
            <div className="flex-shrink-0">
              <svg className="h-6 w-6 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>
            <div className="ml-3 flex-1">
              <p className="text-sm font-medium text-gray-900">
                Ogiltiga email-adresser
              </p>
              <div className="mt-2 text-sm text-gray-700 space-y-1">
                {validationErrors.map((error, index) => (
                  <p key={index}>{error}</p>
                ))}
              </div>
            </div>
            <div className="ml-4 flex-shrink-0 flex">
              <button
                className="inline-flex text-gray-400 hover:text-gray-500"
                onClick={() => setShowValidationMessage(false)}
              >
                <span className="sr-only">Stäng</span>
                <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
                </svg>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
