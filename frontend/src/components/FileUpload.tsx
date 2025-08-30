import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { useToast } from '@/hooks/use-toast';
import { Upload, FileText, Loader2 } from 'lucide-react';
import { apiService } from '@/services/api';

interface FileUploadProps {
  onFileProcessed: (data: any) => void;
}

export function FileUpload({ onFileProcessed }: FileUploadProps) {
  const [isUploading, setIsUploading] = useState(false);
  const [isDragOver, setIsDragOver] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const { toast } = useToast();



  const processFile = async (file: File) => {
    if (!file.name.toLowerCase().endsWith('.se')) {
      toast({
        title: "Fel filformat",
        description: "Vänligen ladda upp en .SE fil",
        variant: "destructive"
      });
      return;
    }

    setIsUploading(true);
    setSelectedFile(file);

    try {
      const result = await apiService.uploadSeFile(file);

      if (result.success) {
        toast({
          title: "Fil bearbetad",
          description: "SE-filen har analyserats och data extraherats"
        });
        onFileProcessed(result);
      } else {
        throw new Error(result.message || 'Okänt fel');
      }

    } catch (error) {
      console.error('Upload error:', error);
      toast({
        title: "Fel vid uppladdning",
        description: error instanceof Error ? error.message : "Kunde inte bearbeta filen",
        variant: "destructive"
      });
    } finally {
      setIsUploading(false);
    }
  };



  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      processFile(file);
    }
  };

  const handleDrop = (event: React.DragEvent) => {
    event.preventDefault();
    setIsDragOver(false);
    
    const file = event.dataTransfer.files[0];
    if (file) {
      processFile(file);
    }
  };

  const handleDragOver = (event: React.DragEvent) => {
    event.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = (event: React.DragEvent) => {
    event.preventDefault();
    setIsDragOver(false);
  };

  return (
    <div className="space-y-4">
      <div
        className={`border-2 border-dashed rounded-lg p-4 text-center transition-colors ${
          isDragOver
            ? 'border-primary bg-primary/5'
            : 'border-border hover:border-primary/50'
        }`}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
      >
        <div className="space-y-3">
          <div className="mx-auto w-8 h-8 bg-muted rounded-lg flex items-center justify-center">
            {isUploading ? (
              <Loader2 className="w-4 h-4 animate-spin text-primary" />
            ) : (
              <FileText className="w-4 h-4 text-muted-foreground" />
            )}
          </div>
          
          <div className="space-y-1">
            <h3 className="text-sm font-medium">Ladda upp .SE fil</h3>
            <p className="text-xs text-muted-foreground">
              Dra och släpp din .SE fil här eller klicka nedan
            </p>
          </div>

          <div className="space-y-2">
            <input
              type="file"
              accept=".se,.SE"
              onChange={handleFileSelect}
              className="hidden"
              id="file-upload"
              disabled={isUploading}
            />
            
            <label htmlFor="file-upload">
              <Button
                variant="outline"
                size="sm"
                className="cursor-pointer"
                disabled={isUploading}
                asChild
              >
                <span>
                  {isUploading ? (
                    <>
                      <Loader2 className="w-3 h-3 mr-2 animate-spin" />
                      Bearbetar...
                    </>
                  ) : (
                    <>
                      <Upload className="w-3 h-3 mr-2" />
                      Välj .SE fil
                    </>
                  )}
                </span>
              </Button>
            </label>

            <p className="text-xs text-muted-foreground">
              .SE filer från bokföringsprogram
            </p>
          </div>
        </div>
      </div>


    </div>
  );
}