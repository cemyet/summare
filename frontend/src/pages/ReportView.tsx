import { useState, useEffect, useRef } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Popover,
  PopoverClose,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { API_BASE_URL } from "@/config/api";
import { ChevronDown, User, FileText, Calculator, PenTool, HelpCircle, Download, Settings, Copy, Check, Send, Link2, RefreshCw, X } from "lucide-react";
import { useToast } from "@/hooks/use-toast";

interface ReportData {
  id: string;
  organization_number: string;
  company_name: string;
  fiscal_year: number;
  fiscal_year_start: string;
  fiscal_year_end: string;
  status: string;
  rr_data: any[];
  br_data: any[];
  noter_data: any[];
  fb_data: any;
  ink2_data: any[];
  signering_data: any;
  scraped_company_data?: any;
  avskrivningstider?: Record<string, number>;
  updated_at: string;
  created_at: string;
}

interface CompanyOption {
  organization_number: string;
  company_name: string;
}

interface FiscalYearOption {
  id: string;
  fiscal_year_start: string;
  fiscal_year_end: string;
  label: string;
}

interface SignerPerson {
  fornamn: string;
  efternamn: string;
  roll?: string;
  email: string;
  personnummer?: string;
  status: 'pending' | 'signed' | 'sent';
  signed_at?: string;
  signing_url?: string;
  revisionsbolag?: string;
}

interface SigneringStatusData {
  signeringData: {
    befattningshavare: SignerPerson[];
    revisor: SignerPerson[];
    date?: string;
    ValtRevisionsbolag?: string;
  };
  signingStatus?: {
    job_uuid: string;
    job_name: string;
    event: string;
    signing_details?: any;
    signed_pdf_download_url?: string;
    updated_at?: string;
  };
  memberUrls: Record<string, string>;
}

const NAV_ITEMS = [
  { id: "signeringsstatus", label: "Signeringsstatus", icon: PenTool },
  { id: "forvaltningsberattelse", label: "Förvaltningsberättelse", icon: FileText },
  { id: "resultatrakning", label: "Resultaträkning", icon: FileText },
  { id: "balansrakning", label: "Balansräkning", icon: FileText },
  { id: "noter", label: "Noter", icon: FileText },
  { id: "skattedeklaration", label: "Skattedeklaration", icon: Calculator },
  { id: "mina-dokument", label: "Mina dokument", icon: Download },
  { id: "mina-uppgifter", label: "Mina uppgifter", icon: Settings },
  { id: "support", label: "Support", icon: HelpCircle },
];

// Note order for proper numbering
const NOTE_ORDER = [
  'NOT1', 'NOT2', 'BYGG', 'MASKIN', 'INV', 'MAT', 'NYANLAGG',
  'KONCERN', 'INTRESSEFTG', 'FORDRKONC', 'FORDRINTRE', 
  'OVRIGAFTG', 'FORDROVRFTG', 'LVP',
  'SAKERHET', 'EVENTUAL', 'OVRIGA'
];

// Blocks that should be completely hidden if they have no non-zero amounts
// These are asset/liability note blocks that only show when there's actual data
const BLOCKS_TO_HIDE_IF_ZERO = [
  'BYGG', 'MASKIN', 'INV', 'MAT', 'NYANLAGG',
  'KONCERN', 'INTRESSEFTG', 'FORDRKONC', 'FORDRINTRE',
  'OVRIGAFTG', 'FORDROVRFTG', 'LVP',
  'NOT', // The generic "Noter" header block
  '', // Empty block name (Förbättringsutgifter på annans fastighet)
];

// Block headings mapping
const BLOCK_HEADINGS: Record<string, string> = {
  'NOT1': 'Redovisningsprinciper',
  'NOT2': 'Medelantalet anställda',
  'BYGG': 'Byggnader och mark',
  'MASKIN': 'Maskiner och andra tekniska anläggningar',
  'INV': 'Inventarier, verktyg och installationer',
  'MAT': 'Övriga materiella anläggningstillgångar',
  'NYANLAGG': 'Pågående nyanläggningar och förskott avseende materiella anläggningstillgångar',
  'KONCERN': 'Andelar i koncernföretag',
  'INTRESSEFTG': 'Andelar i intresseföretag och gemensamt styrda företag',
  'FORDRKONC': 'Fordringar hos koncernföretag',
  'FORDRINTRE': 'Fordringar hos intresseföretag och gemensamt styrda företag',
  'OVRIGAFTG': 'Ägarintressen i övriga företag',
  'FORDROVRFTG': 'Fordringar hos övriga företag som det finns ett ägarintresse i',
  'LVP': 'Andra långfristiga värdepappersinnehav',
  'SAKERHET': 'Ställda säkerheter',
  'EVENTUAL': 'Eventualförpliktelser',
  'OVRIGA': 'Övriga upplysningar',
};

// Download Card Component for Mina dokument section
interface DownloadCardProps {
  title: string;
  subtitle: string;
  reportId?: string;
  endpoint: string;
  filename: string;
}

const DownloadCard = ({ title, subtitle, reportId, endpoint, filename }: DownloadCardProps) => {
  const [isGenerating, setIsGenerating] = useState(false);
  const [downloaded, setDownloaded] = useState(false);

  const handleDownload = async () => {
    if (!reportId) return;
    
    try {
      setIsGenerating(true);
      
      // Determine the correct API endpoint
      let url = '';
      if (endpoint === 'annual-report') {
        url = `${API_BASE_URL}/api/pdf/annual-report/${reportId}`;
      } else if (endpoint === 'ink2-form') {
        url = `${API_BASE_URL}/api/pdf/ink2-form/${reportId}`;
      } else if (endpoint === 'sru') {
        url = `${API_BASE_URL}/api/sru/generate/${reportId}`;
      } else if (endpoint === 'bokforing-instruktion') {
        url = `${API_BASE_URL}/api/pdf/bokforing-instruktion/${reportId}`;
      }
      
      const response = await fetch(url, {
        method: 'GET',
        cache: 'no-store',
      });
      
      if (!response.ok) {
        const errorText = await response.text();
        console.error(`${endpoint} error:`, errorText);
        
        // Handle specific error for bokforing-instruktion (no adjustments needed)
        if (response.status === 400 && endpoint === 'bokforing-instruktion') {
          alert('Ingen bokföringsinstruktion krävs - inga justeringar behövs för detta bolag.');
          setIsGenerating(false);
          return;
        }
        
        throw new Error(`Server responded with ${response.status}`);
      }
      
      const blob = await response.blob();
      const blobUrl = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = blobUrl;
      
      // Use filename from Content-Disposition header if available
      const contentDisposition = response.headers.get('Content-Disposition');
      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename="(.+)"/);
        if (filenameMatch) {
          a.download = filenameMatch[1];
        } else {
          a.download = filename;
        }
      } else {
        a.download = filename;
      }
      
      document.body.appendChild(a);
      a.click();
      URL.revokeObjectURL(blobUrl);
      a.remove();
      
      setDownloaded(true);
      setIsGenerating(false);
    } catch (error) {
      console.error('Error downloading file:', error);
      alert('Ett fel uppstod vid nedladdning. Försök igen.');
      setIsGenerating(false);
    }
  };

  return (
    <div
      className={`border-2 border-dashed rounded-lg p-6 text-center transition-all duration-300 ${
        downloaded
          ? 'border-green-500 bg-green-50'
          : 'border-gray-200 hover:border-gray-400'
      }`}
    >
      <div className="space-y-3">
        <div className="mx-auto w-12 h-12 bg-gray-100 rounded-lg flex items-center justify-center">
          {downloaded ? (
            <svg className="w-6 h-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          ) : (
            <FileText className="w-5 h-5 text-gray-500" />
          )}
        </div>

        <div className="space-y-1">
          <h3 className="text-base font-semibold text-gray-900">
            {title}
          </h3>
          <p className="text-sm text-gray-500">
            {subtitle}
          </p>
        </div>

        <Button
          variant="outline"
          size="sm"
          className="cursor-pointer w-full mt-2"
          onClick={handleDownload}
          disabled={isGenerating || !reportId}
        >
          {isGenerating ? (
            <>
              <div className="w-4 h-4 mr-2 border-2 border-gray-400 border-t-transparent rounded-full animate-spin" />
              Genererar...
            </>
          ) : (
            <>
              <Download className="w-4 h-4 mr-2" />
              Ladda ner
            </>
          )}
        </Button>
      </div>
    </div>
  );
};

