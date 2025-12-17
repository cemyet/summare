import { API_ENDPOINTS } from '@/config/api';

export interface UploadResponse {
  success: boolean;
  company_data: any;
  message: string;
}

export interface TestParserResponse {
  success: boolean;
  company_info: any;
  current_accounts_count: number;
  previous_accounts_count: number;
  current_accounts_sample: Record<string, number>;
  previous_accounts_sample: Record<string, number>;
  rr_count: number;
  rr_sample: any[];
  br_count: number;
  br_sample: any[];
  message: string;
}

class ApiService {
  private async makeRequest<T>(
    url: string, 
    options: RequestInit = {}
  ): Promise<T> {
    try {
      const response = await fetch(url, {
        headers: {
          'Content-Type': 'application/json',
          ...options.headers,
        },
        ...options,
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('API request failed:', error);
      throw error;
    }
  }

  async uploadSeFile(file: File): Promise<UploadResponse> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(API_ENDPOINTS.uploadSeFile, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      // Extract the actual error message from the response
      try {
        const errorData = await response.json();
        const errorMessage = errorData.detail || `Upload failed: ${response.status}`;
        throw new Error(errorMessage);
      } catch (parseError) {
        // If we can't parse the error response, fall back to generic message
        throw new Error(`Upload failed: ${response.status}`);
      }
    }

    return await response.json();
  }

  async uploadTwoSeFiles(currentYearFile: File, previousYearFile: File): Promise<UploadResponse> {
    const formData = new FormData();
    formData.append('current_year_file', currentYearFile);
    formData.append('previous_year_file', previousYearFile);

    const response = await fetch(API_ENDPOINTS.uploadTwoSeFiles, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      // Extract the actual error message from the response
      try {
        const errorData = await response.json();
        console.log('uploadTwoSeFiles Error response data:', errorData);
        const errorMessage = errorData.detail || `Upload failed: ${response.status}`;
        console.log('uploadTwoSeFiles Extracted error message:', errorMessage);
        throw new Error(errorMessage);
      } catch (parseError) {
        // If we can't parse the error response, fall back to generic message
        console.log('uploadTwoSeFiles Failed to parse error response:', parseError);
        console.log('uploadTwoSeFiles Response status:', response.status);
        console.log('uploadTwoSeFiles Response headers:', response.headers);
        throw new Error(`Upload failed: ${response.status}`);
      }
    }

    return await response.json();
  }

  async testParser(file: File): Promise<TestParserResponse> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(API_ENDPOINTS.testParser, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      throw new Error(`Parser test failed: ${response.status}`);
    }

    return await response.json();
  }

  async healthCheck(): Promise<{ status: string; timestamp: string }> {
    return this.makeRequest(API_ENDPOINTS.health);
  }

  async getCompanyInfo(orgNumber: string): Promise<any> {
    return this.makeRequest(`${API_ENDPOINTS.companyInfo}/${orgNumber}`);
  }

  async getChatFlowStep(stepNumber: number) {
    try {
      const response = await this.makeRequest(`${API_ENDPOINTS.chatFlow}/${stepNumber}`);
      return response;
    } catch (error) {
      console.error('Error getting chat flow step:', error);
      throw error;
    }
  }

  async getNextChatFlowStep(currentStep: number): Promise<{
    success: boolean;
    question?: any;
    options?: any[];
    next_step?: number;
  }> {
    return this.makeRequest(`${API_ENDPOINTS.chatFlow}/next/${currentStep}`);
  }

