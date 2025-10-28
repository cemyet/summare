import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Download as DownloadIcon, FileText, Check } from 'lucide-react';

interface DownloadFile {
  id: string;
  title: string;
  subtitle: string;
  filename: string;
  icon: React.ReactNode;
  downloaded: boolean;
}

interface DownloadProps {
  companyData?: any;
}

export function Download({ companyData }: DownloadProps) {
  const [isGenerating, setIsGenerating] = useState<string | null>(null);
  const [files, setFiles] = useState<DownloadFile[]>([
    {
      id: 'arsredovisning',
      title: 'Årsredovisning',
      subtitle: 'Ladda ner pdf',
      filename: 'arsredovisning.pdf',
      icon: <FileText className="w-5 h-5" />,
      downloaded: false
    },
    {
      id: 'inkomstdeklaration-pdf',
      title: 'Inkomstdeklaration',
      subtitle: 'Ladda ner pdf',
      filename: 'INK2_inkomstdeklaration.pdf',
      icon: <FileText className="w-5 h-5" />,
      downloaded: false
    },
    {
      id: 'inkomstdeklaration-sru',
      title: 'Inkomstdeklaration',
      subtitle: 'Ladda ner SRU-fil',
      filename: 'INK2.zip',
      icon: <FileText className="w-5 h-5" />,
      downloaded: false
    },
    {
      id: 'bokforingsorder',
      title: 'Bokföringsinstruktion',
      subtitle: 'Ladda ner pdf',
      filename: 'bokforingsinstruktion.pdf',
      icon: <FileText className="w-5 h-5" />,
      downloaded: false
    }
  ]);

  const handleDownload = async (fileId: string) => {
    const file = files.find(f => f.id === fileId);
    if (!file) return;

    try {
      setIsGenerating(fileId);
      
      // Handle Årsredovisning with server-side PDF generation
      if (fileId === 'arsredovisning') {
        if (!companyData) {
          alert('Företagsdata saknas. Vänligen ladda upp en SIE-fil först.');
          setIsGenerating(null);
          return;
        }
        
        const API_BASE = import.meta.env.VITE_API_URL || 'https://api.summare.se';
        
        // Add cache buster to ensure fresh PDF generation
        // Debug INV specifically before sending
        const invItems = (companyData.noterData || []).filter((item: any) => item.block === 'INV');
        const invNedskr = invItems.filter((item: any) => 
          (item.row_title || '').toLowerCase().includes('nedskrivning')
        );
        
        // Debug NOT2 specifically
        const not2Items = (companyData.noterData || []).filter((item: any) => item.block === 'NOT2');
        
        const response = await fetch(`${API_BASE}/api/pdf/annual-report`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ 
            companyData,
            renderVersion: Date.now() // cache buster
          }),
          cache: 'no-store', // prevent browser caching
        });
        
        if (!response.ok) {
          const errorText = await response.text();
          console.error('Annual report PDF error:', errorText);
          throw new Error(`Server responded with ${response.status}`);
        }
        
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = file.filename;
        document.body.appendChild(a);
        a.click();
        URL.revokeObjectURL(url);
        a.remove();
      } else if (fileId === 'inkomstdeklaration-pdf') {
        // Handle INK2 form with server-side PDF form filling
        if (!companyData) {
          alert('Företagsdata saknas. Vänligen ladda upp en SIE-fil först.');
          setIsGenerating(null);
          return;
        }
        
        const API_BASE = import.meta.env.VITE_API_URL || 'https://api.summare.se';
        
        const response = await fetch(`${API_BASE}/api/pdf/ink2-form`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ 
            companyData,
            renderVersion: Date.now() // cache buster
          }),
          cache: 'no-store', // prevent browser caching
        });
        
        if (!response.ok) {
          const errorText = await response.text();
          console.error('INK2 form PDF error:', errorText);
          throw new Error(`Server responded with ${response.status}`);
        }
        
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = file.filename;
        document.body.appendChild(a);
        a.click();
        URL.revokeObjectURL(url);
        a.remove();
      } else if (fileId === 'inkomstdeklaration-sru') {
        // Handle SRU file generation
        if (!companyData) {
          alert('Företagsdata saknas. Vänligen ladda upp en SIE-fil först.');
          setIsGenerating(null);
          return;
        }
        
        const API_BASE = import.meta.env.VITE_API_URL || 'https://api.summare.se';
        
        const response = await fetch(`${API_BASE}/api/sru/generate`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ 
            companyData
          }),
          cache: 'no-store',
        });
        
        if (!response.ok) {
          const errorText = await response.text();
          console.error('SRU file error:', errorText);
          throw new Error(`Server responded with ${response.status}`);
        }
        
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = file.filename;
        document.body.appendChild(a);
        a.click();
        URL.revokeObjectURL(url);
        a.remove();
      } else if (fileId === 'bokforingsorder') {
        // Handle Bokföringsinstruktion PDF generation
        if (!companyData) {
          alert('Företagsdata saknas. Vänligen ladda upp en SIE-fil först.');
          setIsGenerating(null);
          return;
        }
        
        const API_BASE = import.meta.env.VITE_API_URL || 'https://api.summare.se';
        
        const response = await fetch(`${API_BASE}/api/pdf/bokforing-instruktion`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ 
            companyData,
            renderVersion: Date.now() // cache buster
          }),
          cache: 'no-store',
        });
        
        if (!response.ok) {
          const errorText = await response.text();
          console.error('Bokföringsinstruktion PDF error:', errorText);
          
          // If no adjustments needed (400 error), show friendly message
          if (response.status === 400) {
            alert('Bokföringsinstruktion behövs inte - inga justeringar krävs för detta bolag.');
          } else {
            throw new Error(`Server responded with ${response.status}`);
          }
          setIsGenerating(null);
          return;
        }
        
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = file.filename;
        document.body.appendChild(a);
        a.click();
        URL.revokeObjectURL(url);
        a.remove();
      } else {
        // Fetch other files from public folder
        const response = await fetch(`/${file.filename}`);
        if (!response.ok) {
          throw new Error('Failed to download file');
        }

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = file.filename;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      }

      // Mark file as downloaded
      setFiles(prevFiles =>
        prevFiles.map(f =>
          f.id === fileId ? { ...f, downloaded: true } : f
        )
      );
      setIsGenerating(null);
    } catch (error) {
      console.error('Error downloading file:', error);
      alert('Ett fel uppstod vid nedladdning. Försök igen.');
      setIsGenerating(null);
    }
  };

  return (
    <div data-section="download" className="space-y-8">
      <Card>
        <CardHeader>
          <CardTitle className="text-2xl font-bold">Dokument och filer</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground mb-6">
            Nu finns alla dokument och filer klara för nedladdning. Signering av årsredovisning kommer att göras digitalt i nästa steg, men du kan också ladda ner den som pdf. Inkomstdeklarationen kan du antingen ladda ner som pdf eller som SRU-filer, som du sen kan ladda upp på Skatteverkets hemsida för att lämna in deklarationen. Dessutom finns en bokföringsinstruktion att ladda ner om justeringar på årets resultat har gjorts.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {files.map((file) => (
              <div
                key={file.id}
                className={`border-2 border-dashed rounded-lg p-6 text-center transition-all duration-300 ${
                  file.downloaded
                    ? 'border-green-500 bg-green-50'
                    : 'border-border hover:border-primary/50'
                }`}
              >
                <div className="space-y-3">
                  <div className="mx-auto w-12 h-12 bg-muted rounded-lg flex items-center justify-center">
                    {file.downloaded ? (
                      <Check className="w-6 h-6 text-green-600" />
                    ) : (
                      <div className="text-muted-foreground">{file.icon}</div>
                    )}
                  </div>

                  <div className="space-y-1">
                    <h3 className="text-base font-semibold text-gray-900">
                      {file.title}
                    </h3>
                    <p className="text-sm text-muted-foreground">
                      {file.subtitle}
                    </p>
                  </div>

                  <Button
                    variant="outline"
                    size="sm"
                    className="cursor-pointer w-full mt-2"
                    onClick={() => handleDownload(file.id)}
                    disabled={isGenerating === file.id}
                  >
                    {isGenerating === file.id ? (
                      <>
                        <div className="w-4 h-4 mr-2 border-2 border-gray-400 border-t-transparent rounded-full animate-spin" />
                        Genererar...
                      </>
                    ) : (
                      <>
                        <DownloadIcon className="w-4 h-4 mr-2" />
                        Ladda ner
                      </>
                    )}
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

