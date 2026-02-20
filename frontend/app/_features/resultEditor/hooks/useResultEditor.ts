'use client';

import { useState, useCallback, useRef } from 'react';

export interface ResultFileInfo {
  filename: string;
  size_bytes: number;
  doc_count: number;
  created_at: string;
}

export interface DocSearchResult {
  docId: string;
  title: string;
  url: string;
  textLength: number;
  textSnippet?: string;
}

export type SearchField = 'all' | 'docId' | 'title' | 'text';

export interface BatchReplaceResult {
  docId: string;
  match_count: number;
  replaced: boolean;
}

export interface BatchResult {
  success: boolean;
  message: string;
  backup_file?: string;
  affected_count: number;
  results: BatchReplaceResult[];
}

export interface DocInfo {
  docId: string;
  title: string;
  url: string;
  text: string;
  hierarchy: string[];
}

export interface DiffLine {
  type: 'unchanged' | 'added' | 'removed';
  lineNumber: { old?: number; new?: number };
  content: string;
}

type EditorStep = 'select' | 'edit' | 'confirm' | 'batch-confirm';

export function useResultEditor() {
  const [step, setStep] = useState<EditorStep>('select');
  const [files, setFiles] = useState<ResultFileInfo[]>([]);
  const [selectedFile, setSelectedFile] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState('');
  const [searchField, setSearchField] = useState<SearchField>('all');
  const [searchResults, setSearchResults] = useState<DocSearchResult[]>([]);
  const [selectedDocId, setSelectedDocId] = useState<string>('');
  const [docInfo, setDocInfo] = useState<DocInfo | null>(null);
  const [originalText, setOriginalText] = useState('');
  const [modifiedText, setModifiedText] = useState('');
  const [diffLines, setDiffLines] = useState<DiffLine[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [findText, setFindText] = useState('');
  const [replaceText, setReplaceText] = useState('');
  const [useRegex, setUseRegex] = useState(false);
  const [matchCount, setMatchCount] = useState(0);

  const [checkedDocIds, setCheckedDocIds] = useState<Set<string>>(new Set());
  const [batchFindText, setBatchFindText] = useState('');
  const [batchReplaceText, setBatchReplaceText] = useState('');
  const [batchUseRegex, setBatchUseRegex] = useState(false);
  const [batchResult, setBatchResult] = useState<BatchResult | null>(null);

  const modifiedTextRef = useRef(modifiedText);
  modifiedTextRef.current = modifiedText;

  const fetchFiles = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const res = await fetch('/api/result-editor/files');
      if (!res.ok) throw new Error('파일 목록을 불러올 수 없습니다');
      const data = await res.json();
      setFiles(data);
      if (data.length > 0 && !selectedFile) {
        setSelectedFile(data[0].filename);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : '파일 목록 조회 실패');
    } finally {
      setIsLoading(false);
    }
  }, [selectedFile]);

  const searchDocs = useCallback(async (filename: string, query: string, field: SearchField) => {
    if (!filename) return;
    try {
      setIsLoading(true);
      setError(null);
      const params = new URLSearchParams({ filename, query, search_field: field, limit: '50' });
      const res = await fetch(`/api/result-editor/search-docs?${params}`);
      if (!res.ok) throw new Error('문서 검색에 실패했습니다');
      const data = await res.json();
      setSearchResults(data.results || []);
    } catch (e) {
      setError(e instanceof Error ? e.message : '문서 검색 실패');
    } finally {
      setIsLoading(false);
    }
  }, []);

  const loadDoc = useCallback(async (filename: string, docId: string) => {
    try {
      setIsLoading(true);
      setError(null);
      const params = new URLSearchParams({ filename, docId });
      const res = await fetch(`/api/result-editor/doc?${params}`);
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.error || '문서를 불러올 수 없습니다');
      }
      const data: DocInfo = await res.json();
      setDocInfo(data);
      setOriginalText(data.text);
      setModifiedText(data.text);
      setSelectedDocId(docId);
      setStep('edit');
      setSuccessMessage(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : '문서 로드 실패');
    } finally {
      setIsLoading(false);
    }
  }, []);

  const updateMatchCount = useCallback((text: string, find: string, regex: boolean) => {
    if (!find) {
      setMatchCount(0);
      return;
    }
    try {
      if (regex) {
        const re = new RegExp(find, 'g');
        const matches = text.match(re);
        setMatchCount(matches ? matches.length : 0);
      } else {
        let count = 0;
        let idx = 0;
        while ((idx = text.indexOf(find, idx)) !== -1) {
          count++;
          idx += find.length;
        }
        setMatchCount(count);
      }
    } catch {
      setMatchCount(0);
    }
  }, []);

  const handleFindTextChange = useCallback((value: string) => {
    setFindText(value);
    updateMatchCount(modifiedTextRef.current, value, useRegex);
  }, [useRegex, updateMatchCount]);

  const handleReplace = useCallback(() => {
    if (!findText) return;
    try {
      let newText: string;
      if (useRegex) {
        const re = new RegExp(findText, '');
        newText = modifiedTextRef.current.replace(re, replaceText);
      } else {
        const idx = modifiedTextRef.current.indexOf(findText);
        if (idx === -1) return;
        newText = modifiedTextRef.current.slice(0, idx) + replaceText + modifiedTextRef.current.slice(idx + findText.length);
      }
      setModifiedText(newText);
      updateMatchCount(newText, findText, useRegex);
    } catch {
      setError('잘못된 정규식 패턴입니다');
    }
  }, [findText, replaceText, useRegex, updateMatchCount]);

  const handleReplaceAll = useCallback(() => {
    if (!findText) return;
    try {
      let newText: string;
      if (useRegex) {
        const re = new RegExp(findText, 'g');
        newText = modifiedTextRef.current.replace(re, replaceText);
      } else {
        newText = modifiedTextRef.current.split(findText).join(replaceText);
      }
      setModifiedText(newText);
      updateMatchCount(newText, findText, useRegex);
    } catch {
      setError('잘못된 정규식 패턴입니다');
    }
  }, [findText, replaceText, useRegex, updateMatchCount]);

  const computeDiff = useCallback((oldText: string, newText: string): DiffLine[] => {
    const oldLines = oldText.split('\n');
    const newLines = newText.split('\n');
    const result: DiffLine[] = [];

    const maxLen = Math.max(oldLines.length, newLines.length);
    let oldIdx = 0;
    let newIdx = 0;

    while (oldIdx < oldLines.length || newIdx < newLines.length) {
      if (oldIdx < oldLines.length && newIdx < newLines.length) {
        if (oldLines[oldIdx] === newLines[newIdx]) {
          result.push({
            type: 'unchanged',
            lineNumber: { old: oldIdx + 1, new: newIdx + 1 },
            content: oldLines[oldIdx],
          });
          oldIdx++;
          newIdx++;
        } else {
          let foundNew = -1;
          for (let j = newIdx + 1; j < Math.min(newIdx + 10, newLines.length); j++) {
            if (oldLines[oldIdx] === newLines[j]) {
              foundNew = j;
              break;
            }
          }

          let foundOld = -1;
          for (let j = oldIdx + 1; j < Math.min(oldIdx + 10, oldLines.length); j++) {
            if (j < oldLines.length && newIdx < newLines.length && oldLines[j] === newLines[newIdx]) {
              foundOld = j;
              break;
            }
          }

          if (foundNew !== -1 && (foundOld === -1 || foundNew - newIdx <= foundOld - oldIdx)) {
            for (let j = newIdx; j < foundNew; j++) {
              result.push({ type: 'added', lineNumber: { new: j + 1 }, content: newLines[j] });
            }
            newIdx = foundNew;
          } else if (foundOld !== -1) {
            for (let j = oldIdx; j < foundOld; j++) {
              result.push({ type: 'removed', lineNumber: { old: j + 1 }, content: oldLines[j] });
            }
            oldIdx = foundOld;
          } else {
            result.push({ type: 'removed', lineNumber: { old: oldIdx + 1 }, content: oldLines[oldIdx] });
            result.push({ type: 'added', lineNumber: { new: newIdx + 1 }, content: newLines[newIdx] });
            oldIdx++;
            newIdx++;
          }
        }
      } else if (oldIdx < oldLines.length) {
        result.push({ type: 'removed', lineNumber: { old: oldIdx + 1 }, content: oldLines[oldIdx] });
        oldIdx++;
      } else {
        result.push({ type: 'added', lineNumber: { new: newIdx + 1 }, content: newLines[newIdx] });
        newIdx++;
      }
    }

    return result;
  }, []);

  const goToConfirm = useCallback(() => {
    const diff = computeDiff(originalText, modifiedText);
    setDiffLines(diff);
    setStep('confirm');
  }, [originalText, modifiedText, computeDiff]);

  const goBackToEdit = useCallback(() => {
    setStep('edit');
  }, []);

  const goBackToSelect = useCallback(() => {
    setStep('select');
    setDocInfo(null);
    setOriginalText('');
    setModifiedText('');
    setSelectedDocId('');
    setFindText('');
    setReplaceText('');
    setMatchCount(0);
    setSuccessMessage(null);
  }, []);

  const saveChanges = useCallback(async () => {
    if (!selectedFile || !selectedDocId) return;
    try {
      setIsSaving(true);
      setError(null);
      const res = await fetch('/api/result-editor/doc', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          filename: selectedFile,
          docId: selectedDocId,
          new_text: modifiedText,
        }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.error || '저장에 실패했습니다');
      }

      const data = await res.json();
      setSuccessMessage(
        `${data.message} (백업: ${data.backup_file})`
      );
      setOriginalText(modifiedText);
      setStep('select');
    } catch (e) {
      setError(e instanceof Error ? e.message : '저장 실패');
    } finally {
      setIsSaving(false);
    }
  }, [selectedFile, selectedDocId, modifiedText]);

  const resetModifiedText = useCallback(() => {
    setModifiedText(originalText);
  }, [originalText]);

  const toggleDocCheck = useCallback((docId: string) => {
    setCheckedDocIds((prev) => {
      const next = new Set(prev);
      if (next.has(docId)) next.delete(docId);
      else next.add(docId);
      return next;
    });
  }, []);

  const toggleAllDocs = useCallback(() => {
    setCheckedDocIds((prev) => {
      if (prev.size === searchResults.length) return new Set();
      return new Set(searchResults.map((d) => d.docId));
    });
  }, [searchResults]);

  const goToBatchConfirm = useCallback(() => {
    if (checkedDocIds.size === 0 || !batchFindText) return;
    setBatchResult(null);
    setStep('batch-confirm');
  }, [checkedDocIds, batchFindText]);

  const goBackFromBatch = useCallback(() => {
    setStep('select');
    setBatchResult(null);
  }, []);

  const executeBatchReplace = useCallback(async () => {
    if (!selectedFile || checkedDocIds.size === 0 || !batchFindText) return;
    try {
      setIsSaving(true);
      setError(null);
      const res = await fetch('/api/result-editor/batch', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          filename: selectedFile,
          doc_ids: Array.from(checkedDocIds),
          find_text: batchFindText,
          replace_text: batchReplaceText,
          use_regex: batchUseRegex,
        }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.error || '일괄 작업에 실패했습니다');
      }

      const data: BatchResult = await res.json();
      setBatchResult(data);

      if (data.affected_count > 0) {
        setSuccessMessage(`${data.message} (백업: ${data.backup_file})`);
        setCheckedDocIds(new Set());
        setBatchFindText('');
        setBatchReplaceText('');
        setStep('select');
        searchDocs(selectedFile, searchQuery, searchField);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : '일괄 작업 실패');
    } finally {
      setIsSaving(false);
    }
  }, [selectedFile, checkedDocIds, batchFindText, batchReplaceText, batchUseRegex, searchDocs, searchQuery, searchField]);

  const isBatchTextSearch = searchField === 'text' && searchQuery.length > 0;

  const hasChanges = originalText !== modifiedText;

  const diffStats = {
    added: diffLines.filter((l) => l.type === 'added').length,
    removed: diffLines.filter((l) => l.type === 'removed').length,
    unchanged: diffLines.filter((l) => l.type === 'unchanged').length,
  };

  return {
    step,
    files,
    selectedFile,
    setSelectedFile,
    searchQuery,
    setSearchQuery,
    searchField,
    setSearchField,
    searchResults,
    selectedDocId,
    docInfo,
    originalText,
    modifiedText,
    setModifiedText,
    diffLines,
    diffStats,
    isLoading,
    isSaving,
    error,
    setError,
    successMessage,
    findText,
    replaceText,
    setReplaceText,
    useRegex,
    setUseRegex,
    matchCount,
    hasChanges,
    checkedDocIds,
    toggleDocCheck,
    toggleAllDocs,
    batchFindText,
    setBatchFindText,
    batchReplaceText,
    setBatchReplaceText,
    batchUseRegex,
    setBatchUseRegex,
    batchResult,
    isBatchTextSearch,
    goToBatchConfirm,
    goBackFromBatch,
    executeBatchReplace,
    fetchFiles,
    searchDocs,
    loadDoc,
    handleFindTextChange,
    handleReplace,
    handleReplaceAll,
    goToConfirm,
    goBackToEdit,
    goBackToSelect,
    saveChanges,
    resetModifiedText,
  };
}