const ReportView = () => {
  const navigate = useNavigate();
  const { reportId } = useParams<{ reportId: string }>();
  const [searchParams] = useSearchParams();
  const { toast } = useToast();
  
  const [report, setReport] = useState<ReportData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const [activeSection, setActiveSection] = useState("forvaltningsberattelse");
  // Always false since we don't show toggles in Mina Sidor
  const showAllRR = false;
  const showAllBR = false;
  const [noterBlockToggles, setNoterBlockToggles] = useState<Record<string, boolean>>({});
  const [showAllInk2, setShowAllInk2] = useState(false);
  
  // Signering status
  const [signeringStatus, setSigneringStatus] = useState<SigneringStatusData | null>(null);
  const [signeringLoading, setSigneringLoading] = useState(false);
  const [resendingEmail, setResendingEmail] = useState<string | null>(null);
  
  // Company/fiscal year selection
  const [companies, setCompanies] = useState<CompanyOption[]>([]);
  const [fiscalYears, setFiscalYears] = useState<FiscalYearOption[]>([]);
  const [selectedCompany, setSelectedCompany] = useState<string>("");
  const [selectedFiscalYear, setSelectedFiscalYear] = useState<string>("");
  
  // Section refs for scrolling
  const sectionRefs = useRef<Record<string, HTMLDivElement | null>>({});

  useEffect(() => {
    const storedUser = localStorage.getItem("summare_user");
    if (!storedUser) {
      navigate("/");
      return;
    }

    if (reportId) {
      fetchReportData(reportId);
    }
    
    // Fetch user's companies for dropdown
    const user = JSON.parse(storedUser);
    fetchUserCompanies(user.username);
  }, [reportId, navigate]);

  // Update fiscal years when report or companies change
  useEffect(() => {
    if (report && companies.length > 0) {
      const storedUser = localStorage.getItem("summare_user");
      if (storedUser) {
        const user = JSON.parse(storedUser);
        fetch(`${API_BASE_URL}/api/annual-report-data/list-by-user?username=${encodeURIComponent(user.username)}`)
          .then(res => res.json())
          .then(data => {
            if (data.success && data.data) {
              const currentCompany = data.data.find(
                (c: any) => c.organization_number === report.organization_number
              );
              if (currentCompany && currentCompany.reports) {
                setFiscalYears(
                  currentCompany.reports.map((r: any) => ({
                    id: r.id,
                    fiscal_year_start: r.fiscal_year_start,
                    fiscal_year_end: r.fiscal_year_end,
                    label: `${r.fiscal_year_start} - ${r.fiscal_year_end}`,
                  }))
                );
              }
            }
          });
      }
    }
  }, [report, companies]);

  const fetchReportData = async (id: string) => {
    setIsLoading(true);
    setError("");

    try {
      const response = await fetch(`${API_BASE_URL}/api/annual-report-data/view/${id}`);
      const data = await response.json();

      if (data.success) {
        setReport(data.data);
        setSelectedCompany(data.data.organization_number);
        setSelectedFiscalYear(id);
      } else {
        setError(data.message || "Kunde inte ladda rapporten.");
      }
    } catch (err) {
      console.error("Error fetching report:", err);
      setError("Ett fel uppstod vid hämtning av rapporten.");
    } finally {
      setIsLoading(false);
    }
  };

  const fetchUserCompanies = async (username: string) => {
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/annual-report-data/list-by-user?username=${encodeURIComponent(username)}`
      );
      const data = await response.json();

      if (data.success && data.data) {
        // Extract unique companies
        const companiesList = data.data.map((c: any) => ({
          organization_number: c.organization_number,
          company_name: c.company_name,
        }));
        setCompanies(companiesList);

        // Extract fiscal years for the current company
        if (report) {
          const currentCompany = data.data.find(
            (c: any) => c.organization_number === report.organization_number
          );
          if (currentCompany && currentCompany.reports) {
            setFiscalYears(
              currentCompany.reports.map((r: any) => ({
                id: r.id,
                fiscal_year_start: r.fiscal_year_start,
                fiscal_year_end: r.fiscal_year_end,
                label: `${r.fiscal_year_start} - ${r.fiscal_year_end}`,
              }))
            );
          }
        }
      }
    } catch (err) {
      console.error("Error fetching companies:", err);
    }
  };

  const handleCompanyChange = (orgNumber: string) => {
    // Find the first report for this company and navigate to it
    const storedUser = localStorage.getItem("summare_user");
    if (storedUser) {
      const user = JSON.parse(storedUser);
      fetch(`${API_BASE_URL}/api/annual-report-data/list-by-user?username=${encodeURIComponent(user.username)}`)
        .then(res => res.json())
        .then(data => {
          if (data.success && data.data) {
            const company = data.data.find((c: any) => c.organization_number === orgNumber);
            if (company && company.reports && company.reports.length > 0) {
              navigate(`/report/${company.reports[0].id}`);
            }
          }
        });
    }
  };

  const handleFiscalYearChange = (id: string) => {
    navigate(`/report/${id}`);
  };

  const handleNavClick = (sectionId: string) => {
    setActiveSection(sectionId);
    const ref = sectionRefs.current[sectionId];
    if (ref) {
      // Get the header height and add some padding
      const headerHeight = 80; // Approximate header height
      const elementPosition = ref.getBoundingClientRect().top;
      const offsetPosition = elementPosition + window.pageYOffset - headerHeight;
      
      window.scrollTo({
        top: offsetPosition,
        behavior: "smooth"
      });
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("summare_user");
    navigate("/");
  };

  // Fetch signing status when report is loaded
  useEffect(() => {
    if (reportId) {
      fetchSigneringStatus(reportId);
    }
  }, [reportId]);

  // Poll for signing status updates every 30 seconds when on Signeringsstatus section
  useEffect(() => {
    if (reportId && activeSection === "signeringsstatus") {
      const interval = setInterval(() => {
        fetchSigneringStatus(reportId, true); // silent refresh
      }, 30000);
      return () => clearInterval(interval);
    }
  }, [reportId, activeSection]);

  const fetchSigneringStatus = async (id: string, silent: boolean = false) => {
    if (!silent) {
      setSigneringLoading(true);
    }
    try {
      const response = await fetch(`${API_BASE_URL}/api/signing-status/by-report/${id}`);
      if (response.ok) {
        const data = await response.json();
        if (data.success) {
          setSigneringStatus(data);
        }
      }
    } catch (err) {
      console.error("Error fetching signing status:", err);
    } finally {
      if (!silent) {
        setSigneringLoading(false);
      }
    }
  };

  const handleCopyLink = async (url: string, signerName: string) => {
    if (!url) {
      toast({
        description: `Ingen signeringslänk tillgänglig för ${signerName}.`,
        duration: 4000,
      });
      return;
    }
    try {
      await navigator.clipboard.writeText(url);
      toast({
        description: `Signeringslänk för ${signerName} kopierad till urklipp.`,
        duration: 4000,
      });
    } catch (err) {
      console.error("Failed to copy:", err);
      toast({
        description: "Kunde inte kopiera länk. Försök igen.",
        duration: 4000,
      });
    }
  };

  const handleResendInvitation = async (email: string, name: string) => {
    if (!reportId) return;
    
    setResendingEmail(email);
    try {
      const response = await fetch(`${API_BASE_URL}/api/signing/resend-invitation`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          report_id: reportId, 
          email, 
          name,
          company_name: report?.company_name || '',
          fiscal_year_start: report?.fiscal_year_start || '',
          fiscal_year_end: report?.fiscal_year_end || '',
        }),
      });
      
      if (response.ok) {
        toast({
          description: `Påminnelse skickad till ${email}`,
          duration: 4000,
        });
      } else {
        throw new Error('Failed to resend');
      }
    } catch (err) {
      console.error("Error resending invitation:", err);
      toast({
        description: 'Kunde inte skicka påminnelse. Försök igen.',
        duration: 4000,
      });
    } finally {
      setResendingEmail(null);
    }
  };

  const handleUpdateEmail = async (signerType: 'befattningshavare' | 'revisor', index: number, oldEmail: string, newEmail: string, name: string) => {
    if (!reportId) return;
    
    try {
      const response = await fetch(`${API_BASE_URL}/api/signing/update-email`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          report_id: reportId,
          old_email: oldEmail,
          new_email: newEmail,
          signer_type: signerType,
          name,
        }),
      });
      
      if (response.ok) {
        // Update local state
        if (signeringStatus) {
          const updated = { ...signeringStatus };
          if (signerType === 'befattningshavare' && updated.signeringData.befattningshavare[index]) {
            updated.signeringData.befattningshavare[index].email = newEmail;
          } else if (signerType === 'revisor' && updated.signeringData.revisor[index]) {
            updated.signeringData.revisor[index].email = newEmail;
          }
          setSigneringStatus(updated);
        }
        setEditingEmail(null);
      } else {
        throw new Error('Failed to update');
      }
    } catch (err) {
      console.error("Error updating email:", err);
      alert('Kunde inte uppdatera email. Försök igen.');
    }
  };

  // Helper functions for display (matching AnnualReportPreview logic)
  const formatAmount = (amount: number | null): string => {
    if (amount === null || amount === undefined) return "";
    if (amount === 0) return "0 kr";
    return `${new Intl.NumberFormat("sv-SE", {
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(Math.round(amount))} kr`;
  };

  // Match exactly the getStyleClasses from AnnualReportPreview.tsx
  const getStyleClasses = (style?: string) => {
    const baseClasses = "grid gap-4";
    let additionalClasses = "";
    let inlineStyle: React.CSSProperties = { gridTemplateColumns: "4fr 0.5fr 1fr 1fr" };
    
    // Handle bold styling for header styles only
    if (style === "H0" || style === "H1" || style === "H2" || style === "H3" || 
        style === "S1" || style === "S2" || style === "S3") {
      additionalClasses += " font-semibold";
    }
    
    // Add 14pt padding before H2 and H3 headings
    if (style === "H2" || style === "H3") {
      inlineStyle = { ...inlineStyle, paddingTop: "14pt" };
    }
    
    // Handle specific styling for S1, S2 and S3 (thin grey lines above and below)
    if (style === "S1" || style === "S2" || style === "S3") {
      additionalClasses += " border-t border-b border-gray-200 pt-1 pb-1";
    }
    
    return {
      className: `${baseClasses}${additionalClasses}`,
      style: inlineStyle,
    };
  };

  // Helper function to check if a block group has any content (mirrors AnnualReportPreview)
  const blockGroupHasContent = (data: any[], blockGroup: string): boolean => {
    if (!blockGroup) return true; // Show items without block_group
    
    const blockItems = data.filter(item => item.block_group === blockGroup);
    
    for (const item of blockItems) {
      const isHeading = item.style && ['H0', 'H1', 'H2', 'H3', 'S1', 'S2', 'S3'].includes(item.style);
      if (isHeading) continue; // Skip headings when checking block content
      
      const hasNonZeroAmount = (item.current_amount !== null && item.current_amount !== 0) ||
                              (item.previous_amount !== null && item.previous_amount !== 0);
      const isAlwaysShow = item.always_show === true;
      const hasNoteNumber = item.note_number !== undefined && item.note_number !== null;
      
      // Show if: (has non-zero amount) OR (always_show = true) OR (has note number)
      if (hasNonZeroAmount || isAlwaysShow || hasNoteNumber) {
        return true;
      }
    }
    return false;
  };

  const shouldShowRow = (item: any, showAll: boolean, data: any[]): boolean => {
    const hiddenRowIds = [312, 310, 240, 241];
    if (item.id && hiddenRowIds.includes(Number(item.id))) return false;
    if (item.label?.toUpperCase() === "TILLGÅNGAR") return false;

    if (showAll) return true;

    const isHeading = ["H0", "H1", "H2", "H3", "S1", "S2", "S3"].includes(item.style || "");
    if (isHeading) {
      // Check if any non-heading row in same block_group has values OR note numbers
      if (item.block_group) {
        return blockGroupHasContent(data, item.block_group);
      }
      return true;
    }

    const hasNonZeroAmount =
      (item.current_amount !== null && item.current_amount !== 0) ||
      (item.previous_amount !== null && item.previous_amount !== 0);
    const isAlwaysShow = item.always_show === true;
    const hasNoteNumber = item.note_number !== undefined && item.note_number !== null;

    // Show if: (has non-zero amount) OR (always_show = true) OR (has note number)
    return hasNonZeroAmount || isAlwaysShow || hasNoteNumber;
  };

  // Noter styling helper (3-column grid for notes)
  const getNoterStyleClasses = (style?: string) => {
    const baseClasses = "grid gap-4";
    let additionalClasses = "";
    const s = style || "NORMAL";
    
    // Bold styling for headers and sum rows
    const boldStyles = ['H0', 'H1', 'H2', 'H3', 'S1', 'S2', 'S3'];
    if (boldStyles.includes(s)) {
      additionalClasses += " font-semibold";
    }
    
    // Lines for S2/S3 rows
    const lineStyles = ['S2', 'S3'];
    if (lineStyles.includes(s)) {
      additionalClasses += " border-t border-b border-gray-200 pt-1 pb-1";
    }
    
    // Padding before H2/H3 headings
    let inlineStyle: React.CSSProperties = { gridTemplateColumns: "4fr 1fr 1fr" };
    if (s === "H2" || s === "H3") {
      inlineStyle = { ...inlineStyle, paddingTop: "10pt" };
    }
    
    return {
      className: `${baseClasses}${additionalClasses}`,
      style: inlineStyle,
    };
  };

  // Helper to check if a noter row should be visible
  const shouldShowNoterRow = (item: any, toggleOn: boolean): boolean => {
    // Always show if always_show is true
    if (item.always_show) return true;
    
    // Show if has non-zero amounts
    const hasNonZero = 
      (item.current_amount !== null && item.current_amount !== 0) ||
      (item.previous_amount !== null && item.previous_amount !== 0);
    if (hasNonZero) return true;
    
    // Show toggle_show rows only if toggle is on
    if (item.toggle_show) return toggleOn;
    
    return false;
  };

  // Group noter items by block
  const getGroupedNoterData = () => {
    if (!report?.noter_data) return {};
    
    const grouped: Record<string, any[]> = {};
    report.noter_data.forEach((item: any) => {
      const block = item.block || 'OTHER';
      if (!grouped[block]) grouped[block] = [];
      grouped[block].push(item);
    });
    
    // Sort each block by row_id
    Object.keys(grouped).forEach(block => {
      grouped[block].sort((a, b) => (a.row_id || 0) - (b.row_id || 0));
    });
    
    return grouped;
  };

  // Get sorted block keys
  const getSortedBlockKeys = (grouped: Record<string, any[]>): string[] => {
    const allBlocks = Object.keys(grouped);
    return [
      ...NOTE_ORDER.filter(b => allBlocks.includes(b)),
      ...allBlocks.filter(b => !NOTE_ORDER.includes(b))
    ];
  };

  // Check if a block has any non-zero amounts (for deciding if block should be shown)
  // This checks if there's actual DATA in the block, not just always_show rows
  const blockHasNonZeroAmounts = (blockItems: any[]): boolean => {
    return blockItems.some(item => {
      const hasNonZero = 
        (item.current_amount !== null && item.current_amount !== undefined && item.current_amount !== 0) ||
        (item.previous_amount !== null && item.previous_amount !== undefined && item.previous_amount !== 0);
      return hasNonZero;
    });
  };

  // Get note number for a BR/RR row (now served from backend)
  const getNoteNumberForRow = (item: any): string => {
    // Backend now calculates and includes note_number in the merged data
    if (item.note_number !== undefined && item.note_number !== null) {
      return item.note_number.toString();
    }
    return '';
  };

  // Calculate note numbers for visible blocks
  const calculateNoteNumbers = (grouped: Record<string, any[]>): Record<string, number> => {
    const blocks = getSortedBlockKeys(grouped);
    let noteNumber = 3; // Start at 3 since NOT1=1, NOT2=2
    const numbers: Record<string, number> = { NOT1: 1, NOT2: 2 };
    
    blocks.forEach(block => {
      if (block === 'NOT1' || block === 'NOT2') return;
      
      const blockItems = grouped[block];
      
      // Check if block has any non-zero amounts
      const hasNonZeroAmounts = blockHasNonZeroAmounts(blockItems);
      
      // Blocks in BLOCKS_TO_HIDE_IF_ZERO need non-zero amounts to get a number
      if (BLOCKS_TO_HIDE_IF_ZERO.includes(block)) {
        if (hasNonZeroAmounts) {
          numbers[block] = noteNumber++;
        }
      } else if (block === 'SAKERHET') {
        // SAKERHET needs visibility toggle AND non-zero amounts
        const isVisible = noterBlockToggles['sakerhet-visibility'] === true;
        if (isVisible && hasNonZeroAmounts) {
          numbers[block] = noteNumber++;
        }
      } else if (block === 'EVENTUAL') {
        // EVENTUAL needs visibility toggle AND non-zero amounts
        const isVisible = noterBlockToggles['eventual-visibility'] === true;
        if (isVisible && hasNonZeroAmounts) {
          numbers[block] = noteNumber++;
        }
      } else if (block === 'OVRIGA') {
        // OVRIGA needs visibility toggle
        const isVisible = noterBlockToggles['ovriga-visibility'] === true;
        if (isVisible) {
          numbers[block] = noteNumber++;
        }
      } else if (hasNonZeroAmounts) {
        // Other blocks only get a number if they have data
        numbers[block] = noteNumber++;
      }
    });
    
    return numbers;
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="flex items-center gap-3 text-gray-500">
          <svg className="animate-spin h-6 w-6" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
          </svg>
          Laddar rapport...
        </div>
      </div>
    );
  }

  if (error || !report) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-500 mb-4">{error || "Rapporten kunde inte hittas."}</p>
          <Button onClick={() => navigate("/mina-sidor")}>Tillbaka till Mina sidor</Button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 flex">
      {/* Left Navigation Sidebar */}
      <aside className="w-64 bg-white border-r border-gray-200 flex-shrink-0 fixed left-0 top-0 bottom-0 overflow-y-auto">
        <div className="p-6">
          <a href="/" className="text-2xl font-bold text-summare-navy">
            Summare
          </a>
        </div>
        
        <nav className="px-4 pb-6">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const isActive = activeSection === item.id;
            
            return (
              <button
                key={item.id}
                onClick={() => handleNavClick(item.id)}
                className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-left transition-colors ${
                  isActive
                    ? "bg-summare-navy text-white"
                    : "text-gray-600 hover:bg-gray-100"
                }`}
              >
                <Icon className="w-5 h-5 flex-shrink-0" />
                <span className="font-medium text-sm">{item.label}</span>
              </button>
            );
          })}
        </nav>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 ml-64">
        {/* Top Header */}
        <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
          <div className="px-6 py-4 flex items-center justify-between">
            <div className="flex items-center gap-4">
              {/* Company Dropdown */}
              <Select value={selectedCompany} onValueChange={handleCompanyChange}>
                <SelectTrigger className="w-[280px]">
                  <SelectValue placeholder="Välj företag">
                    {report?.company_name || "Välj företag"}
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  {companies.map((company) => (
                    <SelectItem key={company.organization_number} value={company.organization_number}>
                      {company.company_name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              {/* Fiscal Year Dropdown */}
              <Select value={selectedFiscalYear} onValueChange={handleFiscalYearChange}>
                <SelectTrigger className="w-[230px]">
                  <SelectValue placeholder="Välj räkenskapsår">
                    {report?.fiscal_year_start && report?.fiscal_year_end
                      ? `${report.fiscal_year_start} - ${report.fiscal_year_end}`
                      : "Välj räkenskapsår"}
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  {fiscalYears.map((fy) => (
                    <SelectItem key={fy.id} value={fy.id}>
                      {fy.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="flex items-center gap-4">
              <a href="#" className="text-sm text-gray-500 hover:text-gray-700">
                Support
              </a>
              <Popover>
                <PopoverTrigger asChild>
                  <Button variant="ghost" size="sm" className="flex items-center gap-2">
                    <User className="w-5 h-5" />
                    <ChevronDown className="w-4 h-4" />
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-48" align="end">
                  <div className="space-y-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="w-full justify-start"
                      onClick={() => navigate("/mina-sidor")}
                    >
                      Mina sidor
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="w-full justify-start text-red-600"
                      onClick={handleLogout}
                    >
                      Logga ut
                    </Button>
                  </div>
                </PopoverContent>
              </Popover>
            </div>
          </div>
        </header>

        {/* Content Area */}
        <div className="p-6 max-w-5xl mx-auto">
          {/* Signeringsstatus Section */}
          <div
            ref={(el) => (sectionRefs.current["signeringsstatus"] = el)}
            className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6"
          >
            <div className="mb-6">
              <h2 className="text-xl font-semibold text-gray-900">Signeringsstatus</h2>
              <p className="text-sm text-gray-600 mt-2 leading-relaxed">
                Din årsredovisning har skickats iväg för signering till följande befattningshavare och revisor om bolaget har en sådan. Du kan i statuskolumnen följa vilka befattningshavare som har signerat och vilka vi fortfarande inväntar signering ifrån. Du har möjlighet att skicka påminnelse via mail och du kan också kopiera länken <Link2 className="w-3 h-3 inline mx-0.5" /> och skicka som textmeddelande. Kontrollera gärna mailadresser och ändra vid fel och skicka isåfall mail igen genom att klicka på <Send className="w-3 h-3 inline mx-0.5" />
              </p>
            </div>

            {signeringLoading ? (
              <div className="flex items-center justify-center py-8">
                <div className="w-8 h-8 border-2 border-gray-300 border-t-blue-600 rounded-full animate-spin" />
              </div>
            ) : signeringStatus?.signeringData?.befattningshavare?.length || signeringStatus?.signeringData?.revisor?.length ? (
              <div className="space-y-8">
                {/* Befattningshavare Section */}
                {signeringStatus.signeringData.befattningshavare?.length > 0 && (
                  <div>
                    <h3 className="text-lg font-semibold text-gray-900 mb-4">Befattningshavare</h3>
                    
                    {/* Column Headers */}
                    <div className="grid grid-cols-12 gap-4 text-sm font-medium text-gray-500 mb-2">
                      <div className="col-span-3">Namn</div>
                      <div className="col-span-3">Roll</div>
                      <div className="col-span-3">Email</div>
                      <div className="col-span-1 text-center">Länk</div>
                      <div className="col-span-1 text-center">Skicka</div>
                      <div className="col-span-1 text-center">Status</div>
                    </div>
                    
                    <div className="space-y-3">
                      {signeringStatus.signeringData.befattningshavare.map((person, index) => {
                        const fullName = `${person.fornamn} ${person.efternamn}`.trim();
                        const isSigned = person.status === 'signed';
                        
                        return (
                          <div
                            key={`befattning-${index}`}
                            className="grid grid-cols-12 gap-4 items-center"
                          >
                            {/* Namn - combined förnamn + efternamn */}
                            <div className="col-span-3">
                              <span className="text-sm text-gray-900">{fullName || '-'}</span>
                            </div>
                            
                            {/* Roll - plain text */}
                            <div className="col-span-3">
                              <span className="text-sm text-gray-600">{person.roll || '-'}</span>
                            </div>
                            
                            {/* Email - editable input */}
                            <div className="col-span-3">
                              <Input
                                value={person.email || ''}
                                onChange={(e) => {
                                  // Update local state
                                  const newBefattningshavare = [...(signeringStatus.signeringData.befattningshavare || [])];
                                  newBefattningshavare[index] = { ...newBefattningshavare[index], email: e.target.value };
                                  setSigneringStatus({
                                    ...signeringStatus,
                                    signeringData: {
                                      ...signeringStatus.signeringData,
                                      befattningshavare: newBefattningshavare
                                    }
                                  });
                                }}
                                onBlur={(e) => {
                                  // Save on blur if changed
                                  if (e.target.value !== person.email) {
                                    handleUpdateEmail('befattningshavare', index, person.email || '', e.target.value, fullName);
                                  }
                                }}
                                placeholder="Email"
                                className="h-8 text-sm"
                              />
                            </div>
                            
                            {/* Länk button */}
                            <div className="col-span-1 flex justify-center">
                              <button
                                className="text-gray-400 hover:text-blue-600 p-1"
                                onClick={() => handleCopyLink(person.signing_url || '', fullName)}
                                title="Kopiera signeringslänk"
                              >
                                <Link2 className="w-5 h-5" />
                              </button>
                            </div>
                            
                            {/* Skicka button */}
                            <div className="col-span-1 flex justify-center">
                              {!isSigned && person.email ? (
                                <button
                                  className="text-gray-400 hover:text-blue-600 p-1"
                                  onClick={() => handleResendInvitation(person.email, fullName)}
                                  disabled={resendingEmail === person.email}
                                  title="Skicka påminnelse"
                                >
                                  {resendingEmail === person.email ? (
                                    <div className="w-5 h-5 border-2 border-gray-300 border-t-blue-600 rounded-full animate-spin" />
                                  ) : (
                                    <Send className="w-5 h-5" />
                                  )}
                                </button>
                              ) : (
                                <Send className="w-5 h-5 text-gray-200" />
                              )}
                            </div>
                            
                            {/* Status */}
                            <div className="col-span-1 flex justify-center">
                              <span
                                className={`text-xs font-medium px-3 py-1.5 rounded ${
                                  isSigned
                                    ? 'bg-green-100 text-green-700'
                                    : 'bg-yellow-100 text-yellow-700'
                                }`}
                              >
                                {isSigned ? 'Signerad' : 'Skickad'}
                              </span>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* Revisor Section - only show if company has revisor */}
                {signeringStatus.signeringData.revisor?.length > 0 && (
                  <div>
                    <h3 className="text-lg font-semibold text-gray-900 mb-4">Revisor</h3>
                    
                    {/* Column Headers */}
                    <div className="grid grid-cols-12 gap-4 text-sm font-medium text-gray-500 mb-2">
                      <div className="col-span-3">Namn</div>
                      <div className="col-span-3">Revisionsbolag</div>
                      <div className="col-span-3">Email</div>
                      <div className="col-span-1 text-center">Länk</div>
                      <div className="col-span-1 text-center">Skicka</div>
                      <div className="col-span-1 text-center">Status</div>
                    </div>
                    
                    <div className="space-y-3">
                      {signeringStatus.signeringData.revisor.map((person, index) => {
                        const fullName = `${person.fornamn} ${person.efternamn}`.trim();
                        const isSigned = person.status === 'signed';
                        
                        return (
                          <div
                            key={`revisor-${index}`}
                            className="grid grid-cols-12 gap-4 items-center"
                          >
                            {/* Namn - combined förnamn + efternamn */}
                            <div className="col-span-3">
                              <span className="text-sm text-gray-900">{fullName || '-'}</span>
                            </div>
                            
                            {/* Revisionsbolag - plain text */}
                            <div className="col-span-3">
                              <span className="text-sm text-gray-600">
                                {person.revisionsbolag || signeringStatus.signeringData.ValtRevisionsbolag || '-'}
                              </span>
                            </div>
                            
                            {/* Email - editable input */}
                            <div className="col-span-3">
                              <Input
                                value={person.email || ''}
                                onChange={(e) => {
                                  // Update local state
                                  const newRevisor = [...(signeringStatus.signeringData.revisor || [])];
                                  newRevisor[index] = { ...newRevisor[index], email: e.target.value };
                                  setSigneringStatus({
                                    ...signeringStatus,
                                    signeringData: {
                                      ...signeringStatus.signeringData,
                                      revisor: newRevisor
                                    }
                                  });
                                }}
                                onBlur={(e) => {
                                  // Save on blur if changed
                                  if (e.target.value !== person.email) {
                                    handleUpdateEmail('revisor', index, person.email || '', e.target.value, fullName);
                                  }
                                }}
                                placeholder="Email"
                                className="h-8 text-sm"
                              />
                            </div>
                            
                            {/* Länk button */}
                            <div className="col-span-1 flex justify-center">
                              <button
                                className="text-gray-400 hover:text-blue-600 p-1"
                                onClick={() => handleCopyLink(person.signing_url || '', fullName)}
                                title="Kopiera signeringslänk"
                              >
                                <Link2 className="w-5 h-5" />
                              </button>
                            </div>
                            
                            {/* Skicka button */}
                            <div className="col-span-1 flex justify-center">
                              {!isSigned && person.email ? (
                                <button
                                  className="text-gray-400 hover:text-blue-600 p-1"
                                  onClick={() => handleResendInvitation(person.email, fullName)}
                                  disabled={resendingEmail === person.email}
                                  title="Skicka påminnelse"
                                >
                                  {resendingEmail === person.email ? (
                                    <div className="w-5 h-5 border-2 border-gray-300 border-t-blue-600 rounded-full animate-spin" />
                                  ) : (
                                    <Send className="w-5 h-5" />
                                  )}
                                </button>
                              ) : (
                                <Send className="w-5 h-5 text-gray-200" />
                              )}
                            </div>
                            
                            {/* Status */}
                            <div className="col-span-1 flex justify-center">
                              <span
                                className={`text-xs font-medium px-3 py-1.5 rounded ${
                                  isSigned
                                    ? 'bg-green-100 text-green-700'
                                    : 'bg-yellow-100 text-yellow-700'
                                }`}
                              >
                                {isSigned ? 'Signerad' : 'Skickad'}
                              </span>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-center py-8">
                <p className="text-gray-500">
                  Ingen signeringsinformation tillgänglig än. Signeringsdata sparas när årsredovisningen skickas för signering.
                </p>
              </div>
            )}
          </div>

          {/* Förvaltningsberättelse Section */}
          <div
            ref={(el) => (sectionRefs.current["forvaltningsberattelse"] = el)}
            className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6"
          >
            <div className="mb-6">
              <h2 className="text-xl font-semibold text-gray-900">Förvaltningsberättelse</h2>
            </div>

            {/* Verksamheten */}
            <section className="mb-6">
              <h3 className="text-lg font-semibold text-gray-800 mb-2">Verksamheten</h3>
              
              <h4 className="text-base font-medium text-gray-700 mb-1" style={{ paddingTop: '4pt' }}>Allmänt om verksamheten</h4>
              <p className="text-sm text-gray-600 mb-4">
                {report.fb_data?.verksamheten?.allmant_om_verksamheten || 'Ingen beskrivning tillgänglig.'}
              </p>
              
              <h4 className="text-base font-medium text-gray-700 mb-1" style={{ paddingTop: '4pt' }}>Väsentliga händelser under räkenskapsåret</h4>
              <p className="text-sm text-gray-600">
                {report.fb_data?.verksamheten?.vasentliga_handelser || 'Inga väsentliga händelser under året.'}
              </p>
            </section>

            {/* Flerårsöversikt */}
            {report.fb_data?.flerarsoversikt && (
              <section className="mb-6">
                <h3 className="text-lg font-semibold text-gray-800 mb-2">Flerårsöversikt</h3>
                <p className="text-xs text-gray-500 mb-2">Belopp i tkr</p>
                
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b">
                      <th className="text-left py-2 font-medium"></th>
                      {report.fb_data.flerarsoversikt.years?.map((year: number, i: number) => (
                        <th key={i} className="text-right py-2 font-medium w-20">{year}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    <tr className="border-b">
                      <td className="py-2 text-gray-600">Omsättning</td>
                      {report.fb_data.flerarsoversikt.omsattning?.map((val: number, i: number) => (
                        <td key={i} className="text-right py-2">
                          {new Intl.NumberFormat('sv-SE').format(val || 0)}
                        </td>
                      ))}
                    </tr>
                    <tr className="border-b">
                      <td className="py-2 text-gray-600">Resultat efter finansiella poster</td>
                      {report.fb_data.flerarsoversikt.resultat_efter_finansiella_poster?.map((val: number, i: number) => (
                        <td key={i} className="text-right py-2">
                          {new Intl.NumberFormat('sv-SE').format(val || 0)}
                        </td>
                      ))}
                    </tr>
                    <tr className="border-b">
                      <td className="py-2 text-gray-600">Balansomslutning</td>
                      {report.fb_data.flerarsoversikt.balansomslutning?.map((val: number, i: number) => (
                        <td key={i} className="text-right py-2">
                          {new Intl.NumberFormat('sv-SE').format(val || 0)}
                        </td>
                      ))}
                    </tr>
                    <tr>
                      <td className="py-2 text-gray-600">Soliditet (%)</td>
                      {report.fb_data.flerarsoversikt.soliditet?.map((val: number, i: number) => (
                        <td key={i} className="text-right py-2">
                          {Math.round(val || 0)}
                        </td>
                      ))}
                    </tr>
                  </tbody>
                </table>
              </section>
            )}

            {/* Förändringar i eget kapital */}
            {report.fb_data?.fb_table && report.fb_data.fb_table.length > 0 && (
              <section className="mb-6">
                <h3 className="text-lg font-semibold text-gray-800 mb-2">Förändringar i eget kapital</h3>
                
                {(() => {
                  const fbTable = report.fb_data.fb_table;
                  
                  // Check which columns have non-zero values
                  const hasNonZeroValues = {
                    aktiekapital: fbTable.some((row: any) => row.aktiekapital !== 0 && row.aktiekapital !== null),
                    reservfond: fbTable.some((row: any) => row.reservfond !== 0 && row.reservfond !== null),
                    uppskrivningsfond: fbTable.some((row: any) => row.uppskrivningsfond !== 0 && row.uppskrivningsfond !== null),
                    balanserat_resultat: fbTable.some((row: any) => row.balanserat_resultat !== 0 && row.balanserat_resultat !== null),
                    arets_resultat: fbTable.some((row: any) => row.arets_resultat !== 0 && row.arets_resultat !== null),
                    total: fbTable.some((row: any) => row.total !== 0 && row.total !== null)
                  };
                  
                  const formatValue = (val: number) => {
                    if (val === null || val === undefined || val === 0) return '';
                    return new Intl.NumberFormat('sv-SE', {
                      minimumFractionDigits: 0,
                      maximumFractionDigits: 0
                    }).format(Math.round(val));
                  };
                  
                  return (
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm table-fixed">
                        <thead>
                          <tr className="border-b">
                            <th className="text-left py-2 font-medium" style={{ width: '200px' }}></th>
                            {hasNonZeroValues.aktiekapital && (
                              <th className="text-right py-2 font-medium" style={{ minWidth: '100px' }}>Aktiekapital</th>
                            )}
                            {hasNonZeroValues.reservfond && (
                              <th className="text-right py-2 font-medium" style={{ minWidth: '100px' }}>Reservfond</th>
                            )}
                            {hasNonZeroValues.uppskrivningsfond && (
                              <th className="text-right py-2 font-medium" style={{ minWidth: '120px' }}>Uppskrivningsfond</th>
                            )}
                            {hasNonZeroValues.balanserat_resultat && (
                              <th className="text-right py-2 font-medium" style={{ minWidth: '130px' }}>Balanserat resultat</th>
                            )}
                            {hasNonZeroValues.arets_resultat && (
                              <th className="text-right py-2 font-medium" style={{ minWidth: '110px' }}>Årets resultat</th>
                            )}
                            {hasNonZeroValues.total && (
                              <th className="text-right py-2 font-medium" style={{ minWidth: '100px' }}>Summa</th>
                            )}
                          </tr>
                        </thead>
                        <tbody>
                          {fbTable.map((row: any, index: number) => {
                            // Always hide "Redovisat värde" row (id=14)
                            if (row.id === 14) return null;
                            
                            // Show rows 1 (Belopp vid årets ingång) and 13 (Belopp vid årets utgång)
                            // and any row with non-zero values
                            const hasValues = row.aktiekapital || row.reservfond || 
                              row.uppskrivningsfond || row.balanserat_resultat || row.arets_resultat;
                            const isKeyRow = row.id === 1 || row.id === 13;
                            
                            if (!isKeyRow && !hasValues) return null;
                            
                            // Only row 13 (Belopp vid årets utgång) is bold, not shaded
                            const isSummaryRow = row.id === 13;
                            
                            return (
                              <tr key={row.id || index} className={`border-b ${isSummaryRow ? 'font-semibold' : ''}`}>
                                <td className="py-2 text-gray-600">{row.label}</td>
                                {hasNonZeroValues.aktiekapital && (
                                  <td className="text-right py-2">{formatValue(row.aktiekapital)}</td>
                                )}
                                {hasNonZeroValues.reservfond && (
                                  <td className="text-right py-2">{formatValue(row.reservfond)}</td>
                                )}
                                {hasNonZeroValues.uppskrivningsfond && (
                                  <td className="text-right py-2">{formatValue(row.uppskrivningsfond)}</td>
                                )}
                                {hasNonZeroValues.balanserat_resultat && (
                                  <td className="text-right py-2">{formatValue(row.balanserat_resultat)}</td>
                                )}
                                {hasNonZeroValues.arets_resultat && (
                                  <td className="text-right py-2">{formatValue(row.arets_resultat)}</td>
                                )}
                                {hasNonZeroValues.total && (
                                  <td className="text-right py-2">{formatValue(row.total)}</td>
                                )}
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  );
                })()}
              </section>
            )}

            {/* Resultatdisposition */}
            {report.fb_data?.fb_table && report.fb_data.fb_table.length > 0 && (
              <section>
                <h3 className="text-lg font-semibold text-gray-800 mb-2" style={{ paddingTop: '8pt' }}>Resultatdisposition</h3>
                
                {(() => {
                  const fbTable = report.fb_data.fb_table;
                  const vars = report.fb_data.fb_variables || {};
                  
                  // Get values from row 13 (Belopp vid årets utgång)
                  const row13 = fbTable.find((r: any) => r.id === 13);
                  const balResultat = row13?.balanserat_resultat || 0;
                  const aretsResultat = row13?.arets_resultat || 0;
                  const summa = balResultat + aretsResultat;
                  
                  // Get utdelning - first from fb_data.arets_utdelning, then from fb_variables
                  const utdelning = report.fb_data.arets_utdelning || vars.fb_aretsresultat_utdelning || vars.fb_arets_utdelning || 0;
                  
                  // Balanseras i ny räkning = Summa - Utdelning
                  const balanseras = summa - utdelning;
                  
                  const formatAmount = (val: number) => {
                    if (val === null || val === undefined) return '0 kr';
                    return new Intl.NumberFormat('sv-SE', {
                      minimumFractionDigits: 0,
                      maximumFractionDigits: 0
                    }).format(Math.round(val)) + ' kr';
                  };
                  
                  return (
                    <div className="text-sm text-gray-600 space-y-2">
                      <p className="text-gray-700" style={{ paddingTop: '10pt' }}>Styrelsen föreslår att till förfogande stående vinstmedel:</p>
                      
                      <table className="w-full max-w-md">
                        <tbody>
                          <tr>
                            <td className="py-1">Balanserat resultat</td>
                            <td className="text-right py-1">{formatAmount(balResultat)}</td>
                          </tr>
                          <tr>
                            <td className="py-1">Årets resultat</td>
                            <td className="text-right py-1">{formatAmount(aretsResultat)}</td>
                          </tr>
                          <tr className="border-t border-gray-200">
                            <td className="py-1 font-medium">Summa</td>
                            <td className="text-right py-1 font-medium">{formatAmount(summa)}</td>
                          </tr>
                        </tbody>
                      </table>
                      
                      <p className="text-gray-700" style={{ paddingTop: '20pt' }}>Disponeras enligt följande:</p>
                      
                      <table className="w-full max-w-md">
                        <tbody>
                          <tr>
                            <td className="py-1">Utdelas till aktieägare</td>
                            <td className="text-right py-1">{formatAmount(utdelning)}</td>
                          </tr>
                          <tr>
                            <td className="py-1">Balanseras i ny räkning</td>
                            <td className="text-right py-1">{formatAmount(balanseras)}</td>
                          </tr>
                          <tr className="border-t border-gray-200">
                            <td className="py-1 font-medium">Summa</td>
                            <td className="text-right py-1 font-medium">{formatAmount(summa)}</td>
                          </tr>
                        </tbody>
                      </table>
                      
                      {/* Försiktighetsregeln text when dividend > 0 */}
                      {utdelning > 0 && (
                        <p className="text-sm" style={{ paddingTop: '20pt' }}>
                          Styrelsen anser att förslaget är förenligt med försiktighetsregeln i 17 kap. 3 § aktiebolagslagen enligt följande redogörelse. Styrelsens uppfattning är att vinstutdelningen är försvarlig med hänsyn till de krav verksamhetens art, omfattning och risk ställer på storleken på det egna kapitalet, bolagets konsolideringsbehov, likviditet och ställning i övrigt.
                        </p>
                      )}
                    </div>
                  );
                })()}
              </section>
            )}
          </div>

          {/* Resultaträkning Section */}
          <div
            ref={(el) => (sectionRefs.current["resultatrakning"] = el)}
            className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6"
          >
            <div className="mb-6">
              <h2 className="text-xl font-semibold text-gray-900">Resultaträkning</h2>
            </div>

            {/* Column Headers */}
            <div
              className="grid gap-4 text-sm text-gray-500 border-b pb-2 font-semibold"
              style={{ gridTemplateColumns: "4fr 0.5fr 1fr 1fr" }}
            >
              <span></span>
              <span className="text-right">Not</span>
              <span className="text-right">{report.fiscal_year}</span>
              <span className="text-right">{report.fiscal_year - 1}</span>
            </div>

            {/* RR Rows */}
            <div className="mt-2 space-y-0">
              {report.rr_data.map((item, index) => {
                if (!shouldShowRow(item, showAllRR, report.rr_data)) {
                  return null;
                }

                const styleClasses = getStyleClasses(item.style);
                
                // RR-specific: add 6pt padding above S1 and S2 rows
                let rrStyle = { ...styleClasses.style };
                if (item.style === "S1" || item.style === "S2") {
                  rrStyle = { ...rrStyle, marginTop: "6pt" };
                }

                return (
                  <div
                    key={item.id || index}
                    className={`${styleClasses.className} ${item.level === 0 ? "border-b pb-1" : ""} py-1`}
                    style={rrStyle}
                  >
                    <span className="text-gray-600 flex items-center justify-between">
                      <span>{item.label}</span>
                      {/* VISA button for rows with account_details */}
                      {item.show_tag && item.account_details?.length > 0 &&
                       item.current_amount !== null && Math.abs(item.current_amount) > 0 && (
                        <Popover>
                          <PopoverTrigger asChild>
                            <Button variant="outline" size="sm" className="ml-2 h-5 px-2 text-xs">
                              VISA
                            </Button>
                          </PopoverTrigger>
                          <PopoverContent className="w-[520px] p-4 bg-white border shadow-lg">
                            <PopoverClose className="absolute top-2 right-2 p-1 hover:bg-gray-100 rounded">
                              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12"/>
                              </svg>
                            </PopoverClose>
                            <div className="space-y-3">
                              <h4 className="font-medium text-sm pr-6">Detaljer för {item.label}</h4>
                              <div className="overflow-x-auto">
                                <table className="w-full text-sm">
                                  <thead>
                                    <tr className="border-b">
                                      <th className="text-left py-2 w-16">Konto</th>
                                      <th className="text-left py-2">Kontotext</th>
                                      <th className="text-right py-2 w-28">{report.fiscal_year}</th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {item.account_details.map((detail: any, i: number) => (
                                      <tr key={i} className="border-b">
                                        <td className="py-2 w-16">{detail.account_id}</td>
                                        <td className="py-2">{detail.account_text || ""}</td>
                                        <td className="text-right py-2 w-28 whitespace-nowrap">
                                          {new Intl.NumberFormat("sv-SE", { minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(Math.round(detail.balance))} kr
                                        </td>
                                      </tr>
                                    ))}
                                    <tr className="border-t border-gray-300 font-semibold">
                                      <td className="py-2">Summa</td>
                                      <td></td>
                                      <td className="text-right py-2 whitespace-nowrap">
                                        {new Intl.NumberFormat("sv-SE", { minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(
                                          Math.round(item.account_details.reduce(
                                            (sum: number, d: any) => sum + (d.balance || 0),
                                            0
                                          ))
                                        )} kr
                                      </td>
                                    </tr>
                                  </tbody>
                                </table>
                              </div>
                            </div>
                          </PopoverContent>
                        </Popover>
                      )}
                    </span>
                    <span className="text-right font-medium text-gray-500">
                      {getNoteNumberForRow(item)}
                    </span>
                    <span className="text-right font-medium">
                      {formatAmount(item.current_amount)}
                    </span>
                    <span className="text-right font-medium">
                      {formatAmount(item.previous_amount)}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Balansräkning Section */}
          <div
            ref={(el) => (sectionRefs.current["balansrakning"] = el)}
            className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6"
          >
            <div className="mb-6">
              <h2 className="text-xl font-semibold text-gray-900">Balansräkning</h2>
            </div>

            {/* Column Headers */}
            <div
              className="grid gap-4 text-sm text-gray-500 border-b pb-2 font-semibold"
              style={{ gridTemplateColumns: "4fr 0.5fr 1fr 1fr" }}
            >
              <span></span>
              <span className="text-right">Not</span>
              <span className="text-right">{report.fiscal_year}-12-31</span>
              <span className="text-right">{report.fiscal_year - 1}-12-31</span>
            </div>

            {/* BR Rows */}
            <div className="mt-2 space-y-0">
              {report.br_data.map((item, index) => {
                // Hide H1 rows in BR
                if (item.style === "H1") {
                  return null;
                }
                
                if (!shouldShowRow(item, showAllBR, report.br_data)) {
                  return null;
                }

                const styleClasses = getStyleClasses(item.style);
                
                // BR-specific: add 6pt padding above S1 and S2 rows
                let brStyle = { ...styleClasses.style };
                if (item.style === "S1" || item.style === "S2") {
                  brStyle = { ...brStyle, marginTop: "6pt" };
                }

                return (
                  <div
                    key={item.id || index}
                    className={`${styleClasses.className} ${item.level === 0 ? "border-b pb-1" : ""} py-1`}
                    style={brStyle}
                  >
                    <span className="text-gray-600 flex items-center justify-between">
                      <span>{item.label}</span>
                      {/* VISA button for rows with account_details */}
                      {item.show_tag && item.account_details?.length > 0 &&
                       item.current_amount !== null && Math.abs(item.current_amount) > 0 && (
                        <Popover>
                          <PopoverTrigger asChild>
                            <Button variant="outline" size="sm" className="ml-2 h-5 px-2 text-xs">
                              VISA
                            </Button>
                          </PopoverTrigger>
                          <PopoverContent className="w-[550px] p-4 bg-white border shadow-lg">
                            <PopoverClose className="absolute top-2 right-2 p-1 hover:bg-gray-100 rounded">
                              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12"/>
                              </svg>
                            </PopoverClose>
                            <div className="space-y-3">
                              <h4 className="font-medium text-sm pr-6">Detaljer för {item.label}</h4>
                              <div className="overflow-x-auto">
                                <table className="w-full text-sm">
                                  <thead>
                                    <tr className="border-b">
                                      <th className="text-left py-2 w-16">Konto</th>
                                      <th className="text-left py-2">Kontotext</th>
                                      <th className="text-right py-2 w-28">{report.fiscal_year}</th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {item.account_details.map((detail: any, i: number) => (
                                      <tr key={i} className="border-b">
                                        <td className="py-2 w-16">{detail.account_id}</td>
                                        <td className="py-2">{detail.account_text || ""}</td>
                                        <td className="text-right py-2 w-28 whitespace-nowrap">
                                          {new Intl.NumberFormat("sv-SE", { minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(Math.round(detail.balance))} kr
                                        </td>
                                      </tr>
                                    ))}
                                    <tr className="border-t border-gray-300 font-semibold">
                                      <td className="py-2">Summa</td>
                                      <td></td>
                                      <td className="text-right py-2 whitespace-nowrap">
                                        {new Intl.NumberFormat("sv-SE", { minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(
                                          Math.round(item.account_details.reduce(
                                            (sum: number, d: any) => sum + (d.balance || 0),
                                            0
                                          ))
                                        )} kr
                                      </td>
                                    </tr>
                                  </tbody>
                                </table>
                              </div>
                            </div>
                          </PopoverContent>
                        </Popover>
                      )}
                    </span>
                    <span className="text-right font-medium text-gray-500">
                      {getNoteNumberForRow(item)}
                    </span>
                    <span className="text-right font-medium">
                      {formatAmount(item.current_amount)}
                    </span>
                    <span className="text-right font-medium">
                      {formatAmount(item.previous_amount)}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Noter Section */}
          <div
            ref={(el) => (sectionRefs.current["noter"] = el)}
            className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6"
          >
            <h2 className="text-xl font-semibold text-gray-900 mb-6">Noter</h2>
            
            {report.noter_data && report.noter_data.length > 0 ? (
              <div className="space-y-6">
                {(() => {
                  const grouped = getGroupedNoterData();
                  const blocks = getSortedBlockKeys(grouped);
                  const noteNumbers = calculateNoteNumbers(grouped);
                  
                  return blocks.map(block => {
                    const blockItems = grouped[block];
                    const noteNumber = noteNumbers[block];
                    
                    // Get block heading
                    const firstItemTitle = blockItems[0]?.row_title || '';
                    const blockHeading = BLOCK_HEADINGS[block] || firstItemTitle || block;
                    const fullHeading = noteNumber 
                      ? `Not ${noteNumber} ${blockHeading}`
                      : `Not ${blockHeading}`;
                    
                    // Check if block has any non-zero amounts
                    const hasNonZeroAmounts = blockHasNonZeroAmounts(blockItems);
                    
                    // Hide blocks with no data using the global constant
                    if (BLOCKS_TO_HIDE_IF_ZERO.includes(block) && !hasNonZeroAmounts) {
                      return null;
                    }
                    
                    // For SAKERHET/EVENTUAL/OVRIGA, check visibility toggle
                    if (block === 'SAKERHET' && noterBlockToggles['sakerhet-visibility'] !== true) {
                      return null;
                    }
                    if (block === 'EVENTUAL' && noterBlockToggles['eventual-visibility'] !== true) {
                      return null;
                    }
                    if (block === 'OVRIGA' && noterBlockToggles['ovriga-visibility'] !== true) {
                      return null;
                    }
                    
                    // Filter visible items (in Mina Sidor we don't use toggles, so always false)
                    const visibleItems = blockItems.filter(item => shouldShowNoterRow(item, false));
                    
                    // Skip blocks with no visible items
                    if (visibleItems.length === 0) {
                      return null;
                    }
                    
                    // Special handling for NOT1 (Redovisningsprinciper - text note with avskrivningstider table)
                    if (block === 'NOT1') {
                      const textItem = blockItems.find((item: any) => item.variable_name === 'redovisning_principer');
                      
                      // Get avskrivningstider from report data
                      const avskrivningstider = report.avskrivningstider || {};
                      
                      // Build avskrivningstider rows from the data
                      const avskrivningsRows: { label: string; years: number | null }[] = [];
                      
                      // Check for each asset type
                      if (avskrivningstider['avskrtid_bygg'] || avskrivningstider['avskrivningstid_bygg']) {
                        avskrivningsRows.push({ label: 'Byggnader & mark', years: avskrivningstider['avskrtid_bygg'] || avskrivningstider['avskrivningstid_bygg'] });
                      }
                      if (avskrivningstider['avskrtid_mask'] || avskrivningstider['avskrivningstid_mask']) {
                        avskrivningsRows.push({ label: 'Maskiner och andra tekniska anläggningar', years: avskrivningstider['avskrtid_mask'] || avskrivningstider['avskrivningstid_mask'] });
                      }
                      if (avskrivningstider['avskrtid_inv'] || avskrivningstider['avskrivningstid_inv']) {
                        avskrivningsRows.push({ label: 'Inventarier, verktyg och installationer', years: avskrivningstider['avskrtid_inv'] || avskrivningstider['avskrivningstid_inv'] });
                      }
                      
                      return (
                        <div key={block} className="pb-4">
                          <h3 className="text-lg font-semibold mb-3">{fullHeading}</h3>
                          <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap mb-4">
                            {textItem?.variable_text || 'Årsredovisningen är upprättad i enlighet med årsredovisningslagen och Bokföringsnämndens allmänna råd (BFNAR 2016:10) om årsredovisning i mindre företag. Avskrivningstider för anläggningstillgångar finns redovisade i tabellen nedan.'}
                          </p>
                          
                          {/* Avskrivningstider table */}
                          {avskrivningsRows.length > 0 && (
                            <div className="mt-4">
                              <div className="grid gap-4 font-semibold border-b border-gray-200 pb-1 mb-1" style={{ gridTemplateColumns: "4fr 1fr" }}>
                                <span className="text-gray-700">Anläggningstillgångar</span>
                                <span className="text-right text-gray-700">År</span>
                              </div>
                              {avskrivningsRows.map((row, idx) => (
                                <div key={idx} className="grid gap-4 py-1 border-b border-gray-100" style={{ gridTemplateColumns: "4fr 1fr" }}>
                                  <span className="text-gray-600">{row.label}</span>
                                  <span className="text-right">{row.years}</span>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      );
                    }
                    
                    // Special handling for NOT2 (Medelantalet anställda)
                    if (block === 'NOT2') {
                      const employeesItem = blockItems.find((item: any) => item.variable_name === 'ant_anstallda');
                      return (
                        <div key={block} className="pb-4">
                          <h3 className="text-lg font-semibold mb-3">{fullHeading}</h3>
                          <div className="grid gap-4 border-b border-gray-200 pb-1" style={{ gridTemplateColumns: "4fr 1fr 1fr" }}>
                            <span className="text-sm text-gray-500"></span>
                            <span className="text-sm text-gray-500 text-right">{report.fiscal_year}</span>
                            <span className="text-sm text-gray-500 text-right">{report.fiscal_year - 1}</span>
                          </div>
                          <div className="grid gap-4 py-1" style={{ gridTemplateColumns: "4fr 1fr 1fr" }}>
                            <span className="text-gray-700">Medelantalet anställda under året</span>
                            <span className="text-right">{employeesItem?.current_amount ?? 0}</span>
                            <span className="text-right">{employeesItem?.previous_amount ?? 0}</span>
                          </div>
                        </div>
                      );
                    }
                    
                    // Regular block rendering
                    return (
                      <div key={block} className="pb-4">
                        {/* Block header */}
                        <div className="mb-3">
                          <h3 className="text-lg font-semibold">{fullHeading}</h3>
                        </div>
                        
                        {/* Column headers */}
                        <div 
                          className="grid gap-4 text-sm text-gray-500 border-b pb-1 font-semibold mb-1"
                          style={{ gridTemplateColumns: "4fr 1fr 1fr" }}
                        >
                          <span></span>
                          <span className="text-right">{report.fiscal_year}-12-31</span>
                          <span className="text-right">{report.fiscal_year - 1}-12-31</span>
                        </div>
                        
                        {/* Block rows */}
                        <div className="space-y-0">
                          {visibleItems.map((item: any, index: number) => {
                            const styleClasses = getNoterStyleClasses(item.style);
                            const isHeading = ['H0', 'H1', 'H2', 'H3'].includes(item.style || '');
                            const isS2 = item.style === 'S2';
                            
                            // Check if previous row was also S2 to add spacing
                            const prevItem = index > 0 ? visibleItems[index - 1] : null;
                            const prevWasS2 = prevItem?.style === 'S2';
                            
                            // Build inline style with S2-consecutive padding
                            let rowStyle = { ...styleClasses.style };
                            if (isS2 && prevWasS2) {
                              rowStyle = { ...rowStyle, marginTop: '6pt' };
                            }
                            
                            return (
                              <div
                                key={item.row_id || index}
                                className={`${styleClasses.className} py-1`}
                                style={rowStyle}
                              >
                                <span className="text-gray-700">
                                  {item.row_title}
                                </span>
                                {!isHeading && (
                                  <>
                                    <span className="text-right">
                                      {item.current_amount !== null && item.current_amount !== undefined
                                        ? formatAmount(item.current_amount)
                                        : ""}
                                    </span>
                                    <span className="text-right">
                                      {item.previous_amount !== null && item.previous_amount !== undefined
                                        ? formatAmount(item.previous_amount)
                                        : ""}
                                    </span>
                                  </>
                                )}
                                {isHeading && (
                                  <>
                                    <span></span>
                                    <span></span>
                                  </>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    );
                  });
                })()}
              </div>
            ) : (
              <p className="text-gray-500">Inga noter tillgängliga.</p>
            )}
          </div>

          {/* Skattedeklaration Section */}
          <div
            ref={(el) => (sectionRefs.current["skattedeklaration"] = el)}
            className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6"
          >
            <div className="mb-4">
              <div className="flex justify-between items-center mb-2">
                <h2 className="text-xl font-semibold text-gray-900">Skattedeklaration INK2S</h2>
                <div className="flex items-center gap-2">
                  <span className="text-sm text-gray-600">Visa alla rader</span>
                  <Switch
                    checked={showAllInk2}
                    onCheckedChange={setShowAllInk2}
                  />
                </div>
              </div>
              <p className="text-sm text-gray-500">
                Här kan du se din INK2S deklaration. För att se hela skattedeklarationen gå till Mina dokument och ladda ner<br />
                Inkomstdeklaration som pdf eller SRU-filer.
              </p>
            </div>

            {report.ink2_data && report.ink2_data.length > 0 ? (
              <div>
                {/* Column Headers */}
                <div
                  className="grid gap-4 text-sm text-gray-500 border-b pb-2 font-semibold mb-2"
                  style={{ gridTemplateColumns: "3fr 1fr" }}
                >
                  <span></span>
                  <span className="text-right">{report.fiscal_year}</span>
                </div>

                {/* INK2 Rows */}
                <div className="space-y-0">
                  {(() => {
                    const headingStyles = ['TH1', 'TH2', 'TH3', 'H0', 'H1', 'H2', 'H3'];
                    
                    // Helper to check if row has a value (non-zero amount or Ja/Nej)
                    const hasValue = (item: any): boolean => {
                      // Check for Ja/Nej rows
                      if (item.variable_name === 'INK4.23a' || item.variable_name === 'INK4.24a') {
                        return true; // Always has Ja or Nej
                      }
                      // Check for non-zero amount
                      return item.amount !== null && item.amount !== undefined && item.amount !== 0;
                    };
                    
                    // Helper to check if item is a heading
                    const isHeading = (item: any): boolean => {
                      return headingStyles.includes(item.style || '');
                    };
                    
                    // Helper to check if row is basically eligible (before value check)
                    const isEligibleRow = (item: any): boolean => {
                      if (item.variable_name === 'INK4.23b' || item.variable_name === 'INK4.24b') return false;
                      if (item.variable_name === 'INK4_header') return false;
                      if (item.show_amount === 'NEVER') return false;
                      if (item.variable_name === 'INK_sarskild_loneskatt' && item.toggle_show === false) return false;
                      if (item.toggle_show !== true) return false;
                      return true;
                    };
                    
                    // Pre-compute which headings have visible children (only needed when showAllInk2 is OFF)
                    const headingsWithChildren = new Set<number>();
                    if (!showAllInk2) {
                      const data = report.ink2_data;
                      for (let i = 0; i < data.length; i++) {
                        const item = data[i];
                        if (!isEligibleRow(item)) continue;
                        if (isHeading(item)) continue;
                        
                        // This is a non-heading row - check if it has value
                        if (hasValue(item)) {
                          // Find the IMMEDIATE parent heading (first heading going backwards)
                          for (let j = i - 1; j >= 0; j--) {
                            const prevItem = data[j];
                            if (isHeading(prevItem) && isEligibleRow(prevItem)) {
                              headingsWithChildren.add(j);
                              break; // Only mark the immediate parent heading, not all ancestors
                            }
                          }
                        }
                      }
                    }
                    
                    // Helper to check if row should be visible
                    const shouldShowInk2Row = (item: any, index: number): boolean => {
                      // Basic eligibility check
                      if (!isEligibleRow(item)) return false;
                      
                      // Special case: INK_sarskild_loneskatt
                      if (item.variable_name === 'INK_sarskild_loneskatt') {
                        return hasValue(item);
                      }
                      
                      // If showAllInk2 is ON, show all eligible rows
                      if (showAllInk2) return true;
                      
                      // If showAllInk2 is OFF:
                      if (isHeading(item)) {
                        // Only show heading if it has visible children
                        return headingsWithChildren.has(index);
                      }
                      
                      // For non-headings, only show if has value
                      return hasValue(item);
                    };
                    
                    // Helper to check if row is a Ja/Nej row (radio button type)
                    const isJaNejRow = (variableName: string): boolean => {
                      return variableName === 'INK4.23a' || variableName === 'INK4.24a';
                    };
                    
                    // Get Ja/Nej value from stored data
                    const getJaNejValue = (variableName: string): string => {
                      // For INK4.23a: if amount = 1, then "Ja", else "Nej"
                      // For INK4.24a: if amount = 1, then "Ja", else "Nej"
                      const item = report.ink2_data.find((r: any) => r.variable_name === variableName);
                      const amount = item?.amount;
                      return amount === 1 ? "Ja" : "Nej";
                    };

                    // Style helper for INK2 rows
                    const getInk2StyleClasses = (style?: string, variableName?: string) => {
                      const s = style || '';
                      let additionalClasses = "";
                      let inlineStyle: React.CSSProperties = { gridTemplateColumns: "3fr 1fr" };
                      
                      // Bold styles
                      const boldStyles = ['H0','H1','H2','H3','S1','S2','S3','TH0','TH1','TH2','TH3','TS1','TS2','TS3'];
                      const specialBoldVariables = ['INK_skattemassigt_resultat'];
                      if (boldStyles.includes(s) || (variableName && specialBoldVariables.includes(variableName))) {
                        additionalClasses += ' font-semibold';
                      }
                      
                      // Heading styles
                      const headingStyles = ['H0','H1','H2','H3','TH0','TH1','TH2','TH3'];
                      if (headingStyles.includes(s)) {
                        additionalClasses += ' py-1.5';
                      }
                      
                      // Line styles (borders)
                      const lineStyles = ['S2','S3','TS2','TS3'];
                      if (lineStyles.includes(s) || variableName === 'INK_skattemassigt_resultat') {
                        additionalClasses += ' border-t border-b border-gray-200 py-1';
                      }
                      
                      // TH3: space before heading
                      if (s === 'TH3') {
                        inlineStyle = { ...inlineStyle, marginTop: '8pt', paddingTop: '8pt' };
                      }
                      
                      // TS2: more space
                      if (s === 'TS2') {
                        inlineStyle = { ...inlineStyle, marginTop: '6pt', marginBottom: '6pt' };
                      }
                      
                      // Extra space before "Skattemässigt resultat"
                      if (variableName === 'INK_skattemassigt_resultat') {
                        inlineStyle = { ...inlineStyle, marginTop: '12pt' };
                      }
                      
                      return {
                        className: `grid gap-4${additionalClasses}`,
                        style: inlineStyle,
                      };
                    };

                    return report.ink2_data
                      .map((item: any, originalIndex: number) => ({ item, originalIndex }))
                      .filter(({ item, originalIndex }) => shouldShowInk2Row(item, originalIndex))
                      .map(({ item, originalIndex }) => {
                        const styleClasses = getInk2StyleClasses(item.style, item.variable_name);
                        const isHeadingRow = ['TH1', 'TH2', 'TH3'].includes(item.style || '');
                        const isJaNej = isJaNejRow(item.variable_name);
                        const hasVisa = item.show_tag && item.account_details?.length > 0;
                        
                        return (
                          <div
                            key={item.variable_name || originalIndex}
                            className={`${styleClasses.className} ${isHeadingRow ? 'py-1' : 'py-0.5'}`}
                            style={{ ...styleClasses.style, gridTemplateColumns: "5fr 0.7fr 1fr" }}
                          >
                            {/* Row title */}
                            <span className="text-gray-600">{item.row_title}</span>
                            
                            {/* VISA button column - aligned */}
                            <span className="flex justify-end">
                              {hasVisa && (
                                <Popover>
                                  <PopoverTrigger asChild>
                                    <Button variant="outline" size="sm" className="h-5 px-2 text-xs">
                                      VISA
                                    </Button>
                                  </PopoverTrigger>
                                  <PopoverContent className="w-[500px] p-4 bg-white border shadow-lg">
                                    <PopoverClose className="absolute top-2 right-2 p-1 hover:bg-gray-100 rounded">
                                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12"/>
                                      </svg>
                                    </PopoverClose>
                                    <div className="space-y-3">
                                      <h4 className="font-medium text-sm pr-6">Detaljer för {item.row_title}</h4>
                                      <div className="overflow-x-auto">
                                        <table className="w-full text-sm">
                                          <thead>
                                            <tr className="border-b">
                                              <th className="text-left py-2 w-16">Konto</th>
                                              <th className="text-left py-2">Kontotext</th>
                                              <th className="text-right py-2 w-28">Belopp</th>
                                            </tr>
                                          </thead>
                                          <tbody>
                                            {item.account_details.map((detail: any, i: number) => (
                                              <tr key={i} className="border-b">
                                                <td className="py-2 w-16">{detail.account_id}</td>
                                                <td className="py-2">{detail.account_text || ""}</td>
                                                <td className="text-right py-2 w-28 whitespace-nowrap">
                                                  {new Intl.NumberFormat("sv-SE", { minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(Math.round(Math.abs(detail.balance)))} kr
                                                </td>
                                              </tr>
                                            ))}
                                            <tr className="border-t border-gray-300 font-semibold">
                                              <td className="py-2">Summa</td>
                                              <td></td>
                                              <td className="text-right py-2 whitespace-nowrap">
                                                {new Intl.NumberFormat("sv-SE", { minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(
                                                  Math.round(Math.abs(item.account_details.reduce(
                                                    (sum: number, d: any) => sum + (d.balance || 0),
                                                    0
                                                  )))
                                                )} kr
                                              </td>
                                            </tr>
                                          </tbody>
                                        </table>
                                      </div>
                                    </div>
                                  </PopoverContent>
                                </Popover>
                              )}
                            </span>
                            
                            {/* Amount/value column */}
                            {!isHeadingRow && (
                              <span className="text-right font-medium">
                                {isJaNej 
                                  ? getJaNejValue(item.variable_name)
                                  : `${new Intl.NumberFormat("sv-SE").format(Math.round(item.amount || 0))} kr`
                                }
                              </span>
                            )}
                            {isHeadingRow && <span></span>}
                          </div>
                        );
                      });
                  })()}
                </div>
              </div>
            ) : (
              <p className="text-gray-500">Ingen skatteberäkning tillgänglig.</p>
            )}
          </div>

          {/* Mina dokument Section */}
          <div
            ref={(el) => (sectionRefs.current["mina-dokument"] = el)}
            className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6"
          >
            <h2 className="text-xl font-semibold text-gray-900 mb-4">Dokument och filer</h2>
            <p className="text-sm text-gray-500 mb-6">
              Här finns alla dokument och filer för nedladdning. Din årsredovisning har skickats för signering, men du kan också ladda ner den som pdf här. Inkomstdeklarationen kan du antingen ladda ner som pdf eller som SRU-filer, som du sen kan ladda upp på Skatteverkets hemsida för att lämna in deklarationen. Dessutom finns en bokföringsinstruktion att ladda ner om justeringar på årets resultat har gjorts.
            </p>

            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              {/* Årsredovisning PDF */}
              <DownloadCard
                title="Årsredovisning"
                subtitle="Ladda ner pdf"
                reportId={report?.id}
                endpoint="annual-report"
                filename="arsredovisning.pdf"
              />
              
              {/* Inkomstdeklaration PDF */}
              <DownloadCard
                title="Inkomstdeklaration"
                subtitle="Ladda ner pdf"
                reportId={report?.id}
                endpoint="ink2-form"
                filename="INK2_inkomstdeklaration.pdf"
              />
              
              {/* Inkomstdeklaration SRU */}
              <DownloadCard
                title="Inkomstdeklaration"
                subtitle="Ladda ner SRU-filer"
                reportId={report?.id}
                endpoint="sru"
                filename="INK2.zip"
              />
              
              {/* Bokföringsinstruktion */}
              <DownloadCard
                title="Bokföringsinstruktion"
                subtitle="Ladda ner pdf"
                reportId={report?.id}
                endpoint="bokforing-instruktion"
                filename="bokforingsinstruktion.pdf"
              />
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

export default ReportView;

