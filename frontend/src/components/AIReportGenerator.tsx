import { useState } from 'react';
import { FileUpload } from './FileUpload';
import { ProcessedDataView } from './ProcessedDataView';
import { AnnualReportChat } from './AnnualReportChat';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { FileText, MessageSquare, Upload } from 'lucide-react';

export function AIReportGenerator() {
  const [processedData, setProcessedData] = useState<any>(null);
  const [reportId, setReportId] = useState<string | null>(null);

  const handleFileProcessed = (data: any) => {
    setProcessedData(data.data);
    setReportId(data.reportId);
  };

  return (
    <div className="min-h-screen bg-background">
      <div className="container mx-auto p-6">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-foreground mb-2">
            AI-driven Årsredovisning
          </h1>
          <p className="text-lg text-muted-foreground">
            Automatisk generering av årsredovisningar med AI-stöd
          </p>
        </div>

        <Tabs defaultValue="upload" className="space-y-6">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="upload" className="flex items-center gap-2">
              <Upload className="w-4 h-4" />
              Ladda upp SE-fil
            </TabsTrigger>
            <TabsTrigger value="manual" className="flex items-center gap-2">
              <MessageSquare className="w-4 h-4" />
              Manuell inmatning
            </TabsTrigger>
            <TabsTrigger value="results" className="flex items-center gap-2" disabled={!processedData}>
              <FileText className="w-4 h-4" />
              Resultat
            </TabsTrigger>
          </TabsList>

          <TabsContent value="upload" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Automatisk SE-filbearbetning</CardTitle>
                <p className="text-sm text-muted-foreground">
                  Ladda upp din .SE fil från bokföringsprogrammet för automatisk AI-analys
                </p>
              </CardHeader>
              <CardContent>
                <FileUpload onFileProcessed={handleFileProcessed} />
              </CardContent>
            </Card>

            {processedData && (
              <Card>
                <CardHeader>
                  <CardTitle>Förhandsvisning av extraherad data</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 p-4 bg-muted rounded-lg">
                      {processedData.organizationNumber && (
                        <div>
                          <p className="text-sm text-muted-foreground">Org.nr</p>
                          <p className="font-medium">{processedData.organizationNumber}</p>
                        </div>
                      )}
                      <div>
                        <p className="text-sm text-muted-foreground">Räkenskapsår</p>
                        <p className="font-medium">{processedData.fiscalYearString}</p>
                      </div>
                      <div>
                        <p className="text-sm text-muted-foreground">Resultatposter</p>
                        <p className="font-medium">{processedData.rr_data?.length || processedData.incomeStatement?.length || 0} st</p>
                      </div>
                    </div>
                    <p className="text-sm text-muted-foreground">
                      Gå till "Resultat"-fliken för att se fullständig rapport och generera PDF.
                    </p>
                  </div>
                </CardContent>
              </Card>
            )}
          </TabsContent>

          <TabsContent value="manual" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Manuell rapportgenerering</CardTitle>
                <p className="text-sm text-muted-foreground">
                  Skapa årsredovisning genom att svara på frågor i chatten
                </p>
              </CardHeader>
              <CardContent className="p-0">
                <AnnualReportChat />
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="results" className="space-y-6">
            {processedData && reportId ? (
              <ProcessedDataView data={processedData} reportId={reportId} />
            ) : (
              <Card>
                <CardContent className="p-8 text-center">
                  <p className="text-muted-foreground">
                    Inga resultat tillgängliga än. Ladda upp en SE-fil eller fyll i data manuellt först.
                  </p>
                </CardContent>
              </Card>
            )}
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}