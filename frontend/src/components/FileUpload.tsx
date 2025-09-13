import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { useToast } from '@/hooks/use-toast';
import { Upload, FileText, Loader2, Check, Calendar } from 'lucide-react';
import { apiService } from '@/services/api';

interface FileUploadProps {
  onFileProcessed: (data: any) => void;
  allowTwoFiles?: boolean;
}

interface UploadedFile {
  file: File;
  uploaded: boolean;
}

export function FileUpload({ onFileProcessed, allowTwoFiles = false }: FileUploadProps) {
  const [isUploading, setIsUploading] = useState(false);
  const [currentYearFile, setCurrentYearFile] = useState<UploadedFile | null>(null);
  const [previousYearFile, setPreviousYearFile] = useState<UploadedFile | null>(null);
  const [dragOverArea, setDragOverArea] = useState<'current' | 'previous' | null>(null);
  const { toast } = useToast();



  const validateFile = (file: File): boolean => {
    if (!file.name.toLowerCase().endsWith('.se')) {
      toast({
        title: "Fel filformat",
        description: "Vänligen ladda upp en .SE fil",
        variant: "destructive"
      });
      return false;
    }
    return true;
  };

  const handleFileUpload = async (file: File, fileType: 'current' | 'previous') => {
    if (!validateFile(file)) return;

    // Set file as selected but not uploaded yet
    const uploadedFile: UploadedFile = { file, uploaded: false };
    if (fileType === 'current') {
      setCurrentYearFile(uploadedFile);
    } else {
      setPreviousYearFile(uploadedFile);
    }

    // Check if we should process immediately or wait for both files
    if (allowTwoFiles) {
      // For two-file mode, wait until we have both files or user explicitly processes
      return;
    } else {
      // For single-file mode, process immediately
      await processFiles([file]);
    }
  };

  const processFiles = async (files?: File[]) => {
    setIsUploading(true);

    try {
      let result;
      let filesToProcess: File[] = [];

      if (files) {
        // Direct file processing (single file mode)
        filesToProcess = files;
      } else {
        // Process selected files (two file mode)
        if (currentYearFile) filesToProcess.push(currentYearFile.file);
        if (previousYearFile) filesToProcess.push(previousYearFile.file);
      }

      if (filesToProcess.length === 0) {
        toast({
          title: "Ingen fil vald",
          description: "Vänligen välj minst en SE-fil",
          variant: "destructive"
        });
        return;
      }

      if (filesToProcess.length === 2) {
        // Upload both files with two_files flag
        result = await apiService.uploadTwoSeFiles(filesToProcess[0], filesToProcess[1]);
      } else {
        // Upload single file
        result = await apiService.uploadSeFile(filesToProcess[0]);
      }

      if (result.success) {
        // Mark files as uploaded
        if (currentYearFile) {
          setCurrentYearFile({ ...currentYearFile, uploaded: true });
        }
        if (previousYearFile) {
          setPreviousYearFile({ ...previousYearFile, uploaded: true });
        }

        toast({
          title: "Fil(er) bearbetad(e)",
          description: filesToProcess.length === 2 
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



  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>, fileType: 'current' | 'previous') => {
    const file = event.target.files?.[0];
    if (file) {
      handleFileUpload(file, fileType);
    }
  };

  const handleDrop = (event: React.DragEvent, fileType: 'current' | 'previous') => {
    event.preventDefault();
    setDragOverArea(null);
    
    const file = event.dataTransfer.files[0];
    if (file) {
      handleFileUpload(file, fileType);
    }
  };

  const handleDragOver = (event: React.DragEvent, fileType: 'current' | 'previous') => {
    event.preventDefault();
    setDragOverArea(fileType);
  };

  const handleDragLeave = (event: React.DragEvent) => {
    event.preventDefault();
    setDragOverArea(null);
  };

  const canProcess = () => {
    if (!allowTwoFiles) return false;
    return currentYearFile && !currentYearFile.uploaded;
  };

  const resetFiles = () => {
    setCurrentYearFile(null);
    setPreviousYearFile(null);
  };

  if (!allowTwoFiles) {
    // Single file upload (existing simple UI)
    return (
      <div className="space-y-4">
        <div
          className={`border-2 border-dashed rounded-lg p-4 text-center transition-colors ${
            dragOverArea === 'current'
              ? 'border-primary bg-primary/5'
              : 'border-border hover:border-primary/50'
          }`}
          onDrop={(e) => handleDrop(e, 'current')}
          onDragOver={(e) => handleDragOver(e, 'current')}
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
              <h3 className="text-sm font-bold">Ladda upp SE-filer här:</h3>
              <p className="text-xs text-muted-foreground">
                Dra och släpp din .SE fil här eller klicka nedan
              </p>
            </div>

            <div className="space-y-2">
              <input
                type="file"
                accept=".se,.SE"
                onChange={(e) => handleFileSelect(e, 'current')}
                className="hidden"
                id="file-upload-single"
                disabled={isUploading}
              />
              
              <label htmlFor="file-upload-single">
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

  // Two file upload with separate frames
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Current Year Upload */}
        <div
          className={`border-2 border-dashed rounded-lg p-4 text-center transition-all duration-300 ${
            currentYearFile
              ? 'border-green-500 bg-green-50'
              : dragOverArea === 'current'
              ? 'border-primary bg-primary/5'
              : 'border-border hover:border-primary/50'
          }`}
          onDrop={(e) => handleDrop(e, 'current')}
          onDragOver={(e) => handleDragOver(e, 'current')}
          onDragLeave={handleDragLeave}
        >
          <div className="space-y-3">
            <div className="mx-auto w-10 h-10 bg-muted rounded-lg flex items-center justify-center">
              {currentYearFile?.uploaded ? (
                <Check className="w-5 h-5 text-green-600" />
              ) : isUploading && currentYearFile ? (
                <Loader2 className="w-5 h-5 animate-spin text-primary" />
              ) : currentYearFile ? (
                <Calendar className="w-5 h-5 text-green-600" />
              ) : (
                <Calendar className="w-5 h-5 text-muted-foreground" />
              )}
            </div>
            
            <div className="space-y-1">
              <h3 className="text-sm font-medium text-gray-900">
                Räkenskapsår
              </h3>
              <p className="text-xs text-muted-foreground">
                {currentYearFile?.uploaded 
                  ? `✓ ${currentYearFile.file.name}`
                  : currentYearFile
                  ? `Vald: ${currentYearFile.file.name}`
                  : "Dra och släpp .SE fil här"
                }
              </p>
            </div>

            {!currentYearFile?.uploaded && (
              <div className="space-y-2">
                <input
                  type="file"
                  accept=".se,.SE"
                  onChange={(e) => handleFileSelect(e, 'current')}
                  className="hidden"
                  id="file-upload-current"
                  disabled={isUploading}
                />
                
                <label htmlFor="file-upload-current">
                  <Button
                    variant="outline"
                    size="sm"
                    className="cursor-pointer"
                    disabled={isUploading}
                    asChild
                  >
                    <span>
                      <Upload className="w-3 h-3 mr-2" />
                      {currentYearFile ? "Byt fil" : "Välj fil"}
                    </span>
                  </Button>
                </label>
              </div>
            )}
          </div>
        </div>

        {/* Previous Year Upload */}
        <div
          className={`border-2 border-dashed rounded-lg p-4 text-center transition-all duration-300 ${
            previousYearFile
              ? 'border-green-500 bg-green-50'
              : dragOverArea === 'previous'
              ? 'border-primary bg-primary/5'
              : 'border-gray-300 hover:border-primary/50'
          }`}
          onDrop={(e) => handleDrop(e, 'previous')}
          onDragOver={(e) => handleDragOver(e, 'previous')}
          onDragLeave={handleDragLeave}
        >
          <div className="space-y-3">
            <div className="mx-auto w-10 h-10 bg-muted rounded-lg flex items-center justify-center">
              {previousYearFile?.uploaded ? (
                <Check className="w-5 h-5 text-green-600" />
              ) : isUploading && previousYearFile ? (
                <Loader2 className="w-5 h-5 animate-spin text-primary" />
              ) : previousYearFile ? (
                <Calendar className="w-5 h-5 text-green-600" />
              ) : (
                <Calendar className="w-5 h-5 text-muted-foreground" />
              )}
            </div>
            
            <div className="space-y-1">
              <h3 className="text-sm font-medium text-gray-700">
                Föregående år
              </h3>
              <p className="text-xs text-muted-foreground">
                {previousYearFile?.uploaded 
                  ? `✓ ${previousYearFile.file.name}`
                  : previousYearFile
                  ? `Vald: ${previousYearFile.file.name}`
                  : "Valfritt - för bättre analys"
                }
              </p>
            </div>

            {!previousYearFile?.uploaded && (
              <div className="space-y-2">
                <input
                  type="file"
                  accept=".se,.SE"
                  onChange={(e) => handleFileSelect(e, 'previous')}
                  className="hidden"
                  id="file-upload-previous"
                  disabled={isUploading}
                />
                
                <label htmlFor="file-upload-previous">
                  <Button
                    variant="outline"
                    size="sm"
                    className="cursor-pointer"
                    disabled={isUploading}
                    asChild
                  >
                    <span>
                      <Upload className="w-3 h-3 mr-2" />
                      {previousYearFile ? "Byt fil" : "Välj fil"}
                    </span>
                  </Button>
                </label>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Process Button */}
      {canProcess() && (
        <div className="flex justify-center space-x-3">
          <Button
            onClick={() => processFiles()}
            disabled={isUploading}
            className="px-6"
          >
            {isUploading ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Bearbetar...
              </>
            ) : (
              <>
                <FileText className="w-4 h-4 mr-2" />
Bearbeta {previousYearFile ? 'filerna' : 'filen'}
              </>
            )}
          </Button>
          
          <Button
            variant="outline"
            onClick={resetFiles}
            disabled={isUploading}
          >
            Rensa
          </Button>
        </div>
      )}

      <div className="text-center">
        <p className="text-xs text-muted-foreground">
          Ladda upp åtminstonde nuvarande räkenskapsårs SE fil. Föregående år är valfritt men ger ett bättre och mer detaljerad resultat.
        </p>
      </div>
    </div>
  );
}