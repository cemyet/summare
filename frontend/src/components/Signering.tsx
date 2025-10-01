import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Plus, Minus } from 'lucide-react';

// Types based on CSV variable mapping
interface UnderskriftForetradare {
  UnderskriftHandlingTilltalsnamn: string;
  UnderskriftHandlingEfternamn: string;
  UnderskriftHandlingRoll: string;
  UnderskriftArsredovisningForetradareAvvikandemening?: string;
  UndertecknandeDatum?: string;
}

interface UnderskriftAvRevisor {
  UnderskriftHandlingTilltalsnamn: string;
  UnderskriftHandlingEfternamn: string;
  UnderskriftHandlingTitel: string;
  UnderskriftRevisorspateckningRevisorHuvudansvarig: boolean;
  RevisionsberattelseTyp?: string;
  RevisionsberattelseDatum?: string;
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
  onDataUpdate: (data: SigneringData) => void;
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
        UnderskriftHandlingRoll: '',
      },
      {
        UnderskriftHandlingTilltalsnamn: '',
        UnderskriftHandlingEfternamn: '',
        UnderskriftHandlingRoll: '',
      }
    ],
    UnderskriftAvRevisor: []
  });

  const updateData = (newData: SigneringData) => {
    setData(newData);
    onDataUpdate({ signeringData: newData });
  };

  const addForetradare = () => {
    const newData = {
      ...data,
      UnderskriftForetradare: [
        ...data.UnderskriftForetradare,
        {
          UnderskriftHandlingTilltalsnamn: '',
          UnderskriftHandlingEfternamn: '',
          UnderskriftHandlingRoll: '',
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
          UnderskriftHandlingTitel: '',
          UnderskriftRevisorspateckningRevisorHuvudansvarig: false,
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
              Ordinarie styrelseledamöter och eventuell revisor har automatiskt hämtats från Bolagsverket. Du kan lägga till
            </p>
            
            <div className="space-y-4">
              <div className="grid grid-cols-12 gap-4 text-sm font-medium text-muted-foreground">
                <div className="col-span-2">Förnamn</div>
                <div className="col-span-2">Efternamn</div>
                <div className="col-span-2">Personnummer</div>
                <div className="col-span-3">Roll</div>
                <div className="col-span-2">Email</div>
                <div className="col-span-1">Åtgärder</div>
              </div>

              {data.UnderskriftForetradare.map((foretradare, index) => (
                <div key={index} className="grid grid-cols-12 gap-4 items-center">
                  <div className="col-span-2">
                    <span className="text-xs text-muted-foreground">Företrädare {index + 1}</span>
                    <Input
                      value={foretradare.UnderskriftHandlingTilltalsnamn}
                      onChange={(e) => updateForetradare(index, 'UnderskriftHandlingTilltalsnamn', e.target.value)}
                      placeholder="Förnamn"
                    />
                  </div>
                  
                  <div className="col-span-2">
                    <Input
                      value={foretradare.UnderskriftHandlingEfternamn}
                      onChange={(e) => updateForetradare(index, 'UnderskriftHandlingEfternamn', e.target.value)}
                      placeholder="Efternamn"
                    />
                  </div>
                  
                  <div className="col-span-2">
                    <Input
                      placeholder="Personnummer"
                      // This would map to a separate field in the actual implementation
                    />
                  </div>
                  
                  <div className="col-span-3">
                    <Select
                      value={foretradare.UnderskriftHandlingRoll}
                      onValueChange={(value) => updateForetradare(index, 'UnderskriftHandlingRoll', value)}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Välj roll" />
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
                  
                  <div className="col-span-2">
                    <Input placeholder="Email" />
                  </div>
                  
                  <div className="col-span-1 flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={addForetradare}
                      className="p-2"
                    >
                      <Plus className="h-4 w-4" />
                    </Button>
                    {data.UnderskriftForetradare.length > 1 && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => removeForetradare(index)}
                        className="p-2"
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
            <p className="text-muted-foreground mb-6">
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

              <div className="space-y-4">
                <div className="grid grid-cols-10 gap-4 text-sm font-medium text-muted-foreground">
                  <div className="col-span-2">Förnamn</div>
                  <div className="col-span-2">Efternamn</div>
                  <div className="col-span-2">Titel</div>
                  <div className="col-span-2">Huvudansvarig</div>
                  <div className="col-span-1">Email</div>
                  <div className="col-span-1">Åtgärder</div>
                </div>

                {data.UnderskriftAvRevisor.map((revisor, index) => (
                  <div key={index} className="grid grid-cols-10 gap-4 items-center">
                    <div className="col-span-2">
                      <Input
                        value={revisor.UnderskriftHandlingTilltalsnamn}
                        onChange={(e) => updateRevisor(index, 'UnderskriftHandlingTilltalsnamn', e.target.value)}
                        placeholder="Förnamn"
                      />
                    </div>
                    
                    <div className="col-span-2">
                      <Input
                        value={revisor.UnderskriftHandlingEfternamn}
                        onChange={(e) => updateRevisor(index, 'UnderskriftHandlingEfternamn', e.target.value)}
                        placeholder="Efternamn"
                      />
                    </div>
                    
                    <div className="col-span-2">
                      <Input
                        value={revisor.UnderskriftHandlingTitel}
                        onChange={(e) => updateRevisor(index, 'UnderskriftHandlingTitel', e.target.value)}
                        placeholder="Titel"
                      />
                    </div>
                    
                    <div className="col-span-2">
                      <Select
                        value={revisor.UnderskriftRevisorspateckningRevisorHuvudansvarig ? 'true' : 'false'}
                        onValueChange={(value) => updateRevisor(index, 'UnderskriftRevisorspateckningRevisorHuvudansvarig', value === 'true')}
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="true">Ja</SelectItem>
                          <SelectItem value="false">Nej</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    
                    <div className="col-span-1">
                      <Input placeholder="Email" />
                    </div>
                    
                    <div className="col-span-1">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => removeRevisor(index)}
                        className="p-2"
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
