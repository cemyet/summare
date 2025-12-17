import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { API_BASE_URL } from "@/config/api";

interface UserSession {
  userId: string;
  username: string;
  organizations: string[];
}

interface Report {
  id: string;
  fiscal_year_start: string;
  fiscal_year_end: string;
  status: string;
  updated_at: string;
  created_at: string;
}

interface CompanyData {
  organization_number: string;
  company_name: string;
  reports: Report[];
  signing_status?: string;
  latest_fiscal_year?: string;
  payment_info?: {
    email: string;
    paid_at: string;
    amount: number;
  };
}

const MinaSidor = () => {
  const navigate = useNavigate();
  const [user, setUser] = useState<UserSession | null>(null);
  const [companies, setCompanies] = useState<CompanyData[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    // Check if user is logged in
    const storedUser = localStorage.getItem("summare_user");
    if (!storedUser) {
      navigate("/");
      return;
    }

    const parsedUser = JSON.parse(storedUser) as UserSession;
    setUser(parsedUser);

    // Fetch user's companies and reports
    fetchUserData(parsedUser);
  }, [navigate]);

  const fetchUserData = async (userSession: UserSession) => {
    setIsLoading(true);
    setError("");

    try {
      // Fetch annual reports for user
      const reportsResponse = await fetch(
        `${API_BASE_URL}/api/annual-report-data/list-by-user?username=${encodeURIComponent(userSession.username)}`
      );
      const reportsData = await reportsResponse.json();

      if (reportsData.success) {
        // Enrich with company info
        const enrichedCompanies = await Promise.all(
          reportsData.data.map(async (company: CompanyData) => {
            try {
              const infoResponse = await fetch(
                `${API_BASE_URL}/api/company/info-by-org/${company.organization_number}`
              );
              const infoData = await infoResponse.json();
              
              return {
                ...company,
                signing_status: infoData.signing_status,
                payment_info: infoData.payment_info,
              };
            } catch {
              return company;
            }
          })
        );

        setCompanies(enrichedCompanies);
      } else {
        // No reports found, but check if user has organizations with payments
        if (userSession.organizations && userSession.organizations.length > 0) {
          const companiesFromOrgs = await Promise.all(
            userSession.organizations.map(async (orgNumber: string) => {
              try {
                const infoResponse = await fetch(
                  `${API_BASE_URL}/api/company/info-by-org/${orgNumber}`
                );
                const infoData = await infoResponse.json();
                
                return {
                  organization_number: orgNumber,
                  company_name: infoData.company_name || `Företag ${orgNumber}`,
                  reports: [],
                  signing_status: infoData.signing_status,
                  payment_info: infoData.payment_info,
                };
              } catch {
                return {
                  organization_number: orgNumber,
                  company_name: `Företag ${orgNumber}`,
                  reports: [],
                };
              }
            })
          );

          setCompanies(companiesFromOrgs);
        }
      }
    } catch (err) {
      console.error("Error fetching user data:", err);
      setError("Kunde inte hämta data. Försök igen.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("summare_user");
    navigate("/");
  };

  const formatOrgNumber = (orgNumber: string) => {
    // Format as XXXXXX-XXXX
    const clean = orgNumber.replace(/\D/g, "");
    if (clean.length === 10) {
      return `${clean.slice(0, 6)}-${clean.slice(6)}`;
    }
    return orgNumber;
  };

  const formatDate = (dateString: string) => {
    if (!dateString) return "";
    const date = new Date(dateString);
    return date.toLocaleDateString("sv-SE", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  };

  const getStatusBadge = (status: string) => {
    const statusConfig: Record<string, { label: string; className: string }> = {
      draft: { label: "Utkast", className: "bg-gray-100 text-gray-700" },
      submitted: { label: "Inskickad", className: "bg-blue-100 text-blue-700" },
      signed: { label: "Signerad", className: "bg-green-100 text-green-700" },
      pending_signature: { label: "Väntar signering", className: "bg-yellow-100 text-yellow-700" },
    };

    const config = statusConfig[status] || statusConfig.draft;

    return (
      <span className={`px-2 py-1 rounded-full text-xs font-medium ${config.className}`}>
        {config.label}
      </span>
    );
  };

  const getSigningStatusBadge = (status: string | undefined) => {
    if (!status) return null;

    const statusConfig: Record<string, { label: string; className: string }> = {
      pending: { label: "Väntar på signering", className: "bg-yellow-100 text-yellow-700" },
      completed: { label: "Signerad", className: "bg-green-100 text-green-700" },
      cancelled: { label: "Avbruten", className: "bg-red-100 text-red-700" },
    };

    const config = statusConfig[status] || { label: status, className: "bg-gray-100 text-gray-700" };

    return (
      <span className={`px-2 py-1 rounded-full text-xs font-medium ${config.className}`}>
        {config.label}
      </span>
    );
  };

  if (!user) {
    return null;
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center gap-6">
              <a href="/" className="text-2xl font-bold text-summare-navy">
                Summare
              </a>
              <span className="text-gray-300">|</span>
              <span className="text-gray-600 font-medium">Mina sidor</span>
            </div>
            
            <div className="flex items-center gap-4">
              <div className="text-right">
                <p className="text-sm font-medium text-gray-900">{user.username}</p>
                <p className="text-xs text-gray-500">
                  {companies.length} {companies.length === 1 ? "företag" : "företag"}
                </p>
              </div>
              <Button variant="ghost" size="sm" onClick={handleLogout}>
                Logga ut
              </Button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-gray-900">Välkommen tillbaka!</h1>
          <p className="text-gray-600 mt-1">
            Här kan du se och hantera dina årsredovisningar.
          </p>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <div className="flex items-center gap-3 text-gray-500">
              <svg className="animate-spin h-6 w-6" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              Laddar dina företag...
            </div>
          </div>
        ) : error ? (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
            {error}
          </div>
        ) : companies.length === 0 ? (
          <Card>
            <CardContent className="py-12 text-center">
              <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <svg className="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                </svg>
              </div>
              <h3 className="text-lg font-medium text-gray-900 mb-2">Inga företag ännu</h3>
              <p className="text-gray-500 mb-4">
                När du har skapat din första årsredovisning kommer den att visas här.
              </p>
              <Button onClick={() => navigate("/app")}>
                Skapa årsredovisning
              </Button>
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-6">
            {companies.map((company) => (
              <Card key={company.organization_number} className="overflow-hidden">
                <CardHeader className="bg-gradient-to-r from-summare-navy to-summare-navy/80 text-white">
                  <div className="flex justify-between items-start">
                    <div>
                      <CardTitle className="text-xl">
                        {company.company_name || `Företag ${formatOrgNumber(company.organization_number)}`}
                      </CardTitle>
                      <p className="text-white/80 text-sm mt-1">
                        {formatOrgNumber(company.organization_number)}
                      </p>
                    </div>
                    {company.signing_status && getSigningStatusBadge(company.signing_status)}
                  </div>
                </CardHeader>
                
                <CardContent className="p-0">
                  {company.reports && company.reports.length > 0 ? (
                    <div className="divide-y divide-gray-100">
                      {company.reports.map((report) => (
                        <div
                          key={report.id}
                          className="px-6 py-4 flex items-center justify-between hover:bg-gray-50 transition-colors"
                        >
                          <div className="flex items-center gap-4">
                            <div className="w-10 h-10 bg-blue-50 rounded-lg flex items-center justify-center">
                              <svg className="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                              </svg>
                            </div>
                            <div>
                              <p className="font-medium text-gray-900">
                                Årsredovisning {report.fiscal_year_end?.slice(0, 4)}
                              </p>
                              <p className="text-sm text-gray-500">
                                {formatDate(report.fiscal_year_start)} – {formatDate(report.fiscal_year_end)}
                              </p>
                            </div>
                          </div>
                          
                          <div className="flex items-center gap-4">
                            {getStatusBadge(report.status)}
                            <span className="text-sm text-gray-500">
                              Uppdaterad {formatDate(report.updated_at)}
                            </span>
                            <Button variant="outline" size="sm">
                              Öppna
                            </Button>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="px-6 py-8 text-center">
                      <p className="text-gray-500 mb-4">
                        Ingen sparad årsredovisning för detta företag ännu.
                      </p>
                      <Button variant="outline" onClick={() => navigate("/app")}>
                        Skapa ny årsredovisning
                      </Button>
                    </div>
                  )}

                  {/* Quick Actions */}
                  <div className="px-6 py-4 bg-gray-50 border-t border-gray-100">
                    <div className="flex items-center justify-between">
                      <div className="text-sm text-gray-500">
                        {company.payment_info && (
                          <>
                            Senaste betalning: {formatDate(company.payment_info.paid_at)} •{" "}
                            {company.payment_info.amount} kr
                          </>
                        )}
                      </div>
                      <div className="flex gap-2">
                        <Button variant="ghost" size="sm">
                          <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                          </svg>
                          Ladda ner
                        </Button>
                        <Button variant="ghost" size="sm">
                          <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z" />
                          </svg>
                          Dela
                        </Button>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {/* Create New Report Button */}
        {companies.length > 0 && (
          <div className="mt-8 text-center">
            <Button size="lg" onClick={() => navigate("/app")}>
              <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
              </svg>
              Skapa ny årsredovisning
            </Button>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="bg-white border-t border-gray-200 mt-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex items-center justify-between">
            <p className="text-sm text-gray-500">
              © 2024 Summare. Alla rättigheter förbehållna.
            </p>
            <div className="flex gap-6">
              <a href="#" className="text-sm text-gray-500 hover:text-gray-700">
                Support
              </a>
              <a href="#" className="text-sm text-gray-500 hover:text-gray-700">
                Villkor
              </a>
              <a href="#" className="text-sm text-gray-500 hover:text-gray-700">
                Integritet
              </a>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default MinaSidor;

