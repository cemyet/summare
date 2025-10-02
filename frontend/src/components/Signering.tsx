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
  'Styrelseledamot',
  'VD',
  'Styrelseordförande', 
  'VD & styrelseledamot',
  'VD & styrelseordförande',
  'Revisor'
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
              UnderskriftAvRevisor: revisorer
            };
            console.log('💾 Updating component data with:', newData);
            updateData(newData);
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

  const handleSendForSigning = async () => {
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
                'Ordinarie styrelseledamöter och eventuell revisor har automatiskt hämtats från Bolagsverket. Förnamn, efternamn, personnummer och roll är förfyllda och låsta. Du kan endast uppdatera e-postadresser och lägga till fler personer vid behov.'
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
                <div className="col-span-3">Email</div>
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
                      className={`h-9 rounded-sm placeholder:text-muted-foreground/40 ${foretradare.fromBolagsverket ? 'bg-muted cursor-not-allowed' : ''}`}
                    />
                  </div>
                  
                  <div className="col-span-2">
                    <Input
                      value={foretradare.UnderskriftHandlingEfternamn}
                      onChange={(e) => updateForetradare(index, 'UnderskriftHandlingEfternamn', e.target.value)}
                      placeholder="Efternamn"
                      disabled={foretradare.fromBolagsverket}
                      className={`h-9 rounded-sm placeholder:text-muted-foreground/40 ${foretradare.fromBolagsverket ? 'bg-muted cursor-not-allowed' : ''}`}
                    />
                  </div>
                  
                  <div className="col-span-2">
                    <Input
                      value={foretradare.UnderskriftHandlingPersonnummer}
                      onChange={(e) => updateForetradare(index, 'UnderskriftHandlingPersonnummer', e.target.value)}
                      placeholder="Personnummer"
                      disabled={foretradare.fromBolagsverket}
                      className={`h-9 rounded-sm placeholder:text-muted-foreground/40 ${foretradare.fromBolagsverket ? 'bg-muted cursor-not-allowed' : ''}`}
                    />
                  </div>
                  
                  <div className="col-span-2">
                    <Select
                      value={foretradare.UnderskriftHandlingRoll}
                      onValueChange={(value) => updateForetradare(index, 'UnderskriftHandlingRoll', value)}
                      disabled={foretradare.fromBolagsverket}
                    >
                      <SelectTrigger className={`h-9 rounded-sm ${foretradare.fromBolagsverket ? 'bg-muted cursor-not-allowed' : ''}`}>
                        <SelectValue placeholder="Välj roll" className="placeholder:text-muted-foreground/40" />
                      </SelectTrigger>
                      <SelectContent>
                        {roleOptions.map((role) => (
                          <SelectItem key={role} value={role}>
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
                      className="h-9 rounded-sm placeholder:text-muted-foreground/40"
                    />
                  </div>
                  
                  <div className="col-span-1 flex gap-1">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={addForetradare}
                      className="h-9 w-9 p-0 rounded-sm"
                    >
                      <Plus className="h-4 w-4" />
                    </Button>
                    {data.UnderskriftForetradare.length > 1 && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => removeForetradare(index)}
                        className="h-9 w-9 p-0 rounded-sm"
                        disabled={foretradare.fromBolagsverket}
                      >
                        <Minus className="h-4 w-4" />
                      </Button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Underskrifter Section */}
          <div>
            <h2 className="text-xl font-semibold mb-4">Underskrifter</h2>
            <p className="text-sm text-muted-foreground mb-6">
              När du kontrollerat att alla befattningshavare är korrekt ifyllda, så kan årsredovisningen skickas till samtliga företrädare 
              för digital signering med BankID. Klicka bara på knappen Skicka nedan så skickas ett mail till alla som ska underteckna 
              med instruktioner om hur de ska skriva under. Du kommer att få ett bekräftelse mail när alla signerat och kan närsomelst 
              också logga in under Mina Sidor för att följa processen och se vilka som har signerat.
            </p>
            
            <Button 
              className="bg-blue-600 hover:bg-blue-700 text-white"
              onClick={handleSendForSigning}
            >
              Skicka
            </Button>
          </div>

          {/* Revisor Section - Optional */}
          {data.UnderskriftAvRevisor.length > 0 && (
            <div>
              <h2 className="text-xl font-semibold mb-4">Revisorspåteckning</h2>
              
              <div className="mb-4">
                <label className="text-sm font-medium">Valt revisionsbolag</label>
                <Input
                  value={data.ValtRevisionsbolag || ''}
                  onChange={(e) => updateData({ ...data, ValtRevisionsbolag: e.target.value })}
                  placeholder="Revisionsbolag"
                  className="mt-1"
                />
              </div>

              <div className="space-y-3">
                <div className="grid grid-cols-12 gap-4 text-sm font-medium text-muted-foreground">
                  <div className="col-span-2">Förnamn</div>
                  <div className="col-span-2">Efternamn</div>
                  <div className="col-span-2">Personnummer</div>
                  <div className="col-span-2">Titel</div>
                  <div className="col-span-1">Huvudans.</div>
                  <div className="col-span-2">Email</div>
                  <div className="col-span-1"></div>
                </div>

                {data.UnderskriftAvRevisor.map((revisor, index) => (
                  <div key={index} className="grid grid-cols-12 gap-4 items-center">
                    <div className="col-span-2">
                      <Input
                        value={revisor.UnderskriftHandlingTilltalsnamn}
                        onChange={(e) => updateRevisor(index, 'UnderskriftHandlingTilltalsnamn', e.target.value)}
                        placeholder="Förnamn"
                        disabled={revisor.fromBolagsverket}
                        className={`h-9 rounded-sm placeholder:text-muted-foreground/40 ${revisor.fromBolagsverket ? 'bg-muted cursor-not-allowed' : ''}`}
                      />
                    </div>
                    
                    <div className="col-span-2">
                      <Input
                        value={revisor.UnderskriftHandlingEfternamn}
                        onChange={(e) => updateRevisor(index, 'UnderskriftHandlingEfternamn', e.target.value)}
                        placeholder="Efternamn"
                        disabled={revisor.fromBolagsverket}
                        className={`h-9 rounded-sm placeholder:text-muted-foreground/40 ${revisor.fromBolagsverket ? 'bg-muted cursor-not-allowed' : ''}`}
                      />
                    </div>
                    
                    <div className="col-span-2">
                      <Input
                        value={revisor.UnderskriftHandlingPersonnummer}
                        onChange={(e) => updateRevisor(index, 'UnderskriftHandlingPersonnummer', e.target.value)}
                        placeholder="Personnummer"
                        disabled={revisor.fromBolagsverket}
                        className={`h-9 rounded-sm placeholder:text-muted-foreground/40 ${revisor.fromBolagsverket ? 'bg-muted cursor-not-allowed' : ''}`}
                      />
                    </div>
                    
                    <div className="col-span-2">
                      <Input
                        value={revisor.UnderskriftHandlingTitel}
                        onChange={(e) => updateRevisor(index, 'UnderskriftHandlingTitel', e.target.value)}
                        placeholder="Titel"
                        disabled={revisor.fromBolagsverket}
                        className={`h-9 rounded-sm placeholder:text-muted-foreground/40 ${revisor.fromBolagsverket ? 'bg-muted cursor-not-allowed' : ''}`}
                      />
                    </div>
                    
                    <div className="col-span-1">
                      <Select
                        value={revisor.UnderskriftRevisorspateckningRevisorHuvudansvarig ? 'true' : 'false'}
                        onValueChange={(value) => updateRevisor(index, 'UnderskriftRevisorspateckningRevisorHuvudansvarig', value === 'true')}
                        disabled={revisor.fromBolagsverket}
                      >
                        <SelectTrigger className={`h-9 rounded-sm ${revisor.fromBolagsverket ? 'bg-muted cursor-not-allowed' : ''}`}>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="true">Ja</SelectItem>
                          <SelectItem value="false">Nej</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    
                    <div className="col-span-2">
                      <Input
                        value={revisor.UnderskriftHandlingEmail}
                        onChange={(e) => updateRevisor(index, 'UnderskriftHandlingEmail', e.target.value)}
                        placeholder="Email"
                        className="h-9 rounded-sm placeholder:text-muted-foreground/40"
                      />
                    </div>
                    
                    <div className="col-span-1 flex gap-1">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => removeRevisor(index)}
                        className="h-9 w-9 p-0 rounded-sm"
                        disabled={revisor.fromBolagsverket}
                      >
                        <Minus className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
              
              <Button
                variant="outline"
                onClick={addRevisor}
                className="mt-4"
              >
                <Plus className="h-4 w-4 mr-2" />
                Lägg till revisor
              </Button>
            </div>
          )}

          {/* Add Revisor Button - if no revisors exist */}
          {data.UnderskriftAvRevisor.length === 0 && (
            <div>
              <Button
                variant="outline"
                onClick={addRevisor}
              >
                <Plus className="h-4 w-4 mr-2" />
                Lägg till revisor
              </Button>
            </div>
          )}

        </CardContent>
      </Card>
    </div>
  );
}
