export interface Message {
  id: string;
  type: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  progress?: ProgressStep[];
  result?: RAGCrawlingResult[];
}

export interface ProgressStep {
  id: string;
  message: string;
  status: 'pending' | 'active' | 'completed' | 'error';
  timestamp: Date;
}

export interface CrawlingResult {
  title?: string;
  textLength?: number;
  linkCount?: number;
  links?: string[];
  screenshot?: string;
  summary?: string;
  error?: string;
}

// RAG 크롤링 결과 타입
export interface RAGCrawlingResult {
  url: string;
  murl?: string;
  hierarchy: string[];
  title: string;
  text: string;
  startdate: string;
  enddate: string;
  metadata: {
    images?: Array<{ src: string; alt?: string }>;
    links?: Array<{ url: string; text?: string }>;
  };
  source?: {
    title?: string;
    menu_path?: string;
  };
  error?: string;
  status?: string;
}

export interface SSEEvent {
  type: 'status' | 'tool_call' | 'partial' | 'final' | 'error';
  data: any;
  timestamp: string;
}

export interface TaskResponse {
  taskId: string;
}


// JSON 비교 관련 타입
export interface ManagerInfo {
  team_name: string;
  manager_names: string;
}

export interface EmptyUrlItem {
  url: string;
  title: string;
  hierarchy: string;
  manager_info?: ManagerInfo;
}

export interface JsonComparisonResult {
  id: string;
  file1_name: string;
  file2_name: string;
  file1_size: number;
  file2_size: number;
  total_objects_1: number;
  total_objects_2: number;
  objects_removed: number;
  objects_added: number;
  objects_modified: number;
  objects_unchanged: number;
  total_changes: number;
  javascript_pages: number;
  created_at: string;
  status: string;
  error_message?: string;
  pdf_file_path?: string;
  summary_report?: string;
}

export interface JsonComparisonTask {
  id: string;
  file1_name: string;
  file2_name: string;
  created_at: string;
  status: string;
  result?: JsonComparisonResult;
  error_message?: string;
  empty_url_items?: EmptyUrlItem[];
}
