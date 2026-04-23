import { useState, useRef } from 'react';
import { Send, Paperclip, X, Mic, Square, Loader2 } from 'lucide-react';
import { useSpeechToText } from './useSpeechToText';

export default function ChatInput({ onSend, disabled, files, setFiles }) {
  const [text, setText] = useState('');
  const fileInputRef = useRef(null);
  const { state: micState, error: micError, start, stopAndTranscribe } = useSpeechToText();

  const isRecording = micState === 'recording';
  const isProcessing = micState === 'processing';

  const handleFileSelect = (e) => {
    if (e.target.files) {
      const selected = Array.from(e.target.files);
      setFiles((prev) => [...prev, ...selected]);
    }
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const removeFile = (index) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!text.trim() && files.length === 0) return;
    onSend(text, files);
    setText('');
    setFiles([]);
  };

  const handleMicClick = async () => {
    if (isProcessing) return;
    if (!isRecording) {
      await start();
      return;
    }
    const transcript = await stopAndTranscribe();
    if (transcript) {
      setText((prev) => (prev ? `${prev} ${transcript}`.replace(/\s+/g, ' ').trim() : transcript));
    }
  };

  const canSend = (text.trim() || files.length > 0) && !disabled && !isRecording && !isProcessing;
  const inputsDisabled = disabled || isRecording || isProcessing;

  const micTitle = isRecording
    ? 'Detener grabación y transcribir'
    : isProcessing
      ? 'Transcribiendo...'
      : 'Grabar audio (se transcribirá a texto)';

  return (
    <>
      {micError && <p className="mic-error">{micError}</p>}
      {files.length > 0 && (
        <div className="files-preview">
          {files.map((file, idx) => (
            <div key={idx} className="file-pill">
              <span className="file-name">{file.name}</span>
              <button type="button" className="remove-file-btn" onClick={() => removeFile(idx)}>
                <X size={14} />
              </button>
            </div>
          ))}
        </div>
      )}
      <form onSubmit={handleSubmit} className="input-form">
        <button
          type="button"
          className="attach-button"
          onClick={() => fileInputRef.current?.click()}
          disabled={inputsDisabled}
        >
          <Paperclip size={20} />
        </button>
        <input
          type="file"
          multiple
          hidden
          ref={fileInputRef}
          onChange={handleFileSelect}
        />
        <input
          type="text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={
            isRecording
              ? 'Grabando... toca el cuadrado para detener'
              : isProcessing
                ? 'Transcribiendo tu audio...'
                : 'Escribe tu mensaje a Yoko...'
          }
          className="chat-input"
          disabled={inputsDisabled}
        />
        <button
          type="button"
          className={`mic-button ${isRecording ? 'recording' : ''} ${isProcessing ? 'processing' : ''}`}
          onClick={handleMicClick}
          disabled={disabled || isProcessing}
          title={micTitle}
          aria-label={micTitle}
        >
          {isProcessing ? (
            <Loader2 size={18} className="spin" />
          ) : isRecording ? (
            <Square size={16} fill="currentColor" />
          ) : (
            <Mic size={18} />
          )}
        </button>
        <button type="submit" className="send-button" disabled={!canSend}>
          <Send size={18} />
        </button>
      </form>
    </>
  );
}
