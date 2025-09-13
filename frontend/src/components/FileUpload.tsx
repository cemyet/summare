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
  const [showYearValidationError, setShowYearValidationError] = useState(false);
  const [yearValidationMessage, setYearValidationMessage] = useState('');
  const [showCompanyMismatchError, setShowCompanyMismatchError] = useState(false);
  const [companyMismatchMessage, setCompanyMismatchMessage] = useState('');
  const { toast } = useToast();

  // Helper to extract server error details
  const serverDetail = (err: any): string => {
    // axios-like
    if (err?.response?.data?.detail) {
      const d = err.response.data.detail;
      if (typeof d === 'string') return d;
      if (typeof d === 'object' && (d.message || d.msg)) return String(d.message || d.msg);
      return JSON.stringify(d);
    }
    if (typeof err?.response?.data === 'string') return err.response.data;

    // fetch-like
    if (err instanceof Response) {
      return `Fel ${err.status}`;
    }

    // fallbacks
    if (err?.message) return String(err.message);
    return '';
  };

  // ---------- SIE preflight helpers (runs before upload) ----------
  const readText = (f: File) => f.text();

  const extractSieMeta = async (file: File) => {
    const txt = await readText(file);
    // fiscal year from #RAR <start> <end> → take end year
    const rar = txt.match(/#RAR\s+(\d{8})\s+(\d{8})/i);
    const endYear = rar ? parseInt(rar[2].slice(0, 4), 10) : null;

    // orgnr (digits only); allow #ORGNR or #ORGANISATIONSNR
    const orgMatch =
      txt.match(/#ORGNR\s+"?([\d\- ]{10,14})"?/i) ||
      txt.match(/#ORGANISATIONSNR\s+"?([\d\- ]{10,14})"?/i);
    const orgnr = orgMatch ? orgMatch[1].replace(/\D/g, '').slice(-10) : null;

    // company name (best effort)
    const nameMatch =
      txt.match(/#FNAMN\s+"([^"]+)"/i) ||
      txt.match(/#KONTOAGN\s+"([^"]+)"/i);
    const company = nameMatch ? nameMatch[1].trim() : null;

    return { endYear, orgnr, company };
  };

  type PreflightResult =
    | { ok: true }
    | { ok: false; type: 'YEAR'; message: string }
    | { ok: false; type: 'COMPANY'; message: string };

  const preflightValidate = async (files: File[]): Promise<PreflightResult> => {
    if (files.length !== 2) return { ok: true };
    const [a, b] = files;
    const [m1, m2] = await Promise.all([extractSieMeta(a), extractSieMeta(b)]);

    // Check year consecutiveness when both years are present
    if (m1.endYear && m2.endYear) {
      const fy = Math.max(m1.endYear, m2.endYear);
      const py = Math.min(m1.endYear, m2.endYear);
      if (fy - py !== 1) {
        return {
          ok: false,
          type: 'YEAR',
          message: `Filerna måste avse två på varandra följande räkenskapsår. Nuvarande: ${fy}, föregående: ${py}.`,
        };
      }
    }

    // Prefer orgnr for company check (fallback to name)
    if (m1.orgnr && m2.orgnr && m1.orgnr !== m2.orgnr) {
      const A = m1.company || m1.orgnr;
      const B = m2.company || m2.orgnr;
      return {
        ok: false,
        type: 'COMPANY',
        message: `Filerna tillhör olika företag: ${A} vs ${B}. Ladda upp filer för samma bolag.`,
      };
    }
    return { ok: true };
  };

  // Map structured backend errors → white popups
  const parseBackendError = (err: any): { code?: string; message?: string } | null => {
    const detail = err?.response?.data?.detail ?? err?.data?.detail ?? err?.detail;
    if (!detail) return null;
    if (typeof detail === 'string') return { message: detail };
    if (typeof detail === 'object') {
      return { code: detail.code || detail.error_code || detail.type, message: detail.message || detail.msg };
    }
    return null;
  };



  const validateFile = (file: File): boolean => {
    if (!file.name.toLowerCase().endsWith('.se')) {
      toast({
        title: "Fel filformat",
        description: "Vänligen ladda upp en SIE-fil"
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
          description: "Vänligen välj minst en SIE-fil"
        });
        return;
      }

      // ---------- PRE-FLIGHT VALIDATION (before any upload) ----------
      if (filesToProcess.length === 2) {
        const pre = await preflightValidate(filesToProcess);
        if (!pre.ok) {
          const error = pre as { ok: false; type: 'YEAR' | 'COMPANY'; message: string };
          if (error.type === 'YEAR') {
            setYearValidationMessage(error.message);
            setShowYearValidationError(true);
          } else if (error.type === 'COMPANY') {
            setCompanyMismatchMessage(error.message);
            setShowCompanyMismatchError(true);
          }
          return;
        }
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
            ? "Båda SIE-filerna har analyserats och data extraherats"
            : "SIE-filen har analyserats och data extraherats"
        });
        onFileProcessed(result);
      } else {
        throw new Error(result.message || 'Okänt fel');
      }

    } catch (error) {
      console.error('Upload error:', error);
      // Prefer structured backend error → map to white popups
      const mapped = parseBackendError(error);
      if (mapped?.code === 'YEAR_MISMATCH') {
        setYearValidationMessage(mapped.message || 'Filerna måste avse två på varandra följande räkenskapsår.');
        setShowYearValidationError(true);
      } else if (mapped?.code === 'COMPANY_MISMATCH') {
        setCompanyMismatchMessage(mapped.message || 'SIE-filerna verkar vara från olika bolag.');
        setShowCompanyMismatchError(true);
      } else {
        // Fall back to best available message (still white toast)
        const detail = serverDetail(error);
        const fallback =
          detail && !String(detail).startsWith('Upload failed')
            ? String(detail)
            : 'Kunde inte bearbeta filen/filerna. Kontrollera att SIE-filen är giltig och försök igen.';
        toast({ title: 'Fel vid uppladdning', description: fallback });
      }
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
              <h3 className="text-sm font-semibold">Ladda upp SIE-filer här</h3>
              <p className="text-xs text-muted-foreground">
                Dra och släpp din SIE-fil här eller klicka nedan
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
                        Välj SIE-fil
                      </>
                    )}
                  </span>
                </Button>
              </label>

              <p className="text-xs text-muted-foreground">
                SIE-filer från bokföringsprogram
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
                  : "Dra och släpp SIE-fil här"
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
          Ladda upp åtminstonde nuvarande räkenskapsårs SIE-fil. Föregående år är valfritt men ger ett bättre och mer detaljerat resultat i framställningen av noterna.
        </p>
      </div>

      {/* Year Validation Error Popup */}
      {showYearValidationError && (
        <div className="fixed bottom-4 right-4 z-50 bg-white border border-gray-200 rounded-lg shadow-lg p-4 max-w-sm animate-in slide-in-from-bottom-2">
          <div className="flex items-start">
            <div className="flex-shrink-0">
              <svg className="w-5 h-5 text-red-500 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
              </svg>
            </div>
            <div className="ml-3 flex-1">
              <p className="text-sm font-medium text-gray-900">
                Felaktiga räkenskapsår
              </p>
              <p className="text-sm text-gray-500 mt-1">
                {yearValidationMessage}
              </p>
            </div>
            <button
              onClick={() => setShowYearValidationError(false)}
              className="ml-4 flex-shrink-0 text-gray-400 hover:text-gray-600"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12"/>
              </svg>
            </button>
          </div>
        </div>
      )}

      {/* Company Mismatch Error Popup */}
      {showCompanyMismatchError && (
        <div className="fixed bottom-4 right-4 z-50 bg-white border border-gray-200 rounded-lg shadow-lg p-4 max-w-sm animate-in slide-in-from-bottom-2">
          <div className="flex items-start">
            <div className="flex-shrink-0">
              <svg className="w-5 h-5 text-red-500 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
              </svg>
            </div>
            <div className="ml-3 flex-1">
              <p className="text-sm font-medium text-gray-900">
                Olika bolag upptäckta
              </p>
              <p className="text-sm text-gray-500 mt-1">
                {companyMismatchMessage || 'SIE-filerna verkar vara från olika bolag. Kontrollera att båda filerna tillhör samma företag.'}
              </p>
            </div>
            <button
              onClick={() => setShowCompanyMismatchError(false)}
              className="ml-4 flex-shrink-0 text-gray-400 hover:text-gray-600"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12"/>
              </svg>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}