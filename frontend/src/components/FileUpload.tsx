import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { useToast } from '@/hooks/use-toast';
import { Upload, FileText, Loader2 } from 'lucide-react';
import { apiService } from '@/services/api';

interface FileUploadProps {
  onFileProcessed: (data: any) => void;
  allowTwoFiles?: boolean;
}

export function FileUpload({ onFileProcessed, allowTwoFiles = false }: FileUploadProps) {
  const [isUploading, setIsUploading] = useState(false);
  const [isDragOver, setIsDragOver] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const { toast } = useToast();



  const processFiles = async (files: File[]) => {
    // Validate files
    for (const file of files) {
      if (!file.name.toLowerCase().endsWith('.se')) {
        toast({
          title: "Fel filformat",
          description: "Vänligen ladda upp endast .SE filer",
          variant: "destructive"
        });
        return;
      }
    }

    if (allowTwoFiles && files.length > 2) {
      toast({
        title: "För många filer",
        description: "Maximalt 2 SE-filer kan laddas upp",
        variant: "destructive"
      });
      return;
    }

    if (!allowTwoFiles && files.length > 1) {
      toast({
        title: "För många filer",
        description: "Endast 1 SE-fil kan laddas upp",
        variant: "destructive"
      });
      return;
    }

    setIsUploading(true);
    setSelectedFiles(files);

    try {
      let result;
      if (files.length === 2) {
        // Upload both files with two_files flag
        result = await apiService.uploadTwoSeFiles(files[0], files[1]);
      } else {
        // Upload single file
        result = await apiService.uploadSeFile(files[0]);
      }

      if (result.success) {
        toast({
          title: "Fil(er) bearbetad(e)",
          description: files.length === 2 
            ? "Båda SE-filerna har analyserats och data extraherats"
            : "SE-filen har analyserats och data extraherats"
        });
        onFileProcessed(result);
      } else {
        throw new Error(result.message || 'Okänt fel');
      }

    } catch (error) {
      console.error('Upload error:', error);
      toast({
        title: "Fel vid uppladdning",
        description: error instanceof Error ? error.message : "Kunde inte bearbeta filen/filerna",
        variant: "destructive"
      });
    } finally {
      setIsUploading(false);
    }
  };



  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const fileList = event.target.files;
    if (fileList) {
      const files = Array.from(fileList);
      processFiles(files);
    }
  };

  const handleDrop = (event: React.DragEvent) => {
    event.preventDefault();
    setIsDragOver(false);
    
    const fileList = event.dataTransfer.files;
    if (fileList) {
      const files = Array.from(fileList);
      processFiles(files);
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
              multiple={allowTwoFiles}
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
                      {allowTwoFiles ? "Välj .SE fil(er)" : "Välj .SE fil"}
                    </>
                  )}
                </span>
              </Button>
            </label>

            <p className="text-xs text-muted-foreground">
              {allowTwoFiles 
                ? ".SE filer från bokföringsprogram (nuvarande år + föregående år)" 
                : ".SE filer från bokföringsprogram"
              }
            </p>
            
            {allowTwoFiles && selectedFiles.length > 0 && (
              <div className="text-xs text-gray-600 mt-2">
                {selectedFiles.length === 1 
                  ? `1 fil vald: ${selectedFiles[0].name}`
                  : `${selectedFiles.length} filer valda: ${selectedFiles.map(f => f.name).join(', ')}`
                }
              </div>
            )}
          </div>
        </div>
      </div>


    </div>
  );
}