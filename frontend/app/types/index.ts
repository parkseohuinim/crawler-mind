export interface Message {
  id: string;
  type: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  progress?: ProgressStep[];
  result?: CrawlingResult;
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

export interface SSEEvent {
  type: 'status' | 'tool_call' | 'partial' | 'final' | 'error';
  data: any;
  timestamp: string;
}

export interface TaskResponse {
  taskId: string;
}

export type ProcessingMode = 'auto' | 'basic';
