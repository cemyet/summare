// API Configuration
export const API_BASE_URL = import.meta.env.VITE_API_URL || 'https://api.summare.se';

export const API_ENDPOINTS = {
  base: API_BASE_URL,
  uploadSeFile: `${API_BASE_URL}/upload-se-file`,
  uploadTwoSeFiles: `${API_BASE_URL}/upload-two-se-files`,
  generateReport: `${API_BASE_URL}/generate-report`,
  testParser: `${API_BASE_URL}/test-parser`,
  health: `${API_BASE_URL}/health`,
  companyInfo: `${API_BASE_URL}/company-info`,
  userReports: `${API_BASE_URL}/user-reports`,
  downloadReport: `${API_BASE_URL}/download-report`,
  recalculateInk2: `${API_BASE_URL}/api/recalculate-ink2`,
  addNoteNumbersToBr: `${API_BASE_URL}/api/add-note-numbers-to-br`,
  chatFlow: `${API_BASE_URL}/api/chat-flow`,
  // Förvaltningsberättelse endpoints
  managementReportTemplate: `${API_BASE_URL}/forvaltningsberattelse/template`,
  managementReportValidate: `${API_BASE_URL}/forvaltningsberattelse/validate`,
  managementReportSubmit: `${API_BASE_URL}/forvaltningsberattelse/submit`,
  // Bolagsverket API endpoints
  bolagsverketCompany: `${API_BASE_URL}/bolagsverket/company`,
  bolagsverketDocuments: `${API_BASE_URL}/bolagsverket/documents`,
  bolagsverketDocument: `${API_BASE_URL}/bolagsverket/document`,
  bolagsverketHealth: `${API_BASE_URL}/bolagsverket/health`,
} as const; 