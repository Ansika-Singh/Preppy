import React, { useState } from 'react';
import { Upload, FileText, CheckCircle, AlertCircle, Sparkles, BookOpen } from 'lucide-react';
import { Material, MaterialKind } from '../types';

interface MaterialsViewProps {
  materials: Material[];
  onUpload: (title: string, content: string, kind: MaterialKind) => Promise<void>;
  onExtractConcepts: (materialId: string) => Promise<void>;
  extractingId: string | null;
}

export const MaterialsView: React.FC<MaterialsViewProps> = ({
  materials,
  onUpload,
  onExtractConcepts,
  extractingId,
}) => {
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [kind, setKind] = useState<MaterialKind>('notes');
  const [uploading, setUploading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || !content.trim()) return;
    setUploading(true);
    try {
      await onUpload(title.trim(), content.trim(), kind);
      setTitle('');
      setContent('');
    } finally {
      setUploading(false);
    }
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setTitle(file.name.replace(/\.[^/.]+$/, ''));
    const reader = new FileReader();
    reader.onload = (event) => {
      const res = event.target?.result;
      if (typeof res === 'string') {
        setContent(res);
      }
    };
    reader.readAsText(file);
  };

  return (
    <div className="learn-materials-view">
      <div className="view-header">
        <div>
          <h2>Course Materials & Grounding</h2>
          <p>
            Upload your syllabus or lecture notes. Preppy verifies every generated question against your exact text
            substrings to ensure zero hallucinations.
          </p>
        </div>
      </div>

      <div className="materials-layout">
        {/* Upload Form */}
        <div className="materials-upload-card">
          <h3>Add Learning Material</h3>

          <div className="kind-selector-tabs">
            <button
              type="button"
              className={`kind-tab ${kind === 'notes' ? 'active' : ''}`}
              onClick={() => setKind('notes')}
            >
              Lecture Notes / Textbook
            </button>
            <button
              type="button"
              className={`kind-tab ${kind === 'syllabus' ? 'active' : ''}`}
              onClick={() => setKind('syllabus')}
            >
              Syllabus Only
            </button>
          </div>

          {kind === 'syllabus' ? (
            <div className="syllabus-honesty-notice">
              <AlertCircle size={16} />
              <span>
                <strong>Syllabus Honesty Rule:</strong> A syllabus is a list of topics, not course content. Questions
                generated from a syllabus alone are labeled <em>"Based on syllabus scope — not verified against your notes"</em>.
              </span>
            </div>
          ) : (
            <div className="notes-grounding-notice">
              <CheckCircle size={16} />
              <span>
                <strong>Verified Grounding Active:</strong> Every diagnostic question will link directly to an exact
                quoted passage from your notes.
              </span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="upload-form">
            <div className="form-group">
              <label>Material Title</label>
              <input
                type="text"
                placeholder="e.g. Engineering Physics — Chapter 2: Dynamics"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                required
              />
            </div>

            <div className="form-group">
              <div className="label-with-file">
                <label>Document Content (Text or Markdown)</label>
                <label className="file-upload-btn">
                  <Upload size={14} />
                  <span>Choose file...</span>
                  <input type="file" accept=".txt,.md,.text" onChange={handleFileUpload} style={{ display: 'none' }} />
                </label>
              </div>
              <textarea
                rows={8}
                placeholder="Paste course notes, key equations, and textbook sections here..."
                value={content}
                onChange={(e) => setContent(e.target.value)}
                required
              />
            </div>

            <button type="submit" className="submit-material-btn" disabled={uploading || !title.trim() || !content.trim()}>
              {uploading ? 'Processing & Ingesting...' : 'Ingest Material'}
            </button>
          </form>
        </div>

        {/* Existing Materials List */}
        <div className="materials-list-card">
          <h3>Ingested Materials ({materials.length})</h3>

          {materials.length === 0 ? (
            <div className="materials-empty">
              <FileText size={36} className="text-muted" />
              <p>No materials ingested yet. Use the form or load the sample dataset to get started.</p>
            </div>
          ) : (
            <div className="materials-items">
              {materials.map((m) => (
                <div key={m.id} className="material-card-row">
                  <div className="material-meta">
                    <span className="material-title">{m.title}</span>
                    <div className="material-tags">
                      <span className={`kind-badge ${m.kind}`}>{m.kind}</span>
                      <span className="grounding-badge">
                        {m.kind === 'syllabus' ? 'Ungrounded (Syllabus)' : '100% Grounded'}
                      </span>
                      <span className="char-count">{m.okf_text.length} chars</span>
                    </div>
                  </div>
                  <div className="material-actions">
                    <button
                      type="button"
                      className="extract-concepts-btn"
                      onClick={() => onExtractConcepts(m.id)}
                      disabled={extractingId === m.id}
                    >
                      <Sparkles size={14} />
                      <span>{extractingId === m.id ? 'Extracting...' : 'Build Concept Map'}</span>
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

