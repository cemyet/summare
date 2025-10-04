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
  const [files, setFiles] = useState<DownloadFile[]>([
    {
      id: 'arsredovisning',
      title: 'Årsredovisning',
      subtitle: 'Ladda ner pdf',
      filename: 'Test.pdf',
      icon: <FileText className="w-5 h-5" />,
      downloaded: false
    },
    {
      id: 'inkomstdeklaration-pdf',
      title: 'Inkomstdeklaration',
      subtitle: 'Ladda ner pdf',
      filename: 'Test.pdf',
      icon: <FileText className="w-5 h-5" />,
      downloaded: false
    },
    {
      id: 'inkomstdeklaration-sru',
      title: 'Inkomstdeklaration',
      subtitle: 'Ladda ner SRU-fil',
      filename: 'Test.pdf',
      icon: <FileText className="w-5 h-5" />,
      downloaded: false
    },
    {
      id: 'bokforingsorder',
      title: 'Bokföringsorder',
      subtitle: 'Ladda ner pdf',
      filename: 'Test.pdf',
      icon: <FileText className="w-5 h-5" />,
      downloaded: false
    }
  ]);

  const handleDownload = async (fileId: string) => {
    const file = files.find(f => f.id === fileId);
    if (!file) return;

    try {
      // Fetch the file from public folder
      const response = await fetch(`/${file.filename}`);
      if (!response.ok) {
        throw new Error('Failed to download file');
      }

      // Create blob from response
      const blob = await response.blob();
      
      // Create a temporary URL for the blob
      const url = window.URL.createObjectURL(blob);
      
      // Create a temporary anchor element to trigger download
      const a = document.createElement('a');
      a.href = url;
      a.download = file.filename;
      document.body.appendChild(a);
      a.click();
      
      // Cleanup
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

      // Mark file as downloaded
      setFiles(prevFiles =>
        prevFiles.map(f =>
          f.id === fileId ? { ...f, downloaded: true } : f
        )
      );
    } catch (error) {
      console.error('Error downloading file:', error);
      alert('Ett fel uppstod vid nedladdning. Försök igen.');
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
            Nu finns alla dokument och filer klara för nedladdning. Signering av årsredovisning kommer att göras digitalt i nästa steg, men du kan också ladda ner den som pdf. Inkomstdeklarationen kan du antingen ladda ner som pdf eller som SRU-filer, som du sen kan ladda upp på Skatteverkets hemsida för att lämna in deklarationen. Dessutom finns en bokföringsorder att ladda ner om justeringar på årets resultat har gjorts.
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
                  >
                    {file.downloaded ? (
                      <>
                        <Check className="w-4 h-4 mr-2" />
                        Nedladdad
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

