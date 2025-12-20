import { useState, useEffect, useRef } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
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
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { API_BASE_URL } from "@/config/api";
import { ChevronDown, User, FileText, Calculator, PenTool, HelpCircle, Download, Settings } from "lucide-react";

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

const ReportView = () => {
  const navigate = useNavigate();
  const { reportId } = useParams<{ reportId: string }>();
  const [searchParams] = useSearchParams();
  
  const [report, setReport] = useState<ReportData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const [activeSection, setActiveSection] = useState("resultatrakning");
  const [showAllRR, setShowAllRR] = useState(false);
  const [showAllBR, setShowAllBR] = useState(false);
  
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
      ref.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("summare_user");
    navigate("/");
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

  const getStyleClasses = (style?: string) => {
    const baseClasses = "grid gap-4";
    const classes: string[] = [baseClasses];
    const s = style || "";
    
    const headingStyles = ["H0", "H1", "H2", "H3"];
    const isHeading = headingStyles.includes(s);
    
    if (isHeading) {
      classes.push("py-1.5", "font-semibold");
    }
    
    // Summary/total lines
    const lineStyles = ["S1", "S2", "S3"];
    const isLine = lineStyles.includes(s);
    
    if (isLine) {
      classes.push("font-semibold");
    }
    
    if (s === "S2" || s === "S3") {
      classes.push("border-t", "border-b", "border-gray-200", "py-1");
    }
    
    if (s === "S1") {
      classes.push("border-t", "border-gray-300", "py-1");
    }
    
    // Compact default rows (not heading, not line)
    if (!isHeading && !isLine) {
      classes.push("py-0"); // Keep rows ultra-tight by default
    }

    return {
      className: classes.join(" "),
      style: { gridTemplateColumns: "4fr 0.5fr 1fr 1fr" },
    };
  };

  const shouldShowRow = (item: any, showAll: boolean, data: any[]): boolean => {
    const hiddenRowIds = [312, 310, 240, 241];
    if (item.id && hiddenRowIds.includes(Number(item.id))) return false;
    if (item.label?.toUpperCase() === "TILLGÅNGAR") return false;

    if (showAll) return true;

    const isHeading = ["H0", "H1", "H2", "H3", "S1", "S2", "S3"].includes(item.style || "");
    if (isHeading) {
      // Check if any non-heading row in same block_group has values
      if (item.block_group) {
        const blockRows = data.filter(
          (r) => r.block_group === item.block_group && !["H0", "H1", "H2", "H3", "S1", "S2", "S3"].includes(r.style || "")
        );
        return blockRows.some(
          (r) => (r.current_amount !== null && r.current_amount !== 0) ||
                 (r.previous_amount !== null && r.previous_amount !== 0)
        );
      }
      return true;
    }

    const hasNonZeroAmount =
      (item.current_amount !== null && item.current_amount !== 0) ||
      (item.previous_amount !== null && item.previous_amount !== 0);
    const isAlwaysShow = item.always_show === true;

    return hasNonZeroAmount || isAlwaysShow;
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
                <Icon className="w-5 h-5" />
                <span className="font-medium">{item.label}</span>
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
                <SelectTrigger className="w-[200px]">
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
          {/* Resultaträkning Section */}
          <div
            ref={(el) => (sectionRefs.current["resultatrakning"] = el)}
            className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6"
          >
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-semibold text-gray-900">Resultaträkning</h2>
              <div className="flex items-center space-x-2">
                <span className="text-sm text-gray-500">Visa alla rader</span>
                <Switch
                  checked={showAllRR}
                  onCheckedChange={setShowAllRR}
                  className={showAllRR ? "bg-green-500" : "bg-gray-300"}
                />
              </div>
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

                return (
                  <div
                    key={item.id || index}
                    className={styleClasses.className}
                    style={styleClasses.style}
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
                          <PopoverContent className="w-[500px] p-4 bg-white border shadow-lg">
                            <div className="space-y-3">
                              <h4 className="font-medium text-sm">Detaljer för {item.label}</h4>
                              <div className="overflow-x-auto">
                                <table className="w-full text-sm">
                                  <thead>
                                    <tr className="border-b">
                                      <th className="text-left py-2 w-16">Konto</th>
                                      <th className="text-left py-2">Kontotext</th>
                                      <th className="text-right py-2 w-24">{report.fiscal_year}</th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {item.account_details.map((detail: any, i: number) => (
                                      <tr key={i} className="border-b">
                                        <td className="py-2 w-16">{detail.account_id}</td>
                                        <td className="py-2">{detail.account_text || ""}</td>
                                        <td className="text-right py-2 w-24">
                                          {new Intl.NumberFormat("sv-SE").format(detail.balance)} kr
                                        </td>
                                      </tr>
                                    ))}
                                    <tr className="border-t border-gray-300 font-semibold">
                                      <td className="py-2">Summa</td>
                                      <td></td>
                                      <td className="text-right py-2">
                                        {new Intl.NumberFormat("sv-SE").format(
                                          item.account_details.reduce(
                                            (sum: number, d: any) => sum + (d.balance || 0),
                                            0
                                          )
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
                      {item.not_number || ""}
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

          {/* Placeholder sections for other nav items */}
          <div
            ref={(el) => (sectionRefs.current["balansrakning"] = el)}
            className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6"
          >
            <h2 className="text-xl font-semibold text-gray-900 mb-4">Balansräkning</h2>
            <p className="text-gray-500">Balansräkning kommer snart...</p>
          </div>

          <div
            ref={(el) => (sectionRefs.current["noter"] = el)}
            className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6"
          >
            <h2 className="text-xl font-semibold text-gray-900 mb-4">Noter</h2>
            <p className="text-gray-500">Noter kommer snart...</p>
          </div>
        </div>
      </main>
    </div>
  );
};

export default ReportView;