  async processChatChoice(data: {
    step_number: number;
    option_value: string;
    context?: Record<string, any>;
  }): Promise<{
    success: boolean;
    result: {
      action_type: string;
      action_data?: any;
      next_step?: number;
    };
  }> {
    return this.makeRequest(`${API_ENDPOINTS.chatFlow}/process-choice`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async recalculateInk2(data: {
    current_accounts: Record<string, number>;
    fiscal_year?: number;
    rr_data: any[];
    br_data: any[];
    manual_amounts: Record<string, number>;
    justering_sarskild_loneskatt?: number;
    ink4_14a_outnyttjat_underskott?: number;
    ink4_16_underskott_adjustment?: number;
  }): Promise<{ success: boolean; ink2_data: any[] }> {
    return this.makeRequest(API_ENDPOINTS.recalculateInk2, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async addNoteNumbersToBr(data: {
    br_data: any[];
    rr_data?: any[];
    note_numbers?: Record<string, number>;
  }): Promise<{ success: boolean; br_data: any[]; rr_data?: any[] }> {
    return this.makeRequest(API_ENDPOINTS.addNoteNumbersToBr, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  // Förvaltningsberättelse API methods
  async getManagementReportTemplate(): Promise<{ success: boolean; template: any; message: string }> {
    return this.makeRequest(API_ENDPOINTS.managementReportTemplate);
  }

  async validateManagementReport(reportData: any): Promise<{ success: boolean; validation_result: any; message: string }> {
    return this.makeRequest(API_ENDPOINTS.managementReportValidate, {
      method: 'POST',
      body: JSON.stringify(reportData),
    });
  }

  async submitManagementReport(reportRequest: any): Promise<{ success: boolean; validation_result: any; submission_id?: string; message: string }> {
    return this.makeRequest(API_ENDPOINTS.managementReportSubmit, {
      method: 'POST',
      body: JSON.stringify(reportRequest),
    });
  }

  async getCompanyInfoFromBolagsverket(orgNumber: string): Promise<{ success: boolean; company_info: any; message: string }> {
    return this.makeRequest(`${API_ENDPOINTS.bolagsverketCompany}/${orgNumber}`);
  }

  async getCompanyDocumentsFromBolagsverket(orgNumber: string): Promise<{ success: boolean; document_list: any; message: string }> {
    return this.makeRequest(`${API_ENDPOINTS.bolagsverketDocuments}/${orgNumber}`);
  }

  async getDocumentFromBolagsverket(documentId: string): Promise<{ success: boolean; document: any; message: string }> {
    return this.makeRequest(`${API_ENDPOINTS.bolagsverketDocument}/${documentId}`);
  }

  async checkBolagsverketHealth(): Promise<{ success: boolean; healthy: boolean; message: string }> {
    return this.makeRequest(API_ENDPOINTS.bolagsverketHealth);
  }

  async getMostRecentPayment(): Promise<{ success: boolean; customer_email: string | null; organization_number: string | null; message?: string }> {
    return this.makeRequest(`${API_ENDPOINTS.base}/api/payments/get-most-recent`);
  }

  async getCustomerEmail(organizationNumber: string): Promise<{ success: boolean; customer_email: string | null; organization_number?: string | null; message?: string }> {
    return this.makeRequest(`${API_ENDPOINTS.base}/api/payments/get-customer-email?organization_number=${encodeURIComponent(organizationNumber)}`);
  }

  async createUserAccount(username: string, organizationNumber: string, companyName?: string): Promise<{ success: boolean; message: string; username: string; user_exist: boolean; email_sent: boolean }> {
    const body: any = { username, organization_number: organizationNumber };
    if (companyName) {
      body.company_name = companyName;
    }
    return this.makeRequest(`${API_ENDPOINTS.base}/api/users/create-account`, {
      method: 'POST',
      body: JSON.stringify(body),
    });
  }

  async checkUserExists(username: string, organizationNumber: string): Promise<{ success: boolean; user_exist: boolean; org_in_user: boolean }> {
    return this.makeRequest(`${API_ENDPOINTS.base}/api/users/check-exists?username=${encodeURIComponent(username)}&organization_number=${encodeURIComponent(organizationNumber)}`);
  }

  // Annual Report Data Storage for Mina Sidor
  // Pass the full companyData object - backend extracts what it needs (like XBRL export)
  async saveAnnualReportData(data: {
    companyData: any;
    status?: string;
  }): Promise<{ success: boolean; message: string; action?: string }> {
    return this.makeRequest(`${API_ENDPOINTS.base}/api/annual-report-data/save`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getAnnualReportData(
    organizationNumber: string,
    fiscalYearStart?: string,
    fiscalYearEnd?: string
  ): Promise<{ success: boolean; message: string; data: any }> {
    let url = `${API_ENDPOINTS.base}/api/annual-report-data/get?organization_number=${encodeURIComponent(organizationNumber)}`;
    if (fiscalYearStart && fiscalYearEnd) {
      url += `&fiscal_year_start=${encodeURIComponent(fiscalYearStart)}&fiscal_year_end=${encodeURIComponent(fiscalYearEnd)}`;
    }
    return this.makeRequest(url);
  }

  async listAnnualReportsByUser(username: string): Promise<{ success: boolean; message: string; data: any[] }> {
    return this.makeRequest(`${API_ENDPOINTS.base}/api/annual-report-data/list-by-user?username=${encodeURIComponent(username)}`);
  }
}

export const apiService = new ApiService();